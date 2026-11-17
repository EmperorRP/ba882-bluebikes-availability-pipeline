import importlib.util
import os
import re
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock, patch

from google.api_core.exceptions import NotFound


DAG_FILE = Path(__file__).resolve().parents[1] / "dags" / "bluebikes_ml_training_dag.py"
RUNNER = Path("/usr/local/airflow/ml/run_bqml.py")


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeClient:
    """Records submitted jobs; answers each query with the first matching canned result."""

    def __init__(self, answers=()):
        self.answers = list(answers)
        self.jobs = []

    def query(self, sql, job_config=None):
        self.jobs.append((sql, job_config))
        for pattern, answer in self.answers:
            if pattern in sql:
                if isinstance(answer, Exception):
                    raise answer
                return Mock(result=Mock(return_value=answer), job_id="job", total_bytes_billed=0)
        return Mock(result=Mock(return_value=[]), job_id="job", total_bytes_billed=0)


class MlTrainingDagTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = load(DAG_FILE, "bluebikes_ml_training_dag")
        cls.dag = cls.module.dag
        cls.runner = load(RUNNER, "bluebikes_run_bqml_test")

    def test_schedule_and_safety_settings(self):
        self.assertEqual(self.dag.schedule, "0 8 * * 1")
        self.assertFalse(self.dag.catchup)
        self.assertEqual(self.dag.max_active_runs, 1)
        self.assertTrue(self.dag.is_paused_upon_creation)
        self.assertFalse(self.dag.params["force_retrain"])

    def test_horizon_chains(self):
        gate = self.dag.get_task("check_for_new_labels")
        self.assertEqual(gate.downstream_task_ids, {f"h{h}.split" for h in (60, 180, 360, 1440)})
        for horizon, models in self.module.HORIZON_MODELS.items():
            with self.subTest(horizon=horizon):
                prefix = f"h{horizon}."
                train_ids = {prefix + f"train_{m}" for m in models}
                self.assertEqual(self.dag.get_task(prefix + "split").downstream_task_ids, train_ids)
                for task_id in train_ids:
                    task = self.dag.get_task(task_id)
                    self.assertEqual(task.downstream_task_ids, {prefix + "score"})
                    self.assertEqual(task.retries, 0)
                self.assertEqual(self.dag.get_task(prefix + "score").downstream_task_ids, {prefix + "metrics"})
                self.assertEqual(self.dag.get_task(prefix + "metrics").downstream_task_ids, {prefix + "evaluate"})
                self.assertEqual(self.dag.get_task(prefix + "evaluate").downstream_task_ids, {prefix + "publish"})
                self.assertEqual(self.dag.get_task(prefix + "publish").downstream_task_ids, {"publish_forecast_view"})
        boosted = {t for t in self.dag.task_ids if t.endswith("train_boosted")}
        self.assertEqual(boosted, {"h1440.train_boosted"})

    def test_dag_matches_runner_configuration(self):
        self.assertEqual(self.dag.get_task("publish_forecast_view").upstream_task_ids,
                         {f"h{h}.publish" for h in self.module.HORIZON_MODELS})
        self.assertEqual(self.module.HORIZON_MODELS,
                         {h: cfg["models"] for h, cfg in self.runner.HORIZONS.items()})
        self.assertEqual(self.module.TRAIN_STEPS, self.runner.TRAIN_STEPS)
        for step in self.runner.bqml.STEPS:
            self.assertIn(step, self.runner.MAX_GB_BILLED)

    def test_ml_code_loads_from_image_when_dag_is_bundled_elsewhere(self):
        self.module.__file__ = "/tmp/versioned-bundle/dags/bluebikes_ml_training_dag.py"
        with patch.dict(os.environ, {"AIRFLOW_HOME": "/usr/local/airflow"}):
            loaded = self.module.ml_module()
        self.assertEqual(Path(loaded.__file__), RUNNER)

    def test_force_retrain_skips_the_label_check(self):
        with patch.object(self.module, "ml_module") as ml_module:
            self.assertTrue(self.module.check_for_new_labels({"force_retrain": True}))
            ml_module.assert_not_called()
            ml_module.return_value.has_new_labels.return_value = False
            self.assertFalse(self.module.check_for_new_labels({"force_retrain": False}))

    def test_run_step_caps_bytes_and_labels_jobs(self):
        client = FakeClient()
        self.runner.run_step("03_train_boosted", 1440, run_id="scheduled__2026-11-23T08:00:00+00:00", client=client)
        sql, config = client.jobs[0]
        self.assertIn("create or replace model `ba882-bluebikes-pipeline.ml_models.boosted_h1440`", sql)
        self.assertEqual(config.maximum_bytes_billed, 30 * 10**9)
        self.assertEqual(config.labels["step"], "03_train_boosted")
        self.assertEqual(config.labels["horizon"], "1440")
        for value in config.labels.values():
            self.assertRegex(value, r"^[a-z0-9_-]{1,63}$")

    def test_scoring_only_uses_models_trained_for_the_horizon(self):
        client = FakeClient()
        self.runner.run_step("04_score", 60, client=client)
        sql = client.jobs[0][0]
        self.assertIn("logreg_h60", sql)
        self.assertNotIn("boosted", sql)
        client = FakeClient()
        self.runner.run_step("04_score", 1440, client=client)
        self.assertEqual(set(re.findall(r"ml_models\.(\w+_h1440)`, \(select", client.jobs[0][0])),
                         {"logreg_h1440", "boosted_h1440"})

    def test_publish_uses_each_horizons_primary_model(self):
        for horizon, model in ((60, "logreg"), (1440, "boosted")):
            client = FakeClient()
            self.runner.run_step("06_publish", horizon, client=client)
            sql = client.jobs[0][0]
            self.assertIn(f"`ba882-bluebikes-pipeline.ml_models.forecasts_h{horizon}`", sql)
            self.assertIn(f"where s.method = '{model}' and s.split = 'test'", sql)
        client = FakeClient()
        self.runner.run_step("07_forecast_view", None, client=client)
        sql, config = client.jobs[0]
        self.assertEqual(config.labels["horizon"], "all")
        self.assertEqual(re.findall(r"forecasts_h(\d+)`", sql), ["60", "180", "360", "1440"])

    def test_new_label_check(self):
        old = datetime(2026, 11, 8, 23, 50, tzinfo=timezone.utc)
        new = datetime(2026, 11, 15, 23, 50, tzinfo=timezone.utc)
        source = [{"horizon_minutes": h, "last_origin": old} for h in (60, 180, 360, 1440)]
        trained = [{"last_origin": old}]
        up_to_date = FakeClient([("group by 1", source), ("split_h", trained)])
        self.assertFalse(self.runner.has_new_labels(client=up_to_date))
        never_trained = FakeClient([("group by 1", source), ("split_h", NotFound("missing"))])
        self.assertTrue(self.runner.has_new_labels(client=never_trained))
        newer = [dict(row, last_origin=new) if row["horizon_minutes"] == 1440 else row for row in source]
        self.assertTrue(self.runner.has_new_labels(client=FakeClient([("group by 1", newer), ("split_h", trained)])))
        with self.assertRaises(RuntimeError):
            self.runner.has_new_labels(client=FakeClient([("group by 1", source[:3]), ("split_h", trained)]))

    def test_evaluation_records_history_and_requires_beating_persistence(self):
        def metrics(model_ap):
            return [{"method": "boosted", "average_precision": model_ap, "precision_at_k": 0.24},
                    {"method": "persistence", "average_precision": 0.095, "precision_at_k": 0.15}]

        client = FakeClient([("method in", metrics(0.23))])
        result = self.runner.record_and_check(1440, run_id="manual__x", client=client)
        self.assertEqual(result["model"], "boosted")
        self.assertIn("insert into `ba882-bluebikes-pipeline.ml_models.metrics_history`", client.jobs[0][0])
        with self.assertRaises(RuntimeError):
            self.runner.record_and_check(1440, client=FakeClient([("method in", metrics(0.09))]))
        with self.assertRaises(RuntimeError):
            self.runner.record_and_check(1440, client=FakeClient([("method in", metrics(0.23)[1:])]))


if __name__ == "__main__":
    unittest.main()
