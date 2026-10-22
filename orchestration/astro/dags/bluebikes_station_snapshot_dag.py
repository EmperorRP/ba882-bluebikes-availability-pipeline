
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
import subprocess

from airflow.sdk import DAG
from airflow.providers.standard.operators.python import PythonOperator


def run_gbfs_ingestion():
    project_root = Path(os.environ.get("AIRFLOW_HOME", "/usr/local/airflow"))
    script = project_root / "ingestion" / "gbfs_ingestion.py"

    subprocess.run(
        [sys.executable, str(script)],
        check=True,
        cwd=str(project_root),
        timeout=600,
    )


with DAG(
    dag_id="bluebikes_station_snapshot_dag",
    description="Collect Bluebikes GBFS snapshots every 5 minutes for availability labels",
    start_date=datetime(2026, 10, 17, tzinfo=timezone.utc),
    schedule="*/5 * * * *",
    catchup=False,
    max_active_runs=1,
    default_args={
        "owner": "data-ingestion",
        "retries": 2,
        "retry_delay": timedelta(minutes=5),
    },
    tags=["bluebikes", "ingestion", "gbfs"],
) as dag:

    collect_gbfs = PythonOperator(
        task_id="collect_gbfs_snapshot",
        python_callable=run_gbfs_ingestion,
    )
