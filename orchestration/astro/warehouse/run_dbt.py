import argparse
import json
import logging
import os
import subprocess
import tempfile
import uuid
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from google.cloud import storage


AIRFLOW_HOME = Path(os.environ.get("AIRFLOW_HOME", "/usr/local/airflow"))
PROJECT = "ba882-bluebikes-pipeline"
BUCKET = "ba882-bluebikes-pipeline-raw"
COMMANDS = {"freshness": ["source", "freshness"], "build": ["build", "--fail-fast"]}


def summarize_artifact(path):
    if not path.is_file():
        return {"artifact_present": False, "counts": {}, "results": []}
    artifact = json.loads(path.read_text())
    results = []
    for result in artifact.get("results", []):
        node = result.get("node", {})
        results.append({
            "unique_id": result.get("unique_id", node.get("unique_id")),
            "status": result.get("status"),
            "execution_time": result.get("execution_time"),
            "max_loaded_at": result.get("max_loaded_at"),
            "snapshotted_at": result.get("snapshotted_at"),
            "max_loaded_at_time_ago_in_s": result.get("max_loaded_at_time_ago_in_s"),
        })
    metadata = artifact.get("metadata", {})
    return {
        "artifact_present": True,
        "dbt_version": metadata.get("dbt_version"),
        "invocation_id": metadata.get("invocation_id"),
        "counts": dict(Counter(result["status"] for result in results)),
        "results": results,
    }


def publish_summary(summary):
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    object_name = f"dbt-runs/{timestamp}/{uuid.uuid4().hex}/{summary['command']}.json"
    client = storage.Client(project=PROJECT)
    client.bucket(BUCKET).blob(object_name).upload_from_string(
        json.dumps(summary, indent=2),
        content_type="application/json",
        if_generation_match=0,
    )
    uri = f"gs://{BUCKET}/{object_name}"
    logging.info("dbt evidence: %s", uri)
    return uri


def execute_step(command, dag_id, run_id, dbt_executable=None):
    if command not in COMMANDS:
        raise ValueError(f"Unsupported dbt step: {command}")
    executable = Path(dbt_executable or AIRFLOW_HOME / "dbt-venv" / "bin" / "dbt")
    if not executable.is_file():
        raise FileNotFoundError(f"Missing isolated dbt executable: {executable}")
    with tempfile.TemporaryDirectory(prefix="bluebikes-dbt-") as directory:
        target_path = Path(directory) / "target"
        arguments = [
            str(executable), "--log-path", str(Path(directory) / "logs"),
            *COMMANDS[command],
            "--project-dir", str(AIRFLOW_HOME / "dbt"),
            "--profiles-dir", str(AIRFLOW_HOME / "warehouse" / "profiles"),
            "--target-path", str(target_path),
        ]
        environment = {**os.environ, "DBT_SEND_ANONYMOUS_USAGE_STATS": "false"}
        timed_out = False
        try:
            result = subprocess.run(arguments, env=environment, check=False, timeout=1800)
            return_code = result.returncode
        except subprocess.TimeoutExpired:
            return_code = 124
            timed_out = True
        artifact_name = "sources.json" if command == "freshness" else "run_results.json"
        artifact_summary = summarize_artifact(target_path / artifact_name)
        summary = {
            "captured_at_utc": datetime.now(timezone.utc).isoformat(),
            "project": PROJECT,
            "profile_target": "astro",
            "dataset": "staging",
            "location": "US",
            "command": command,
            "dag_id": dag_id,
            "airflow_run_id": run_id,
            "code_revision": os.environ.get("BLUEBIKES_CODE_REVISION", "unknown"),
            "return_code": return_code,
            "timed_out": timed_out,
            **artifact_summary,
        }
        uri = publish_summary(summary)
        failed_statuses = {"error", "fail", "runtime error"}
        failed_results = failed_statuses.intersection(artifact_summary["counts"])
        if return_code or failed_results or not artifact_summary["results"]:
            raise RuntimeError(f"dbt {command} failed or produced no results; evidence: {uri}")
        logging.info("dbt %s result counts: %s", command, summary["counts"])
        return uri


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=COMMANDS)
    parser.add_argument("--dag-id", required=True)
    parser.add_argument("--run-id", required=True)
    arguments = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    execute_step(arguments.command, arguments.dag_id, arguments.run_id)


if __name__ == "__main__":
    main()
