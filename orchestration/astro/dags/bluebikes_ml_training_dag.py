"""Weekly BigQuery ML retraining for station availability (1, 3, 6 and 24 h horizons).

All compute runs inside BigQuery. Each task renders one ml/sql template and submits it as a single
BigQuery job (see ml/run_bqml.py). Per horizon:

    split -> train (logreg, plus boosted at 24 h) -> score -> metrics -> evaluate -> publish

then publish_forecast_view refreshes ml_models.station_forecasts, the table the frontend reads
(docs/ml/forecast-serving-contract.md). A horizon is only published if it passes evaluate.

check_for_new_labels skips the whole run when ml.station_availability_training_ready has no origins
newer than the last split, so a weekly schedule does not re-bill identical training. Trigger with
{"force_retrain": true} to retrain anyway.
"""
import importlib.util
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from airflow.providers.standard.operators.python import PythonOperator, ShortCircuitOperator
from airflow.sdk import DAG, Param, TaskGroup


def ml_module():
    """Load ml/run_bqml.py from the image, independent of where the DAG bundle is stored."""
    path = Path(os.environ.get("AIRFLOW_HOME", "/usr/local/airflow")) / "ml" / "run_bqml.py"
    spec = importlib.util.spec_from_file_location("bluebikes_run_bqml", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def check_for_new_labels(params):
    if params.get("force_retrain"):
        return True
    return ml_module().has_new_labels()


def run_bqml_step(step, horizon_minutes, run_id):
    ml_module().run_step(step, horizon_minutes, run_id=run_id)


def evaluate_horizon(horizon_minutes, run_id):
    return ml_module().record_and_check(horizon_minutes, run_id=run_id)


# Kept in sync with ml/run_bqml.py HORIZONS (a test enforces this). Defined here so the DAG's shape
# does not depend on importing the ML code at parse time.
HORIZON_MODELS = {
    60: ("logreg",),
    180: ("logreg",),
    360: ("logreg",),
    1440: ("logreg", "boosted"),
}
TRAIN_STEPS = {"logreg": "02_train_logreg", "boosted": "03_train_boosted"}
RUN_ID = "{{ run_id }}"


with DAG(
    dag_id="bluebikes_ml_training_dag",
    description="Weekly BigQuery ML retraining and evaluation for bike availability forecasts",
    start_date=datetime(2026, 11, 16, tzinfo=timezone.utc),
    # Monday 08:00 UTC, after the daily 06:00 weather ingestion and dbt build.
    schedule="0 8 * * 1",
    catchup=False,
    max_active_runs=1,
    # Training bills BigQuery; a deploy should not start it until someone unpauses the DAG.
    is_paused_upon_creation=True,
    params={"force_retrain": Param(False, type="boolean",
                                   description="Retrain even if there are no new labelled origins")},
    default_args={
        "owner": "ml",
        "retries": 1,
        "retry_delay": timedelta(minutes=5),
        "execution_timeout": timedelta(hours=1),
    },
    tags=["bluebikes", "ml", "bigquery-ml"],
) as dag:
    check_new_labels = ShortCircuitOperator(
        task_id="check_for_new_labels",
        python_callable=check_for_new_labels,
    )

    horizon_groups = []
    for horizon, models in HORIZON_MODELS.items():
        with TaskGroup(group_id=f"h{horizon}") as horizon_group:
            split = PythonOperator(
                task_id="split",
                python_callable=run_bqml_step,
                op_kwargs={"step": "01_split", "horizon_minutes": horizon, "run_id": RUN_ID},
            )
            train = [
                PythonOperator(
                    task_id=f"train_{model}",
                    python_callable=run_bqml_step,
                    op_kwargs={"step": TRAIN_STEPS[model], "horizon_minutes": horizon, "run_id": RUN_ID},
                    # A retry re-bills the whole training job; investigate a failure before rerunning.
                    retries=0,
                    execution_timeout=timedelta(hours=2),
                )
                for model in models
            ]
            score = PythonOperator(
                task_id="score",
                python_callable=run_bqml_step,
                op_kwargs={"step": "04_score", "horizon_minutes": horizon, "run_id": RUN_ID},
            )
            metrics = PythonOperator(
                task_id="metrics",
                python_callable=run_bqml_step,
                op_kwargs={"step": "05_metrics", "horizon_minutes": horizon, "run_id": RUN_ID},
            )
            evaluate = PythonOperator(
                task_id="evaluate",
                python_callable=evaluate_horizon,
                op_kwargs={"horizon_minutes": horizon, "run_id": RUN_ID},
                retries=0,
            )
            publish = PythonOperator(
                task_id="publish",
                python_callable=run_bqml_step,
                op_kwargs={"step": "06_publish", "horizon_minutes": horizon, "run_id": RUN_ID},
            )
            split >> train >> score >> metrics >> evaluate >> publish
        check_new_labels >> horizon_group
        horizon_groups.append(horizon_group)

    publish_view = PythonOperator(
        task_id="publish_forecast_view",
        python_callable=run_bqml_step,
        op_kwargs={"step": "07_forecast_view", "horizon_minutes": None, "run_id": RUN_ID},
    )
    horizon_groups >> publish_view
