# Runbook

## Shared deployment

For the new isolated dbt image, build from the repository root using the named dbt context and deploy the prebuilt image. See [dbt orchestration](dbt-orchestration.md) for the authoritative commands, required pool and scoped permissions. The older build commands below describe the ingestion-only image and do not include dbt. See [operating policy](operating-policy.md) before waking the deployment.

- GCP project: `ba882-bluebikes-pipeline`; BigQuery location: `US`.
- Astro workspace: `BA882 Team Workspace` (`cmfsgoajd1rsx01pdcza2kkcw`).
- Astro deployment: `BA882 Team Project` (`cmv1byju444do01pl0bhotk1f`).
- Runtime: `3.3-9`, based on Airflow `3.3.2`.
- Workload identity: `astro-classical-level-9533@astro-us-central1-0001.iam.gserviceaccount.com`.
- The deployment was hibernating at inspection on 2026-10-22. Inspect it again before assuming it is collecting data.

## Local Google access

Use the team-authorized Google account in each browser login:

```powershell
gcloud auth login
gcloud auth application-default login
gcloud config set project ba882-bluebikes-pipeline
gcloud auth application-default set-quota-project ba882-bluebikes-pipeline
```

The CLI login serves `gcloud` and `bq`; Application Default Credentials serve Python/dbt. Cloud execution uses Astro's workload identity instead of a local login or a downloaded service-account key.

## Ingestion identity permissions

Grant this workload identity only the following ingestion permissions, preserving existing IAM entries:

| Resource | Role | Reason |
| --- | --- | --- |
| Project `ba882-bluebikes-pipeline` | `roles/bigquery.jobUser` | Submit BigQuery load/query jobs. |
| Dataset `raw` | `roles/bigquery.dataEditor` | Load/merge raw tables and create/delete temporary ingestion tables. |
| Bucket `ba882-bluebikes-pipeline-raw` | `roles/storage.objectCreator` | Append immutable source objects; overwrites are not required. |

This does not grant access to write staging, marts, intermediate, or ML datasets. Add the dbt runtime identity and its dataset permissions separately when integrating PR #15.

## Build, validate, and deploy

Start Docker Desktop, authenticate with `astro login`, and run from `orchestration/astro` in the reviewed checkout:

```powershell
docker build -t bluebikes-ingestion-verified .
docker run --rm --entrypoint python --volume "${PWD}/dags:/usr/local/airflow/dags:ro" --volume "${PWD}/tests:/usr/local/airflow/tests:ro" bluebikes-ingestion-verified -m unittest discover -s /usr/local/airflow/tests -v
astro deployment inspect cmv1byju444do01pl0bhotk1f --show-workload-identity
astro deployment wake-up cmv1byju444do01pl0bhotk1f --for 4h
astro deploy cmv1byju444do01pl0bhotk1f --image-name bluebikes-ingestion-verified --wait
```

On Windows, if the image push selects WSL's unavailable `/bin/bash`, prepend the installed Git Bash directory for the deployment command only:

```powershell
$env:PATH = 'C:\Program Files\Git\bin;' + $env:PATH
```

The default generated Astro integrity-test file was absent in the original project. Use the checked-in runtime tests above as deployment evidence; do not treat the CLI's skipped default test as a successful import check. CI also runs dependency consistency checks. The Google client dependencies require `opentelemetry-api==1.42.1` for compatibility with Runtime 3.3-9's existing SDK; removing that constraint caused Airflow to fail during import in the first runtime CI run.

The four-hour wake period is for integration testing. It does not establish sustained collection. Agree an ongoing awake period with the course deployment administrator and its billing owner before claiming continuous ingestion. The current Tuesday-only wake schedule cannot support the collection contract.

The image copies ingestion code into `/usr/local/airflow/ingestion`; tasks resolve it using `AIRFLOW_HOME`, independently of the versioned DAG bundle path. A DAG-only deployment cannot ship ingestion Python or dependency changes; deploy the image when either changes. Runtime tests mock task subprocesses and do not load cloud data.

## Scheduling contract

- GBFS: every five minutes, UTC, no catchup, one active run. This provides collection opportunities within the dbt 15-minute post-target label window despite ordinary report lag. Monitor task duration/retries: the declared cadence alone does not guarantee usable outcomes.
- Weather: daily at 06:00 UTC, matching the dbt 36-hour warning / 48-hour error policy. This initial job also refreshes historical weather; splitting archival backfill into a separate bounded workflow is a follow-up optimization.
- Trips: monthly on day 10 at 06:00 UTC. The archive month derives from the run's data interval end so retries/backfills keep the original month.
- dbt: pending integration of PR #15. These DAGs do not run dbt or train models yet.

Keep the current raw trip timestamp meaning until an ingestion/staging migration is coordinated. PR #15 interprets the stored CSV clock as America/New_York; converting raw rows to true UTC independently would shift times twice.

## Acceptance and rollback

1. Record the deployment image/version and reviewed Git commit.
2. Verify zero DAG import errors and that all three DAGs appear in Airflow.
3. Check the trip run's calculated month before triggering a manual historical load; unpause DAGs only after identity/configuration checks.
4. Observe successful GBFS collections across multiple scheduled intervals; compare raw ingestion times and source `last_reported` times.
5. Observe a successful weather run with a new versioned forecast batch.
6. After dbt integration, run `dbt build` and `dbt source freshness` separately. Inspect `ml.availability_sample_coverage` by horizon; passing model tests does not establish sufficient labels.
7. Confirm failure notifications reach a team-owned destination. Preserve the existing instructor alert address unless the administrator approves a change.

If a deployed change fails, pause the affected DAG and deploy the last known-good image and DAG revision. Preserve raw source objects and tables for replay. Record the failed run, error, image/commit and recovery in `pipeline-status.md`. Never include credentials in documentation or logs.
