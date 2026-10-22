import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
import subprocess

from airflow.sdk import DAG
from airflow.providers.standard.operators.python import PythonOperator


def run_weather_ingestion():
    project_root = Path(os.environ.get("AIRFLOW_HOME", "/usr/local/airflow"))
    script = project_root / "ingestion" / "weather_ingestion.py"

    subprocess.run(
        [sys.executable, str(script)],
        check=True,
        cwd=str(project_root),
        timeout=1800,
    )


with DAG(
    dag_id="weather_ingestion_dag",
    description="Collect Boston historical and forecast weather",
    start_date=datetime(2026, 10, 19, tzinfo=timezone.utc),
    schedule="0 6 * * *",
    catchup=False,
    max_active_runs=1,
    default_args={
        "owner": "data-ingestion",
        "retries": 2,
        "retry_delay": timedelta(minutes=5),
    },
    tags=["weather", "ingestion", "open-meteo"],
) as dag:
    ingest_weather = PythonOperator(
        task_id="ingest_weather_data",
        python_callable=run_weather_ingestion,
    )
