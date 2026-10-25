import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from airflow.sdk import DAG
from airflow.providers.standard.operators.python import PythonOperator


def ingest_trips(data_interval_end):
    project_root = Path(os.environ.get("AIRFLOW_HOME", "/usr/local/airflow"))
    script = project_root / "ingestion" / "historical_trips.py"

    last_month = data_interval_end.replace(day=1) - timedelta(days=1)
    trip_month = last_month.strftime("%Y%m")

    subprocess.run(
        [sys.executable, str(script)],
        cwd=str(project_root),
        env={**os.environ, "TRIP_MONTH": trip_month},
        check=True,
        timeout=1800,
    )


def run_dbt_step(command, dag_id, run_id):
    project_root = Path(os.environ.get("AIRFLOW_HOME", "/usr/local/airflow"))
    subprocess.run(
        [sys.executable, str(project_root / "warehouse" / "run_dbt.py"),
         command, "--dag-id", dag_id, "--run-id", run_id],
        check=True,
        cwd=str(project_root),
        timeout=1900,
    )


with DAG(
    dag_id="bluebikes_trip_ingestion_dag",
    description="Monthly Bluebikes historical trip ingestion",
    start_date=datetime(2026, 10, 1, tzinfo=timezone.utc),
    schedule="0 6 10 * *",
    catchup=False,
    max_active_runs=1,
    default_args={
        "owner": "data-ingestion",
        "retries": 2,
        "retry_delay": timedelta(minutes=5),
    },
    tags=["bluebikes", "historical-trips", "ingestion"],
) as dag:
    ingest_monthly_trips = PythonOperator(
        task_id="ingest_monthly_trips",
        python_callable=ingest_trips,
    )
    source_freshness = PythonOperator(
        task_id="check_source_freshness",
        python_callable=run_dbt_step,
        op_kwargs={"command": "freshness", "dag_id": "{{ dag.dag_id }}", "run_id": "{{ run_id }}"},
        queue="dbt",
        pool="bluebikes_dbt_build",
    )
    build_warehouse = PythonOperator(
        task_id="build_warehouse",
        python_callable=run_dbt_step,
        op_kwargs={"command": "build", "dag_id": "{{ dag.dag_id }}", "run_id": "{{ run_id }}"},
        queue="dbt",
        pool="bluebikes_dbt_build",
        retries=0,
    )
    ingest_monthly_trips >> source_freshness >> build_warehouse
