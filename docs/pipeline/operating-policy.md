# Operating window and budget decision

## Confirmed on 2026-10-25

- The user approved one new **up-to-four-hour** Astro verification window for the dbt deployment. The actual override expiry was checked through the API and retained in the private audit; it has not been extended. The UI's next-event banner is not this manual override expiry. See the [public verification summary](evidence/verification-2026-10-25.md).
- The approved Data Editor-equivalent grants were applied and verified on `staging`, `intermediate`, `marts` and `ml` for the existing Astro workload identity, preserving prior access. The one-slot dbt pool was created; the scheduled cloud build succeeded. No credential keys or project-wide editor role were created.
- The normal enabled Astro schedule wakes Tuesday at `19:00 UTC` and hibernates at `23:00 UTC`. Its old free-text description about weekday midnight operation is inaccurate; cron expressions are authoritative. The normal schedule is not changed by this verification work.
- The Astro organization is on a student/trial arrangement. The API reports expiry `2027-02-28T05:00:00Z`; the user sees 126 trial days remaining. Neither establishes a dollar allowance or credit balance. Billing/credits are not visible in the user's current UI access.
- The GCP billing account name contains `QST843 $50 Fall26` and is shared with another project. Do not interpret its name as remaining funds, a BA882 allocation, or Astro credits. The Budget API is disabled; no budget API or new billable service was enabled for this task.

## Decision still required from the course/organization billing owner

Ask for the Astro allowance and remaining balance, expiry and overage behavior, whether resources stop when credits run out, the intended GCP funding source and shared credit balance, and the maximum approved ongoing spend/window. If the student's role cannot view Billing, request a balance confirmation from the owner rather than broad administrative access.

Until confirmed, do not convert the deployment to always-on, extend the override, add paid infrastructure, enable autoscaling beyond the existing limits, or assume student credits cover GCP. The existing wake policy resumes after the approved verification window; it is not an operating SLA.

## Proposed ongoing policy, not applied

After funding approval, choose a bounded continuous collection period with a recorded stop date, not unbounded operation. Continue five-minute raw station snapshots and daily forecast refresh. Run dbt daily and after monthly trips; use one build pool slot and zero idle workers. Review distinct label times/classes, collection gaps and freshness before extending the period. A week of data can be a useful first audit window but does not guarantee adequate ML evaluation coverage.

For a cost estimate, distinguish deployment awake-hours, worker usage, networking, BigQuery processing/storage and GCS storage/operations. Use measured billing/usage after the test; query byte caps and low worker minima do not cap the invoice. Hibernation stops Airflow execution, not charges for stored data. Do not reduce polling to weekly while claiming the existing intraday label contract is supported.

## Presentation wording

"Cloud ingestion and warehouse transformation were deployed and demonstrated during an approved time-limited window. Ongoing availability is budget-gated. Live station observations missed during sleep cannot be backfilled; our current collection coverage and training readiness are reported separately."

[dbt orchestration](dbt-orchestration.md) · [Current pipeline status](pipeline-status.md)
