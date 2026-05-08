# NativeForge source human approval artifact (v1)

## Purpose

The human approval artifact (`schema_version: nf_source_human_approval_artifact_v1`) is a **deterministic, JSON-serializable, unsigned paperwork layer** that consumes **`nf_discovery_source_quality_v1`** and Sprint 40 **`nf_source_activation_preview_v1`**. It produces a **formal approval packet** for operator review **before** any future activation command dry-run or activation sprint—without approving candidates, activating sources, writing database rows, scraping, ingesting, calling external APIs, calling LLMs, or creating operator ledger actions.

Implementation: `nativeforge.services.source_human_approval_artifact_service.build_source_human_approval_artifact`.

Integration: `build_discovery_source_quality` attaches **`source_human_approval_artifact`** after **`source_activation_preview`** on **`nf_discovery_source_quality_v1`** (and on operator **`source_quality`** payloads).

## Schema (summary)

| Section | Description |
|--------|-------------|
| `organization_scope` | `organization_id`, `generated_at` |
| `approval_posture` | Posture, scores, preview counts, **`approval_artifact_count`**, **`signed_approval_count` always 0**, **`actual_activation_count` always 0** |
| `approval_artifacts` | Per-candidate unsigned rows: recommendation (planning language only), attestations, required approvals/evidence, missing evidence, blockers, **`proposed_active_source_record_snapshot`** (copy from preview), **`approval_signature_block`**, **`approval_boundary`**, **`dry_run_only` true**, **`should_create_action` false** |
| `approval_batches` | `ordered_batches` aligned to preview batches with **`approval_artifact_ids`**, **`batch_approval_status`**, **`required_batch_attestations`**, **`dry_run_only` true**, **`should_create_action` false** |
| `global_approval_boundary` | **`approval_artifact_only` true**, **`signed_approval_count` 0**, **`actual_activation_count` 0**, denial of approval persistence, activation, database writes, scraping, ingestion, external APIs, and ledger actions |
| `risk_flags` | Deterministic governance flags |
| `summary` | Short narrative, including the future permitted command class label **`nf_source_activation_command_dry_run_v1`** (not executed here) |
| `recommended_review_interval_days` | Integer aligned with source-quality posture bands |

Each **`approval_artifact_id`** is **deterministic**: SHA-256 over `organization_id`, `candidate_id`, and `nf_source_human_approval_artifact_v1` (stable hex prefix style consistent with Sprint 37 registry IDs).

## Relationship to upstream artifacts

- **`nf_discovery_source_quality_v1`** (Sprint 33+) supplies posture, counts, and embeddings for downstream builders.
- **`nf_source_coverage_plan_v1`** (Sprint 36) informs lane posture (including overrepresented lanes) consumed indirectly through onboarding and readiness.
- **`nf_source_candidate_registry_v1`** (Sprint 37) supplies registry-backed metadata referenced via previews.
- **`nf_source_onboarding_decision_pack_v1`** (Sprint 38) supplies batch choreography mirrored into **`approval_batches`**.
- **`nf_source_activation_readiness_contract_v1`** (Sprint 39) supplies **`required_evidence`** lists matched per candidate for artifact rows.
- **`nf_source_activation_preview_v1`** (Sprint 40) supplies **`preview_status`** fields, **`proposed_active_source_record`**, remaining approvals, missing evidence, and blockers mapped into this artifact.

## Unsigned approval boundary

**`signed_approval_count` is always 0.** Every artifact keeps **`approval_boundary.approval_record_is_unsigned` true** and **`approval_boundary.may_approve_now` false**. Conditional readiness from Sprint 40 maps to **`unsigned_conditionally_ready`**—a planning posture, not a signature.

## No approval persistence boundary

**`approval_boundary.approval_is_not_persisted` is always true.** **`global_approval_boundary.may_persist_approvals_now` is always false.** This sprint produces review payloads only.

## No activation / no database write / no ingestion / no scraping / no API / no ledger boundary

**`global_approval_boundary.may_activate_sources_now`**, **`may_write_database_rows_now`**, **`may_scrape_now`**, **`may_ingest_now`**, **`may_call_external_apis_now`**, and **`may_create_ledger_actions_now`** are **false**. Payloads are offline deterministic; no connector execution.

## Proposed active source record snapshot

**`proposed_active_source_record_snapshot`** is a **verbatim preview-only copy** of Sprint 40 **`proposed_active_source_record`**. It illustrates future fields **without persistence** and **without authorization** to activate.

## Required operator attestations

Artifact rows include deterministic attestation strings (for example confirmation that Native relevance is not keyword-inferred alone, that broad eligibility differs from confirmed tribal eligibility, and that this artifact does not authorize scraping, API polling, or ingestion). Additional lane-specific lines may appear for broad Native-eligible or not-ready paths.

## Required evidence

**`required_evidence`** carries the Sprint 39-aligned evidence inventory from the readiness contract for each candidate. **`missing_required_evidence`** carries preview-listed gaps still outstanding on file.

## Legal / TOS acknowledgment

**`approval_signature_block.legal_tos_acknowledgment_required`** may be **true** when lane or proposed collection posture implies portal, API, philanthropy, or federal broad-public-access review contexts—still **unsigned** in this sprint.

## Native relevance acknowledgment

**`native_relevance_acknowledgment_required`** stays **true**: Native-first relevance remains operator-judged, not inferred from catalog keywords alone.

## Provenance requirements

Artifact rows inherit preview **`proposed_provenance_fields`** inside the snapshot and surface readiness **`required_evidence`** entries tied to publisher identity and capture plans.

## Freshness requirements

Snapshot carries deterministic freshness cadence hints; **`freshness_acknowledgment_required`** stays **true** until operator-approved schedules exist.

## Dedupe requirements

Snapshot carries **`proposed_dedupe_key_strategy`** as a label only; **`dedupe_acknowledgment_required`** stays **true** until an approved dedupe posture exists.

## Native-first, not Native-only doctrine

Coverage spans federal, tribal, philanthropic, corporate, university, and broad Native-eligible channels. Broad lanes remain explicitly **`unsigned_review_required`** or **`unsigned_not_ready`** as appropriate—they do **not** confirm tribal specificity without human judgment.

## Future pathway to activation command dry-run

After separate governed signatures and evidence closure, the next permitted automation class is **`nf_source_activation_command_dry_run_v1`**, followed by a future activation sprint. **Sprint 41 stops at unsigned approval artifacts.**

## Related documents

- Activation preview: [nativeforge-source-activation-preview-v1.md](./nativeforge-source-activation-preview-v1.md)
- Activation readiness contract: [nativeforge-source-activation-readiness-contract-v1.md](./nativeforge-source-activation-readiness-contract-v1.md)
- Onboarding decision pack: [nativeforge-source-onboarding-decision-pack-v1.md](./nativeforge-source-onboarding-decision-pack-v1.md)
- Candidate registry: [nativeforge-source-candidate-registry-v1.md](./nativeforge-source-candidate-registry-v1.md)
- Coverage plan: [nativeforge-source-coverage-plan-v1.md](./nativeforge-source-coverage-plan-v1.md)
