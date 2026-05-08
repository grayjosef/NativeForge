# NativeForge active source runtime migration readiness gate (v1)

## Sprint 50 purpose

Sprint 50 adds a **read-only, deterministic readiness decision gate** that sits **after** Sprint 48 (runtime migration apply **plan** artifact) and Sprint 49 (human approval **intake** validation artifact). It answers whether a **future** operator-controlled apply sprint may be **prepared** with explicit human execution—it never authorizes immediate apply work from this sprint.

## Inputs

The gate consumes:

- **Sprint 48:** `build_active_source_runtime_migration_apply_plan(...)` → artifact type `nf_active_source_runtime_migration_apply_plan_v1`.
- **Sprint 49:** `build_active_source_runtime_migration_approval_intake(approval_payload)` → artifact type `nf_active_source_runtime_migration_approval_intake_v1`.

An optional `approval_payload` dict may be supplied; it is passed through Sprint 49 validation unchanged.

## Decision values

The gate emits `readiness_decision` (and aligned `gate_status`) as one of:

| Value | Meaning |
| --- | --- |
| `not_ready` | Preconditions are incomplete (e.g. no approval payload, or Sprint 49 intake not `ready_for_future_apply_sprint`). |
| `blocked_requires_human_review` | Sprint 48 plan is missing/malformed, not in the expected plan-only posture, revision/table mismatch, or boundary/`actual_*` violations require human review. |
| `ready_for_apply_window` | Sprint 48 plan and Sprint 49 intake are internally consistent and valid; a **future** apply sprint may be **scheduled and prepared**—**not** executed here. |

## Hard boundaries (this sprint)

Sprint 50 **does not**:

- Apply Alembic migrations or run Alembic CLI commands.
- Open database connections or write to any persistent database.
- Create source rows, seed data, or activate sources.
- Scrape, ingest, call external APIs, call LLMs, or create operator ledger actions.

Even when `readiness_decision == ready_for_apply_window`, the artifact **always** keeps:

- `may_apply_runtime_migration_now = false`
- All other `may_*` execution flags **false**
- All `actual_*` execution counts **zero**

`ready_for_apply_window` only means **preparation for a future apply sprint is logically allowed**, never “apply now” from Sprint 50.

## Related artifacts

- Sprint 46 migration file: `alembic/versions/0019_nf_active_opportunity_sources.py`
- Target revision chain: `0018` → `0019`
- Target table: `nf_active_opportunity_sources`

## Discovery embedding

`build_discovery_source_quality` may embed `active_source_runtime_migration_readiness_gate` by calling the gate with **no** approval payload. That yields a read-only governance snapshot (typically `not_ready` until an approval payload is supplied through the proper operator path). Nothing is persisted by the gate itself.
