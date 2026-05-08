# NativeForge active source schema + rollback contract (v1)

## Purpose

The active source schema + rollback contract (`schema_version: nf_active_source_schema_rollback_contract_v1`) is a deterministic, JSON-serializable planning payload for the future active opportunity source system. It consumes `nf_discovery_source_quality_v1` and/or Sprint 42 `nf_source_activation_command_dry_run_v1`, then produces the proposed active source table shape, constraints, indexes, lifecycle, rollback mechanics, migration safety gates, and audit requirements.

Implementation: `nativeforge.services.active_source_schema_rollback_contract_service.build_active_source_schema_rollback_contract`.

Integration: `build_discovery_source_quality` attaches `active_source_schema_rollback_contract` after `source_activation_command_dry_run`, so operator Workbench `source_quality` payloads inherit the contract. Sprint 44 then attaches **`active_source_migration_dry_run_plan`** (`nf_active_source_migration_dry_run_plan_v1`) after this contract—see [nativeforge-active-source-migration-dry-run-plan-v1.md](./nativeforge-active-source-migration-dry-run-plan-v1.md).

## Relationship to upstream artifacts

Sprint 43 is the next governed step after source-quality scoring, coverage planning, candidate registry generation, onboarding decision packs, activation readiness contracts, activation previews, human approval artifacts, and command dry-runs.

The chain is:

`source quality -> source coverage plan -> source candidate registry -> onboarding decision pack -> activation readiness contract -> human-approved activation preview -> human approval artifact -> activation command dry-run -> active source schema + rollback contract`

Sprint 43 uses Sprint 42 command rows as schema-preview inputs. It does not sign approvals, persist approval artifacts, execute activation commands, create active opportunity source rows, or start ingestion.

## Schema Contract Only Boundary

The payload is a design contract only. `global_schema_boundary.schema_contract_only` is always `true`. `actual_migration_count`, `actual_database_write_count`, and `actual_activation_count` are always `0`.

The contract explicitly denies migration creation, migration application, database writes, source activation, scraping, ingestion, external API calls, and operator ledger actions.

## Proposed Active Source Table Shape

The proposed table name is `nf_active_opportunity_sources`, with `schema_status: design_contract_only` and `migration_status: not_created`.

The proposed fields include identity, org isolation, source name/type/lane, source target, collection method, update frequency, freshness cadence, stale threshold, health timestamps, health status, lifecycle status, dedupe strategy, provenance capture plan, Native relevance basis, broad eligibility review, keyword-only eligibility guard, legal/TOS review, public access basis, activation approval linkage, activation command linkage, rollback contract linkage, disable metadata, and timestamps.

These field rows are deterministic metadata. They do not create a database table and do not write rows.

## Required Constraints And Indexes

The proposed unique constraints are dry-run-only and cover:

- Organization, source name, and source type uniqueness.
- Organization and dedupe key strategy uniqueness.
- Organization and activation command identity uniqueness.

The proposed indexes are dry-run-only and support:

- Organization plus source lifecycle status review.
- Organization plus Native priority lane coverage review.
- Organization plus source health review.
- Freshness scheduling fields.
- Approval artifact lookup.
- Rollback contract lookup.

## Proposed Status Lifecycle

The proposed lifecycle includes:

- `candidate_reviewed`
- `approval_signed`
- `activation_pending`
- `active`
- `paused`
- `disabled`
- `retired`
- `rollback_pending`

Transitions require signed human approval, future activation execution, rollback contract testing, audit reasons, operator review, ingestion pause, freshness pause, and provenance snapshot preservation as applicable.

## Source Schema Row Previews

Each Sprint 42 dry-run command becomes a `source_activation_schema_rows` preview with `proposed_record_status: schema_preview_only`.

Every row has:

- `dry_run_only: true`
- `may_create_active_source_now: false`
- `may_write_database_rows_now: false`
- `may_create_migration_now: false`
- `should_create_action: false`

Federal Native-specific rows may produce schema previews, but they are never created by Sprint 43. Broad Native-eligible rows retain human review and no confirmed eligibility language. Keyword-only Native relevance remains not confirmed eligible. Foundation, corporate, and university rows retain legal/TOS and research requirements.

## Rollback Contract Requirements

The rollback contract is `design_contract_only`. It requires disable mechanics before activation, provenance snapshot preservation, activation approval snapshot preservation, audit reason capture, operator rollback approval, downstream ingestion pause, freshness monitor pause, rollback test completion, and rollback audit event planning.

The rollback boundary is metadata-only:

- `may_disable_source_now: false`
- `may_pause_ingestion_now: false`
- `may_write_rollback_event_now: false`
- `requires_future_rollback_test_sprint: true`

## Migration Safety Contract

The migration safety contract is also design-only. The proposed future migration name is `create_nf_active_opportunity_sources`, but Sprint 43 does not generate an Alembic revision and does not apply any migration.

Required pre-migration checks include:

- `active_source_schema_review_complete`
- `active_source_rollback_contract_review_complete`
- `alembic_migration_dry_run_required`
- `rollback_migration_plan_required`
- `source_status_lifecycle_review_complete`
- `source_health_fields_review_complete`
- `provenance_fields_review_complete`
- `freshness_fields_review_complete`
- `dedupe_constraints_review_complete`
- `legal_tos_fields_review_complete`
- `native_relevance_fields_review_complete`
- `no_live_ingestion_during_schema_migration`
- `no_customer_sensitive_data_required`

Required post-migration checks verify the future table, constraints, indexes, rollback fields, and the continued boundary that migration alone does not start ingestion or write active source rows.

## Provenance Requirements

Future active source rows must carry a provenance capture plan. Rollback must preserve a provenance snapshot before disabling any source. Provenance fields are inherited from Sprint 40/Sprint 42 preview lineage and remain review-only until a future migration and activation sprint.

## Freshness Requirements

Future active source rows must define `freshness_cadence_days`, `stale_threshold_days`, source health status, and health timestamps. Freshness monitoring is not started by this contract. A future sprint must review cadence, stale handling, health fields, and monitor pause behavior before activation.

## Dedupe Requirements

Future active source rows must carry a deterministic `dedupe_key_strategy`, and the proposed constraints protect org-scoped dedupe uniqueness. Sprint 43 only proposes the strategy and constraints; it does not enforce them in a database.

## Legal / TOS Requirements

Rows that imply portal monitoring, API use, public notice monitoring, philanthropy, corporate sources, university research, or broad public access retain legal/TOS review requirements. The contract does not authorize scraping, crawling, API calls, ingestion, or source monitoring.

## Native Relevance Requirements

NativeForge is Native-first, not Native-only. Federal Native-specific rows may lead schema previews for sparse or critical posture, but broad Native-eligible rows require explicit human review, and keyword-only Native relevance is not treated as confirmed eligibility. The contract preserves broad eligibility and keyword-only guard fields in the proposed schema.

## Future Pathway To Migration Dry-Run

Sprint 44 implements the migration dry-run plan layer on top of this contract: [nativeforge-active-source-migration-dry-run-plan-v1.md](./nativeforge-active-source-migration-dry-run-plan-v1.md). That payload must pass schema review, rollback contract review, status lifecycle review, source health review, provenance review, freshness review, dedupe review, legal/TOS review, Native relevance review, and no-live-ingestion checks before any **future** sprint is allowed to generate or apply a real Alembic migration.

Only after a future migration, signed approval artifacts, activation execution review, and rollback testing may a later sprint consider active source creation.

## Related Documents

- Migration dry-run plan (Sprint 44): [nativeforge-active-source-migration-dry-run-plan-v1.md](./nativeforge-active-source-migration-dry-run-plan-v1.md)
- Activation command dry-run: [nativeforge-source-activation-command-dry-run-v1.md](./nativeforge-source-activation-command-dry-run-v1.md)
- Human approval artifact: [nativeforge-source-human-approval-artifact-v1.md](./nativeforge-source-human-approval-artifact-v1.md)
- Activation preview: [nativeforge-source-activation-preview-v1.md](./nativeforge-source-activation-preview-v1.md)
- Activation readiness contract: [nativeforge-source-activation-readiness-contract-v1.md](./nativeforge-source-activation-readiness-contract-v1.md)
- Onboarding decision pack: [nativeforge-source-onboarding-decision-pack-v1.md](./nativeforge-source-onboarding-decision-pack-v1.md)
- Candidate registry: [nativeforge-source-candidate-registry-v1.md](./nativeforge-source-candidate-registry-v1.md)
