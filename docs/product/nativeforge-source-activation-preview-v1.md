# NativeForge source activation preview (v1)

## Purpose

The human-approved source activation preview (`schema_version: nf_source_activation_preview_v1`) is a **deterministic, JSON-serializable, dry-run-only** layer that consumes **`nf_discovery_source_quality_v1`** and the Sprint 39 **`nf_source_activation_readiness_contract_v1`**. It produces a **reviewable preview** of what **active-source-like** fields could look like **after** future human approval—without activating sources, writing database rows, scraping, ingesting, calling external APIs, calling LLMs, or creating operator ledger actions.

Implementation: `nativeforge.services.source_activation_preview_service.build_source_activation_preview`.

Integration: `build_discovery_source_quality` attaches **`source_activation_preview`** alongside **`source_activation_readiness_contract`**, **`source_onboarding_decision_pack`**, **`source_candidate_registry`**, **`source_coverage_plan`**, and Sprint 41 **`source_human_approval_artifact`** (`nf_source_human_approval_artifact_v1`) on **`nf_discovery_source_quality_v1`** (and therefore on operator **`source_quality`** payloads).

## Schema (summary)

| Section | Description |
|--------|-------------|
| `organization_scope` | `organization_id`, `generated_at` |
| `preview_posture` | Posture, scores, counts (`preview_candidate_count`, `conditionally_ready_count`, `blocked_count`, `not_ready_count`, `human_approval_required_count`, `legal_tos_required_count`, `proposed_activation_count`, **`actual_activation_count` always 0**) |
| `activation_previews` | Per-candidate dry-run rows: `source_activation_preview_status` (`preview_only_*`), **`proposed_active_source_record`** (preview-only normalized shape), remaining approvals, missing evidence, blockers, operator notes, per-row boundaries (**`may_activate_source_now` false**, **`may_write_active_source_now` false**, **`may_write_database_rows_now` false**, **`can_become_active_source` false**, **`should_create_action` false**, **`dry_run_only` true**) |
| `activation_preview_batches` | `ordered_batches` aligned to the onboarding batch plan with `preview_batch_status`, `required_batch_approvals`, **`dry_run_only` true**, **`should_create_action` false** |
| `global_preview_boundary` | Org-wide **`preview_only` true**, **`actual_activation_count` 0**, denial of activation, database writes, scraping, ingestion, external APIs, and ledger actions from this sprint |
| `risk_flags` | Deterministic governance flags for preview posture |
| `summary` | Short narrative |
| `recommended_review_interval_days` | Integer aligned with source-quality posture bands |

## Relationship to upstream artifacts

- **`nf_discovery_source_quality_v1`** (Sprint 33+) provides posture, counts, and embeddings for coverage, registry, onboarding, and readiness builders.
- **`nf_source_coverage_plan_v1`** (Sprint 36) informs lane posture (including overrepresented-lane maintenance context) consumed indirectly through readiness.
- **`nf_source_candidate_registry_v1`** (Sprint 37) supplies deterministic candidate metadata used for proposed fields (for example `expected_update_frequency`, Native relevance seeds).
- **`nf_source_onboarding_decision_pack_v1`** (Sprint 38) supplies **`batch_review_plan`** choreography mirrored into **`activation_preview_batches`** without changing Sprint 38 semantics.
- **`nf_source_activation_readiness_contract_v1`** (Sprint 39) supplies per-candidate activation readiness status and governance contracts that Sprint 40 **maps into preview-only statuses** (for example `conditionally_ready` → `preview_only_conditionally_ready`).

## Dry-run-only boundary

**`actual_activation_count` is always 0.** **`global_preview_boundary.preview_only` is always true.** No candidate is activated in this sprint. No preview row sets **`may_activate_source_now`**, **`may_write_active_source_now`**, or **`may_write_database_rows_now`** to true. No preview or batch row sets **`should_create_action`** to true.

## No activation / no database write / no ingestion / no scraping / no API / no ledger boundary

Payloads are **offline deterministic**. This layer does not perform ingestion, scraping, external API calls, LLM calls, or operator action ledger writes. It does not create or mutate active opportunity source rows.

## Proposed active source record shape

**`proposed_active_source_record`** is a **normalized preview-only** projection (for example proposed name, lane, collection method hints, freshness cadence, dedupe strategy label, provenance field list, Native relevance basis). It is **not persisted** and does **not** authorize activation.

## Human approval gate

Every preview row keeps **`requires_human_approval: true`** and lists **`remaining_required_approvals`** still outstanding for a future activation sprint. **`human_approval_required_count`** reflects that governance remains mandatory for every candidate in scope.

## Future activation sprint requirement

**`requires_future_activation_sprint: true`** on preview rows and **`requires_future_activation_sprint`** on the global boundary state that **a later governed sprint** is required before real active source creation.

## Provenance requirements

Preview rows surface **`missing_required_evidence`** aligned to Sprint 39 evidence expectations (for example publisher identity, Native relevance basis, capture plan). Dry-run semantics treat these as **not yet on file** for preview purposes.

## Freshness requirements

**`proposed_freshness_cadence_days`** and **`proposed_stale_threshold_days`** are deterministic projections derived from lane and source type—planning hints only until operator-approved freshness plans exist.

## Dedupe requirements

**`proposed_dedupe_key_strategy`** is a deterministic label describing how overlap would be handled in a future activation sprint—not an executed dedupe job.

## Native relevance requirements

**`proposed_native_relevance_basis`** carries deterministic Native relevance context from registry seeds where available. **Broad Native-eligible** lanes remain **`preview_only_review_required`** (or **`preview_only_not_ready`** for keyword-only paths) and **do not** imply confirmed eligibility. **Keyword-only** Native mentions remain **not confirmed eligible**, consistent with Sprint 39 **`keyword_only_not_confirmed_eligible`**.

## Native-first, not Native-only doctrine

Coverage spans federal, tribal, philanthropic, corporate, university, and broad Native-eligible channels. The preview **prioritizes Native programmatic relevance** while keeping broad channels explicitly behind human review.

## Future pathway to real human-approved active source creation

After operator approvals and evidence gates are satisfied in future sprints, a governed activation sprint may create real active opportunity source rows with ledger-approved actions and connectors. **Sprint 40 stops at preview artifacts**—still **dry-run only**.

## Related documents

- Human approval artifact (Sprint 41): [nativeforge-source-human-approval-artifact-v1.md](./nativeforge-source-human-approval-artifact-v1.md)
- Activation readiness contract: [nativeforge-source-activation-readiness-contract-v1.md](./nativeforge-source-activation-readiness-contract-v1.md)
- Onboarding decision pack: [nativeforge-source-onboarding-decision-pack-v1.md](./nativeforge-source-onboarding-decision-pack-v1.md)
- Candidate registry: [nativeforge-source-candidate-registry-v1.md](./nativeforge-source-candidate-registry-v1.md)
- Coverage plan: [nativeforge-source-coverage-plan-v1.md](./nativeforge-source-coverage-plan-v1.md)
