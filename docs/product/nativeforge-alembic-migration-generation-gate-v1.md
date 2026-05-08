# NativeForge Alembic migration generation gate (v1)

## Purpose

The Alembic migration generation gate (`schema_version: nf_alembic_migration_generation_gate_v1`) is a deterministic, JSON-serializable **final planning checkpoint** before any future sprint is allowed to author a real Alembic revision for `nf_active_opportunity_sources`. It consumes Sprint 44 `nf_active_source_migration_dry_run_plan_v1` (and indirectly `nf_discovery_source_quality_v1` / Sprint 43 rollback contract material), then emits field, constraint, index, upgrade, and downgrade **generation manifests**, gate checks, manual authorization requirements, migration file absence proof, and explicit global boundaries—without creating an Alembic revision, applying a migration, writing database rows, activating sources, persisting approvals, scraping, ingesting, calling external APIs, or creating operator ledger actions.

Implementation: `nativeforge.services.alembic_migration_generation_gate_service.build_alembic_migration_generation_gate`.

Integration: `build_discovery_source_quality` attaches `alembic_migration_generation_gate` immediately after `active_source_migration_dry_run_plan`, so operator Workbench `source_quality` payloads inherit the gate alongside Sprint 44.

## Schema

Top-level groups:

- `organization_scope`: org identity and generation timestamp aligned with upstream payloads.
- `generation_gate_posture`: posture, counts, gate check tallies, and **always-zero** actual Alembic revision, migration, database write, and activation counters.
- `migration_generation_candidate`: proposed migration identity (`create_nf_active_opportunity_sources`), table name, revision slug, dependency revision hint, counts, and generation boundary flags (`generation_gate_only_not_created`, no revision generation now).
- `field_generation_manifest`, `constraint_generation_manifest`, `index_generation_manifest`: rows transcribed from Sprint 44 maps with `generation_status: planned_not_generated`, `dry_run_only: true`, and **never** `may_generate_now` / `may_apply_now` true.
- `upgrade_generation_plan` / `downgrade_generation_plan`: ordered planned operations with proposed Alembic call sketches and boundaries denying execution in Sprint 45.
- `gate_checks`: deterministic checks with `passed`, `blocked`, or `manual_required` status.
- `manual_authorization_requirements`: future operator, schema owner, rollback owner, Alembic head, downgrade path, and no-live-ingestion requirements with `authorization_status: not_authorized` and `should_create_action: false`.
- `migration_file_absence_proof`: repository scan under `alembic/versions` for forbidden filename patterns; Sprint 45 expects `matching_revision_files_found` to remain empty.
- `global_generation_boundary`: product-wide denial surface for revision creation, migration apply, database writes, activation, ingestion, scraping, external APIs, and ledger actions.
- `risk_flags`, `summary`, `recommended_review_interval_days`.

## Relationship to Sprint 44 migration dry-run plan

Sprint 44 produces `field_migration_map`, `constraint_migration_map`, `index_migration_map`, and ordered upgrade/downgrade steps. Sprint 45 **does not reinterpret** those maps; it reformats them into generation-oriented manifests, adds Alembic-oriented operation labels, runs deterministic gate checks, and records that **no revision file exists yet**.

See: [nativeforge-active-source-migration-dry-run-plan-v1.md](./nativeforge-active-source-migration-dry-run-plan-v1.md).

## Generation gate only boundary

`global_generation_boundary.generation_gate_only` is always `true`. `actual_alembic_revision_count`, `actual_migration_count`, `actual_database_write_count`, and `actual_activation_count` are always `0`. `alembic_revision_created_now` is always `false`. Every manifest row keeps `dry_run_only: true` and denies generation/application now.

## No Alembic revision / no database write / no activation

This sprint **does not** add a file under `alembic/versions`. It **does not** run Alembic upgrade/downgrade. It **does not** create tables or rows. It **does not** activate sources or persist approvals. Those obligations move to **future** operator-authorized migration generation, review, and local verification sprints.

## Migration generation candidate

`proposed_migration_name` and `proposed_revision_slug` are `create_nf_active_opportunity_sources`. `proposed_table_name` is `nf_active_opportunity_sources`. `proposed_revision_status` is `generation_gate_only_not_created`. `proposed_generation_mode` is `future_operator_authorized_only`. `proposed_dependency_revision` mirrors Sprint 44 (`current_existing_head_or_unknown` until resolved against the live head).

## Field generation manifest

Each Sprint 44 field row becomes a manifest row with SQLAlchemy type hints, `proposed_alembic_operation: create_table_column_future`, `source_migration_plan_reference` pointing into `nf_active_source_migration_dry_run_plan_v1.field_migration_map`, and explicit denial flags for generation and apply in this sprint.

## Constraint and index generation manifests

Constraints and indexes reference Sprint 44 rows with `op.create_unique_constraint_future` and `op.create_index_future` labels. All rows remain planning metadata only.

## Upgrade and downgrade generation plans

Upgrade and downgrade operations mirror Sprint 44 step ordering with additional `proposed_alembic_call` sketches. Boundaries keep `may_generate_*_now: false` and `may_execute_*_now: false`. Downgrade retains `rollback_review_required: true`.

## Manual authorization requirements

Future work requires explicit operator generation authorization, schema owner review, rollback owner review, Alembic head verification, downgrade path review, and confirmation of a no-live-ingestion window. `authorization_status` remains `not_authorized` until recorded outside this payload. `should_create_action` is `false`.

## Migration file absence proof

The service records forbidden glob patterns for filenames under `alembic/versions`. An empty `matching_revision_files_found` list is the expected healthy state before any future migration generation sprint.

## Global generation boundary

Denies revision generation, migration application, database writes, activation, scraping, ingestion, external API usage, and ledger action creation. Requires future migration generation, operator authorization, migration review sprint, and local migration verification.

## Required operator, schema, and rollback approvals

Operator generation authorization, schema owner stewardship, and rollback owner review remain prerequisites. Sprint 45 surfaces gaps via `manual_authorization_requirements` and `manual_required` gate checks without persisting approvals.

## Provenance requirements

Manifests retain Sprint 43/Sprint 44 provenance-related columns; gate checks include `provenance_fields_present`.

## Freshness requirements

Freshness cadence and related health fields remain in the field manifest; gate checks include `freshness_fields_present`.

## Dedupe requirements

Dedupe strategy fields and unique constraints remain represented; gate checks include `dedupe_fields_present`.

## Legal / TOS requirements

Legal/TOS review fields remain in the manifest; gate checks include `legal_tos_fields_present`.

## Native relevance requirements

Native relevance basis and keyword-not-confirmed semantics remain governed (no confirmed eligibility from planning payloads); gate checks include `native_relevance_fields_present`.

## Native-first, not Native-only doctrine

Source coverage and governed onboarding remain the product engine. This gate reinforces **conservative, staged schema stewardship**—especially under strong posture—rather than urgent activation language.

## Future pathway to actual migration generation sprint

After operator authorization, schema and rollback reviews, Alembic head verification, and migration review/verification sprints, a **future** sprint may generate an Alembic revision file, subject to repository policy and CI. Sprint 45 explicitly stays upstream of that step.
