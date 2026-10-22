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
    PythonOperator(
        task_id="ingest_monthly_trips",
        python_callable=ingest_trips,
    )
