
from datetime import datetime, timedelta
from pathlib import Path
import subprocess

from airflow import DAG
from airflow.operators.python import PythonOperator


def run_gbfs_ingestion():
    # Find the project root from the DAG file
    project_root = Path(__file__).resolve().parents[2]
    script = project_root / "ingestion" / "gbfs_ingestion.py"

    subprocess.run(
        ["python", str(script)],
        check=True,
        cwd=str(project_root),
        timeout=600,
    )


with DAG(
    dag_id="bluebikes_station_snapshot_dag",
    description="Collect Bluebikes GBFS snapshots every 30 minutes",
    start_date=datetime(2026, 10, 17),
    schedule="*/30 * * * *",
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
