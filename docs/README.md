# Project documentation

Start with the [pipeline status and integration guide](pipeline/pipeline-status.md) for how the workstreams fit together, deployment gates, and next steps.

For the Phase 1 data-model presentation, use the [table relationships, keys, grains and dbt lineage](architecture/data-model.md).

The [Phase 1 evidence map](presentation/README.md) connects the business problem, team roles, workflows and AI-assisted validation to the later presentation.

The [October 25 public verification summary](pipeline/evidence/verification-2026-10-25.md) covers the scheduled dbt build, aggregate warehouse coverage and operating limitations. Detailed audits and original screenshots remain local at the user's request.

| Area | Contents |
| --- | --- |
| [dbt and warehouse](dbt/README.md) | Setup, model contracts, handoff, audits, work log, and verification evidence |
| [Pipeline and operations](pipeline/README.md) | Running pipeline status, scheduling, deployment, and operational runbook |
| [Ingestion](ingestion/README.md) | Data sources and ingestion implementation references |
| [Architecture](architecture/README.md) | Business problem, system design, data model, and project boundaries |

## Keeping this organized

Keep new documents in the relevant area rather than the top-level docs folder. Put dbt model contracts in [dbt/contracts](dbt/contracts/README.md) and validation artifacts in [dbt/evidence](dbt/evidence/README.md). Link new documents from the relevant area index.

Dated handoffs, audits, and verification records describe the state at the time they were written; use the pipeline status guide for ongoing coordination. Evidence JSON files are preserved unchanged, including paths and hashes recorded under the original repository layout.
