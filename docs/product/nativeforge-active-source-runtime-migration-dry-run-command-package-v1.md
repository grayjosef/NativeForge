# NativeForge active source runtime migration dry-run command package (v1)

## Sprint 51 purpose

Sprint 51 produces a **deterministic, preview-only** artifact of type `nf_active_source_runtime_migration_dry_run_command_package_v1`. It packages **future operator command strings** for applying Alembic revision **0019** (`alembic/versions/0019_nf_active_opportunity_sources.py`, table `nf_active_opportunity_sources`) **after** a separate, human-approved apply sprint. This sprint **never** executes those commands.

## Consumes Sprint 50

The builder calls `build_active_source_runtime_migration_readiness_gate(approval_payload)` and embeds the full gate JSON under `readiness_gate_artifact`. Field `readiness_decision` on the package **mirrors** Sprint 50 (`not_ready`, `blocked_requires_human_review`, or `ready_for_apply_window`).

- `readiness_gate_required` is always **true**.
- `readiness_gate_required_decision` is always **`ready_for_apply_window`** — the package is only in **`preview_ready_for_future_apply_sprint`** status when Sprint 50 emits that decision.

## Package status

| `package_status` | When |
| --- | --- |
| `blocked` | Sprint 50 `readiness_decision` is anything other than `ready_for_apply_window`. Preview strings may still be present for planning, but the package is **not** executable. |
| `preview_ready_for_future_apply_sprint` | Sprint 50 gate is `ready_for_apply_window`. This still **does not** authorize apply work from Sprint 51. |

## Command previews (strings only)

Preflight, apply, post-apply validation, and rollback sections each list command objects with `preview_only: true`, `executed_in_sprint_51: false`, `may_execute_now: false`, and `requires_future_human_approved_apply_sprint: true`. Operators may run analogous commands **only** in the future apply sprint, against an explicitly chosen target database.

## Hard boundaries (this sprint)

Sprint 51 **does not**:

- Execute Alembic CLI commands or run Alembic programmatic APIs.
- Launch OS child processes for migration or tooling.
- Open database connections or write to any persistent database.
- Create source rows, seed data, or activate sources.
- Scrape, ingest, call external APIs, call LLMs, or create operator ledger actions.

Even when `package_status == preview_ready_for_future_apply_sprint`, the artifact **always** keeps:

- `may_apply_runtime_migration_now = false`
- `may_execute_commands_now = false`
- All other `may_*` flags **false**
- All `actual_*` execution counts **zero** (including `actual_alembic_command_execution_count` and `actual_subprocess_execution_count`)

**`preview_ready_for_future_apply_sprint` only permits preparation of a future apply sprint — never apply-now from Sprint 51.**

## Discovery embedding

`build_discovery_source_quality` may embed `active_source_runtime_migration_dry_run_command_package` by calling the builder with **no** approval payload. That yields a read-only governance snapshot (typically **`blocked`** with `not_ready` readiness) until an approval payload is supplied through the proper operator path. Nothing is persisted by the package builder itself.

## Related artifacts

- Sprint 50: `nf_active_source_runtime_migration_readiness_gate_v1`
- Sprint 48 plan: `nf_active_source_runtime_migration_apply_plan_v1`
- Sprint 49 intake: `nf_active_source_runtime_migration_approval_intake_v1`
