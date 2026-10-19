import os
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

from airflow import DAG
from airflow.operators.python import PythonOperator


def ingest_trips():
    project_root = Path(__file__).resolve().parents[1]
    script = project_root / "ingestion" / "historical_trips.py"

    # Collect last month's completed trip data
    today = datetime.now()
    last_month = today.replace(day=1) - timedelta(days=1)
    trip_month = last_month.strftime("%Y%m")

    subprocess.run(
        ["python", str(script)],
        cwd=str(project_root),
        env={**os.environ, "TRIP_MONTH": trip_month},
        check=True,
        timeout=1800,
    )


with DAG(
    dag_id="bluebikes_trip_ingestion_dag",
    description="Monthly Bluebikes historical trip ingestion",
    start_date=datetime(2026, 10, 1),
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
