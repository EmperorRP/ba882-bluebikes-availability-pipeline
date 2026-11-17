"""Execute the BigQuery ML steps in ml/sql/ against BigQuery.

bqml.py renders the SQL. This module runs it: once per step, with a bytes-billed cap and job
labels so each run's cost can be traced in INFORMATION_SCHEMA.JOBS. The Airflow DAG
(orchestration/astro/dags/bluebikes_ml_training_dag.py) calls these functions, and they can also be
run by hand with Application Default Credentials:

    python ml/run_bqml.py 01_split --horizon-minutes 1440
"""
from __future__ import annotations

import argparse
import logging
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bqml  # noqa: E402

LOCATION = "US"
GB = 1_000_000_000

# Which models are trained for each horizon, and which one must beat persistence (see ml/README.md).
# Boosted trees are only trained for the primary 24 h horizon: they bill ~70x more than
# logistic regression, which was the best model at 1/3/6 h.
HORIZONS = {
    60: {"models": ("logreg",), "primary": "logreg"},
    180: {"models": ("logreg",), "primary": "logreg"},
    360: {"models": ("logreg",), "primary": "logreg"},
    1440: {"models": ("logreg", "boosted"), "primary": "boosted"},
}
TRAIN_STEPS = {"logreg": "02_train_logreg", "boosted": "03_train_boosted"}

# Per-job ceiling on bytes billed. BigQuery refuses a job that would bill more than the cap, so a
# runaway query fails before it is charged. Observed costs (2026-11-13): 24 h boosted ~14 GB,
# logreg ~0.2 GB.
MAX_GB_BILLED = {
    "01_split": 25,
    "02_train_logreg": 5,
    "03_train_boosted": 30,
    "04_score": 25,
    "05_metrics": 10,
    "06_publish": 5,
    "07_forecast_view": 1,
    "check": 2,
    "evaluate": 2,
}

BASELINE = "persistence"


def _client():
    from google.cloud import bigquery

    return bigquery.Client(project=bqml.DEFAULTS["project"], location=LOCATION)


def _label(value: object) -> str:
    """BigQuery label values: lowercase letters, digits, '_' and '-', at most 63 characters."""
    return re.sub(r"[^a-z0-9_-]", "_", str(value).lower())[:63]


def _run(sql: str, kind: str, labels: dict, params: list | None = None, client=None):
    from google.cloud import bigquery

    client = client or _client()
    config = bigquery.QueryJobConfig(
        maximum_bytes_billed=MAX_GB_BILLED[kind] * GB,
        labels={"pipeline": "bluebikes-ml", "step": _label(kind),
                **{k: _label(v) for k, v in labels.items()}},
        query_parameters=params or [],
    )
    job = client.query(sql, job_config=config)
    rows = list(job.result())
    logging.info("%s %s: job %s billed %.3f GB", kind, labels, job.job_id,
                 (job.total_bytes_billed or 0) / GB)
    return rows


def run_step(step: str, horizon_minutes: int | None, run_id: str = "manual", client=None) -> int:
    """Render one ml/sql step for a horizon, run it, and log its final result set.

    horizon_minutes is None for steps that cover every horizon (07_forecast_view)."""
    if horizon_minutes is None:
        sql = bqml.render(step, horizons=",".join(str(h) for h in HORIZONS))
    else:
        config = HORIZONS[int(horizon_minutes)]
        sql = bqml.render(step, horizon_minutes=horizon_minutes, models=",".join(config["models"]),
                          primary_model=config["primary"])
    rows = _run(sql, step, {"horizon": horizon_minutes or "all", "airflow_run": run_id}, client=client)
    for row in rows[:50]:
        logging.info("  %s", dict(row.items()))
    return len(rows)


def has_new_labels(horizons=HORIZONS, client=None) -> bool:
    """True when any horizon has labelled origins newer than its last split (or was never split).

    Retraining on unchanged data would bill the same ~14 GB boosted-tree run for an identical model.
    """
    from google.api_core.exceptions import NotFound

    client = client or _client()
    p, d = bqml.DEFAULTS["project"], bqml.DEFAULTS["dataset"]
    source = {row["horizon_minutes"]: row["last_origin"] for row in _run(
        f"select horizon_minutes, max(prediction_at_utc) as last_origin "
        f"from `{p}.{bqml.DEFAULTS['source']}` group by 1", "check", {}, client=client)}
    new = False
    for horizon in horizons:
        try:
            trained = _run(f"select max(prediction_at_utc) as last_origin from `{p}.{d}.split_h{horizon}`",
                           "check", {"horizon": horizon}, client=client)[0]["last_origin"]
        except NotFound:
            trained = None
        latest = source.get(horizon)
        logging.info("horizon %s: latest labelled origin %s, last trained on %s", horizon, latest, trained)
        if latest is None:
            raise RuntimeError(f"No labelled rows for horizon {horizon} in {bqml.DEFAULTS['source']}")
        new = new or trained is None or latest > trained
    return new


def record_and_check(horizon_minutes: int, run_id: str = "manual", client=None) -> dict:
    """Append this run's metrics to ml_models.metrics_history, then fail unless the horizon's primary
    model beats the persistence baseline on test average precision."""
    from google.cloud import bigquery

    client = client or _client()
    horizon = int(horizon_minutes)
    primary = HORIZONS[horizon]["primary"]
    p, d = bqml.DEFAULTS["project"], bqml.DEFAULTS["dataset"]
    metrics = f"`{p}.{d}.metrics_h{horizon}`"
    history = f"`{p}.{d}.metrics_history`"
    labels = {"horizon": horizon, "airflow_run": run_id}
    params = [
        bigquery.ScalarQueryParameter("run_id", "STRING", run_id),
        bigquery.ScalarQueryParameter("revision", "STRING", os.environ.get("BLUEBIKES_CODE_REVISION", "unknown")),
    ]
    _run(f"""
create table if not exists {history} as
select m.*, '' as airflow_run_id, '' as code_revision from {metrics} m limit 0;
insert into {history}
select m.*, @run_id, @revision from {metrics} m;
""", "evaluate", labels, params, client)

    rows = _run(f"select method, average_precision, precision_at_k from {metrics} "
                f"where split = 'test' and method in ('{primary}', '{BASELINE}')", "evaluate", labels, client=client)
    scores = {row["method"]: row for row in rows}
    if primary not in scores or BASELINE not in scores:
        raise RuntimeError(f"metrics_h{horizon} is missing test rows for {primary} or {BASELINE}")
    model_ap, baseline_ap = scores[primary]["average_precision"], scores[BASELINE]["average_precision"]
    result = {"horizon_minutes": horizon, "model": primary, "test_average_precision": model_ap,
              "persistence_average_precision": baseline_ap,
              "test_precision_at_k": scores[primary]["precision_at_k"]}
    logging.info("evaluation: %s", result)
    if model_ap is None or baseline_ap is None or model_ap <= baseline_ap:
        raise RuntimeError(f"{primary}_h{horizon} does not beat persistence on test average precision: {result}")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("step", choices=[*bqml.STEPS, "check", "evaluate"])
    parser.add_argument("--horizon-minutes", type=int, choices=sorted(HORIZONS), default=1440)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    if args.step == "check":
        print(has_new_labels())
    elif args.step == "evaluate":
        print(record_and_check(args.horizon_minutes))
    elif args.step == "07_forecast_view":
        run_step(args.step, None)
    else:
        run_step(args.step, args.horizon_minutes)


if __name__ == "__main__":
    main()
