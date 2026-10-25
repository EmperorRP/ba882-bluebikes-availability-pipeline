import importlib.util
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch


RUNNER = Path("/usr/local/airflow/warehouse/run_dbt.py")
specification = importlib.util.spec_from_file_location("bluebikes_dbt_runner", RUNNER)
runner = importlib.util.module_from_spec(specification)
specification.loader.exec_module(runner)


class DbtRunnerTests(unittest.TestCase):
    def execute(self, command, return_code=0, statuses=None, timeout=False, artifact=True):
        statuses = statuses or ["success", "pass", "warn"]

        def run(arguments, **kwargs):
            if timeout:
                raise subprocess.TimeoutExpired(arguments, 1800)
            if artifact:
                target = Path(arguments[arguments.index("--target-path") + 1])
                target.mkdir(parents=True)
                filename = "sources.json" if command == "freshness" else "run_results.json"
                results = [{"unique_id": f"test.{index}", "status": status} for index, status in enumerate(statuses)]
                (target / filename).write_text(json.dumps({"metadata": {"dbt_version": "test"}, "results": results}))
            return Mock(returncode=return_code)

        with tempfile.TemporaryDirectory() as directory:
            executable = Path(directory) / "dbt"
            executable.touch()
            with patch.object(runner.subprocess, "run", side_effect=run) as process:
                with patch.object(runner, "publish_summary", return_value="gs://test/evidence.json") as publish:
                    outcome = None
                    try:
                        runner.execute_step(command, "test_dag", "test_run", executable)
                    except RuntimeError as error:
                        outcome = error
                    return outcome, process.call_args, publish.call_args.args[0]

    def test_build_preserves_warnings_and_uses_isolated_profile(self):
        error, call, summary = self.execute("build")
        self.assertIsNone(error)
        self.assertIn("--fail-fast", call.args[0])
        self.assertEqual(summary["counts"], {"success": 1, "pass": 1, "warn": 1})
        self.assertEqual(summary["airflow_run_id"], "test_run")
        self.assertEqual(summary["dataset"], "staging")
        self.assertFalse(call.kwargs["check"])
        self.assertEqual(call.kwargs["env"]["DBT_SEND_ANONYMOUS_USAGE_STATS"], "false")

    def test_freshness_error_is_not_a_successful_build(self):
        error, call, summary = self.execute("freshness", return_code=1, statuses=["pass", "error"])
        self.assertIsInstance(error, RuntimeError)
        self.assertIn("source", call.args[0])
        self.assertIn("freshness", call.args[0])
        self.assertEqual(summary["return_code"], 1)
        self.assertEqual(summary["counts"]["error"], 1)

    def test_error_artifact_fails_even_if_process_returns_zero(self):
        error, _, _ = self.execute("build", statuses=["error"])
        self.assertIsInstance(error, RuntimeError)

    def test_missing_artifact_fails_even_if_process_returns_zero(self):
        error, _, summary = self.execute("build", artifact=False)
        self.assertIsInstance(error, RuntimeError)
        self.assertFalse(summary["artifact_present"])

    def test_timeout_is_recorded_before_failure(self):
        error, _, summary = self.execute("build", timeout=True)
        self.assertIsInstance(error, RuntimeError)
        self.assertTrue(summary["timed_out"])
        self.assertEqual(summary["return_code"], 124)

    def test_only_supported_steps_can_run(self):
        with self.assertRaises(ValueError):
            runner.execute_step("run-operation", "test", "test")

    def test_summary_upload_is_immutable(self):
        with patch.object(runner.storage, "Client") as client:
            uri = runner.publish_summary({"command": "build", "counts": {"pass": 1}})
        upload = client.return_value.bucket.return_value.blob.return_value.upload_from_string
        self.assertEqual(upload.call_args.kwargs["if_generation_match"], 0)
        self.assertTrue(uri.startswith("gs://ba882-bluebikes-pipeline-raw/dbt-runs/"))


if __name__ == "__main__":
    unittest.main()
