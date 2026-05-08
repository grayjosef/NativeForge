# NativeForge source activation command dry-run (v1)

## Purpose

The activation command dry-run (`schema_version: nf_source_activation_command_dry_run_v1`) is a **deterministic, JSON-serializable packet** that consumes **`nf_discovery_source_quality_v1`** and Sprint 41 **`nf_source_human_approval_artifact_v1`** (built on demand when absent). It models the **exact future governed command posture** that would be eligible for execution **only after** signed human approvals and a separate activation sprint—without executing commands, activating sources, persisting approvals, writing database rows, scraping, ingesting, calling external APIs, calling LLMs, or creating operator ledger actions.

Implementation: `nativeforge.services.source_activation_command_dry_run_service.build_source_activation_command_dry_run`.

Integration: `build_discovery_source_quality` attaches **`source_activation_command_dry_run`** immediately after **`source_human_approval_artifact`** on **`nf_discovery_source_quality_v1`** (and therefore on operator **`source_quality`** payloads).

## Schema (summary)

| Section | Description |
|--------|-------------|
| `organization_scope` | `organization_id`, `generated_at` |
| `command_posture` | Posture, scores, counts; **`signed_approval_count` always 0**; **`executable_command_count` always 0**; **`actual_activation_count` always 0**; **`actual_database_write_count` always 0**; `dry_run_command_count`, `blocked_command_count`, `unsigned_approval_count` |
| `dry_run_commands` | Per-candidate rows: `dry_run_command_id` (deterministic), artifact/candidate identity, `command_status` (`dry_run_*`), `command_recommendation`, `proposed_command_type`, **`proposed_active_source_record_snapshot`** (copy from Sprint 41), `required_signed_approval_fields`, `required_pre_execution_checks`, `missing_pre_execution_requirements`, `unresolved_blockers`, **`rollback_plan`**, **`dry_run_boundary`**, **`dry_run_only` true**, **`should_create_action` false**, **`can_become_active_source` false** |
| `command_batches` | `ordered_batches` aligned to approval batches with `batch_command_status`, `dry_run_command_ids`, `required_batch_pre_execution_checks`, `rollback_requirements`, **`dry_run_only` true**, **`should_create_action` false** |
| `global_command_boundary` | **`command_dry_run_only` true**; counts at zero; denial of command execution, approval persistence, activation, database writes, scraping, ingestion, external APIs, and ledger actions |
| `risk_flags` | Deterministic governance flags |
| `summary` | Short narrative |
| `recommended_review_interval_days` | Integer aligned with source-quality posture bands |

Each **`dry_run_command_id`** is **deterministic**: SHA-256 over `organization_id`, `approval_artifact_id`, `candidate_id`, and `nf_source_activation_command_dry_run_v1`.

## Relationship to upstream artifacts

- **`nf_discovery_source_quality_v1`** (Sprint 33+) supplies posture, counts, and embeddings for downstream builders.
- **`nf_source_coverage_plan_v1`** (Sprint 36) informs lane posture consumed indirectly through onboarding and readiness.
- **`nf_source_candidate_registry_v1`** (Sprint 37) supplies registry-backed metadata referenced via previews and snapshots.
- **`nf_source_onboarding_decision_pack_v1`** (Sprint 38) supplies batch choreography mirrored into **`command_batches`**.
- **`nf_source_activation_readiness_contract_v1`** (Sprint 39) supplies evidence expectations reflected in missing requirements and blockers.
- **`nf_source_activation_preview_v1`** (Sprint 40) supplies the **`proposed_active_source_record_snapshot`** lineage (via Sprint 41).
- **`nf_source_human_approval_artifact_v1`** (Sprint 41) supplies approval row identity, unsigned approval status, batch alignment, and the snapshot copy for each command row.

## Command dry-run-only boundary

**`executable_command_count` is always 0.** No command row sets **`dry_run_boundary.may_execute_command_now`** to true. **`global_command_boundary.command_dry_run_only`** is always true.

## Unsigned approval boundary

**`signed_approval_count` is always 0** at posture and global boundary. Every command keeps **`dry_run_boundary.approval_is_unsigned`** and **`approval_is_not_persisted`** true.

## No approval persistence boundary

**`may_persist_approval_now` and `global_command_boundary.may_persist_approvals_now` are false.** This sprint materializes review-only packets.

## No activation / no database write / no ingestion / no scraping / no API / no ledger boundary

**`may_activate_source_now`**, **`may_write_database_rows_now`**, **`may_start_ingestion_now`**, and global **`may_*`** execution toggles are false for scraping, ingestion, external APIs, and ledger actions. Payloads are offline deterministic.

## Proposed future command shape

Each row uses **`proposed_command_type`** as planning language only (`create_active_source_record_future`, `defer_activation_future`, `legal_review_future`, `research_followup_future`) paired with **`command_recommendation`** (for example `collect_signature_then_rerun_dry_run`, `resolve_evidence_gaps`, `complete_legal_tos_review`, `continue_research`, `defer`).

## Required signed approval fields

**`required_signed_approval_fields`** enumerates operator name, role, timestamp, notes, legal/TOS acknowledgment, Native relevance acknowledgment, provenance, freshness, and dedupe acknowledgments—all required as future signature gates.

## Pre-execution checks

**`required_pre_execution_checks`** lists deterministic gate names (for example `signed_human_approval_present`, `rollback_plan_reviewed`, `no_scraping_or_api_execution_without_separate_approval`). **`missing_pre_execution_requirements`** summarizes what remains unsatisfied while every approval stays unsigned.

## Rollback plan requirements

Every **`dry_run_commands`** row includes **`rollback_plan`** booleans (`disable_active_source_required`, preserve provenance snapshot, audit reason, operator rollback approval, downstream ingestion pause, rollback test before activation)—**metadata only**; no writes.

## Proposed active source record snapshot

**`proposed_active_source_record_snapshot`** is inherited from Sprint 41 (itself Sprint 40-shaped). It is **dry-run only** and **not persisted**.

## Legal / TOS acknowledgment

Contexts that imply philanthropy, portals, APIs, or broad federal public access elevate legal/TOS review language in classifications and missing requirements **without implying execution**.

## Native relevance acknowledgment

Broad Native-eligible lanes remain explicitly review-dependent; breadth does **not** equal confirmed tribal specificity.

## Provenance requirements

Snapshots carry deterministic provenance field anchors; unresolved evidence gaps remain listed until operator closure in a future sprint.

## Freshness requirements

Snapshots carry cadence hints; acknowledgments remain required until operator-approved schedules exist.

## Dedupe requirements

Snapshots carry deterministic dedupe strategy labels only; acknowledgment remains required until governance closure.

## Native-first, not Native-only doctrine

Command choreography may emphasize federal Native-specific signals under critical posture, yet **still performs no activation**. Portfolio breadth spans tribal, philanthropy, university, corporate, state/local, and broad Native-eligible channels without shrinking or removing registry intent.

## Future pathway to real human-approved source activation

After separate governed signatures, evidence closure, and a permitted activation execution sprint, active opportunity sources may be created under future automation—**never from this Sprint 42 layer**.

## Related documents

- Human approval artifact: [nativeforge-source-human-approval-artifact-v1.md](./nativeforge-source-human-approval-artifact-v1.md)
- Activation preview: [nativeforge-source-activation-preview-v1.md](./nativeforge-source-activation-preview-v1.md)
- Activation readiness contract: [nativeforge-source-activation-readiness-contract-v1.md](./nativeforge-source-activation-readiness-contract-v1.md)
- Onboarding decision pack: [nativeforge-source-onboarding-decision-pack-v1.md](./nativeforge-source-onboarding-decision-pack-v1.md)
- Candidate registry: [nativeforge-source-candidate-registry-v1.md](./nativeforge-source-candidate-registry-v1.md)
