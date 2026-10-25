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
    ingest_weather >> source_freshness >> build_warehouse
