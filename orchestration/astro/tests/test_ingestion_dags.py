import importlib.util
import os
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from airflow.models.dagbag import DagBag


DAG_FOLDER = Path(__file__).resolve().parents[1] / "dags"


def load_dag_module(filename):
    spec = importlib.util.spec_from_file_location(filename, DAG_FOLDER / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class IngestionDagTests(unittest.TestCase):
    def test_runtime_imports_and_deployed_schedules(self):
        dag_bag = DagBag(dag_folder=str(DAG_FOLDER), include_examples=False)
        self.assertEqual(dag_bag.import_errors, {})
        expected_schedules = {
            "bluebikes_station_snapshot_dag": "*/5 * * * *",
            "bluebikes_trip_ingestion_dag": "0 6 10 * *",
            "weather_ingestion_dag": "0 6 * * *",
        }
        self.assertEqual(set(dag_bag.dags), set(expected_schedules))
        for dag_id, schedule in expected_schedules.items():
            with self.subTest(dag_id=dag_id):
                dag = dag_bag.dags[dag_id]
                self.assertEqual(dag.schedule, schedule)
                self.assertEqual(str(dag.timezone), "UTC")
                self.assertFalse(dag.catchup)
                self.assertEqual(dag.max_active_runs, 1)

    def test_ingestion_uses_image_path_when_dag_is_bundled_elsewhere(self):
        cases = (
            ("bluebikes_station_snapshot_dag.py", "run_gbfs_ingestion", "gbfs_ingestion.py"),
            ("weather_ingestion_dag.py", "run_weather_ingestion", "weather_ingestion.py"),
        )
        for filename, callable_name, script_name in cases:
            with self.subTest(filename=filename):
                module = load_dag_module(filename)
                module.__file__ = "/tmp/versioned-bundle/dags/" + filename
                with patch.dict(os.environ, {"AIRFLOW_HOME": "/usr/local/airflow"}):
                    with patch.object(module.subprocess, "run") as run:
                        getattr(module, callable_name)()
                self.assertEqual(run.call_args.args[0], [
                    sys.executable, "/usr/local/airflow/ingestion/" + script_name,
                ])
                self.assertTrue(Path(run.call_args.args[0][1]).is_file())
                self.assertEqual(run.call_args.kwargs["cwd"], "/usr/local/airflow")
                self.assertTrue(run.call_args.kwargs["check"])

    def test_trip_retries_use_scheduled_month_across_year_boundary(self):
        module = load_dag_module("bluebikes_trip_ingestion_dag.py")
        with patch.dict(os.environ, {"AIRFLOW_HOME": "/usr/local/airflow"}):
            with patch.object(module.subprocess, "run") as run:
                module.ingest_trips(datetime(2026, 1, 10, 6, tzinfo=timezone.utc))
        self.assertEqual(run.call_args.kwargs["env"]["TRIP_MONTH"], "202512")
        self.assertEqual(run.call_args.args[0][1], "/usr/local/airflow/ingestion/historical_trips.py")
        self.assertTrue(Path(run.call_args.args[0][1]).is_file())

    def test_five_minute_polling_supplies_reports_inside_label_window(self):
        origin = datetime(2026, 10, 22, 12, 0, 5, tzinfo=timezone.utc)
        for horizon_hours in (1, 3, 6, 24):
            with self.subTest(horizon_hours=horizon_hours):
                target = origin + timedelta(hours=horizon_hours)
                reports = [
                    target + timedelta(minutes=offset, seconds=-30)
                    for offset in (0, 5, 10, 15)
                ]
                labels = [report for report in reports if target <= report <= target + timedelta(minutes=15)]
                self.assertEqual(len(labels), 3)
                half_hour_reports = [reports[0], target + timedelta(minutes=30, seconds=-30)]
                self.assertFalse(any(target <= report <= target + timedelta(minutes=15) for report in half_hour_reports))

    def test_dbt_follows_successful_weather_and_trip_loads(self):
        cases = (
            ("weather_ingestion_dag.py", "ingest_weather_data"),
            ("bluebikes_trip_ingestion_dag.py", "ingest_monthly_trips"),
        )
        for filename, ingestion_task in cases:
            with self.subTest(filename=filename):
                module = load_dag_module(filename)
                dag = module.dag
                self.assertEqual(dag.get_task(ingestion_task).downstream_task_ids, {"check_source_freshness"})
                self.assertEqual(dag.get_task("check_source_freshness").downstream_task_ids, {"build_warehouse"})
                for task_id in ("check_source_freshness", "build_warehouse"):
                    task = dag.get_task(task_id)
                    self.assertEqual(task.queue, "dbt")
                    self.assertEqual(task.pool, "bluebikes_dbt_build")
                    self.assertEqual(task.trigger_rule, "all_success")
                self.assertEqual(dag.get_task("build_warehouse").retries, 0)

    def test_dbt_task_uses_bundled_safe_argument_list(self):
        for filename in ("weather_ingestion_dag.py", "bluebikes_trip_ingestion_dag.py"):
            with self.subTest(filename=filename):
                module = load_dag_module(filename)
                with patch.dict(os.environ, {"AIRFLOW_HOME": "/usr/local/airflow"}):
                    with patch.object(module.subprocess, "run") as run:
                        module.run_dbt_step("build", "test_dag", "manual__run;not-a-shell-command")
                self.assertEqual(run.call_args.args[0], [
                    sys.executable, "/usr/local/airflow/warehouse/run_dbt.py", "build",
                    "--dag-id", "test_dag", "--run-id", "manual__run;not-a-shell-command",
                ])
                self.assertTrue(Path(run.call_args.args[0][1]).is_file())
                self.assertTrue(run.call_args.kwargs["check"])

    def test_snapshot_dag_does_not_rebuild_warehouse_every_five_minutes(self):
        module = load_dag_module("bluebikes_station_snapshot_dag.py")
        self.assertEqual(set(module.dag.task_ids), {"collect_gbfs_snapshot"})


if __name__ == "__main__":
    unittest.main()
