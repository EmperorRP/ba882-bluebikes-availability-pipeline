# Phase 1 presentation preparation

This is an evidence map and outline for the later presentation, not a finished slide deck or submission. Deliver the final deck and <=3-page writeup as PDFs or shared Google files. The presentation is approximately ten minutes plus questions.

## Narrative and supporting material

| Topic | What to explain/show | Evidence |
| --- | --- | --- |
| Business problem | Riders need a bike at a future time; operators need rebalancing insight | [Problem and MVP proposal](../architecture/README.md) |
| What we are building | Raw sources -> warehouse analytics -> defensible availability prediction -> app | [Integration guide](../pipeline/pipeline-status.md) |
| Team responsibilities | Separate ingestion, warehouse, ML, app and integration work; show review/integration boundaries | Role summary below and [dbt handoff](../dbt/dbt-handoff-2026-10-21.md) |
| Data model | Station/date dimensions, hourly flows, observed inventory, as-of features and nullable labels | [Relationship diagrams, grains and keys](../architecture/data-model.md) |
| Deployed workflow | Five-minute snapshots; daily weather and monthly trips followed by freshness and dbt | [Orchestration](../pipeline/dbt-orchestration.md), actual Astro Graph/Grid/run IDs and logs |
| Input/output validation | Raw batches/timestamps, source freshness, model/test results, label coverage and known warnings | Dated cloud evidence and [independent October 22 review](../dbt/polling-label-review-2026-10-22.md) |
| AI collaboration | CLI access, code/document review, explicit approvals, testing and independent output checks | AI workflow below; GitHub PRs and cloud evidence |
| Look ahead | Cloud reporting, bounded collection, chronological ML evaluation and clearly labelled prediction/proxy scope | [Operating policy](../pipeline/operating-policy.md) and coverage audit |

## Team responsibility summary

Reported responsibility areas, not new GitHub assignee changes. Confirm the final wording with the team.

| Contributor | Primary workstream |
| --- | --- |
| Erica | Source ingestion and the original ingestion DAGs |
| Marcus | BigQuery/dbt models, data contracts, tests and handoff |
| Danish | ML target, features, split/evaluation policy and training |
| George / Xingchen Ding | Analytics application/dashboard and consumer contract |
| Rahul | Integration, cloud deployment/access coordination, review and presentation coordination |

## How we used AI, with verification boundaries

1. Connect existing local `astro`/`gcloud` authentication and the GitHub connection without copying keys into the repository or chat.
2. Inspect source code and PRs before changing them; reconcile conflicts through reviewed branches/PRs, not destructive replacement.
3. Generate and maintain README/runbook material, Mermaid relationships and grain/key documentation grounded in the actual model SQL/YAML.
4. Identify risks such as collection cadence versus label-window mismatch, timestamp semantics, forecast-version leakage, missing IAM and dependency conflicts.
5. Test in the real Astro container, keep dbt dependencies isolated, run credential-free parse and authenticated build checks, and inspect warehouse outputs rather than trusting generated explanations.
6. Require human approval for paid runtime and security-sensitive access. Keep the unconfirmed ongoing budget decision explicit.

AI assists implementation and review; runtime tests, cloud job IDs and warehouse audits provide the evidence. Passing synthetic tests does not prove sufficient real training data or model accuracy. Human contributors remain accountable for scope, approvals and interpretation.

## Demo evidence checklist

- Public repository link and reviewed commit/PR links.
- Astro image/bundle version, wake expiry and actual DAG run IDs.
- Station snapshot Grid view showing repeated scheduled collections.
- Weather/trip Graph view showing ingestion -> source freshness -> warehouse build.
- Task log lines with dbt result counts and immutable GCS evidence URIs.
- Raw latest ingestion/source-report timestamps, shared mart update times and current horizon coverage.
- Known warnings, downtime/collection limitations, and planned versus delivered analytics.
- A backup recording/screenshots and PDF diagrams so presentation success does not depend on keeping compute awake.

[Documentation index](../README.md)
