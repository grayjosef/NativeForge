# NativeForge Active Source Runtime Migration Approval Intake (`nf_active_source_runtime_migration_approval_intake_v1`)

## Sprint 49 purpose

Sprint 49 delivers a **deterministic approval intake validation artifact** for **migration `0019`** (`alembic/versions/0019_nf_active_opportunity_sources.py`). It answers whether an optional human **approval payload** is **complete enough** for a **future** operator apply sprint to proceed to apply **design and review** — not whether migration apply may run from this codebase today.

This sprint **does not**:

- Apply migrations to runtime, development, or production application databases.
- Run Alembic CLI commands (`current`, `upgrade`, `downgrade`, etc.).
- Write to any persistent database or open pooled connections for migration apply.
- Create rows in `nf_active_opportunity_sources`, seed data, or activate sources.
- Scrape, ingest, call external APIs, call LLMs, or create operator ledger actions.

## Relationship to Sprint 48

Sprint **48** produced the plan-only artifact `nf_active_source_runtime_migration_apply_plan_v1`, including the **required approval field names** and **plan_only** posture. Sprint **49** validates those same fields when supplied as an **approval intake payload**. It does **not** replace the apply plan and does **not** execute operator commands.

## Readiness semantics

- **`not_ready`**: Payload absent, incomplete, blank, semantically invalid (including revision mismatches or boolean attestations not literally `true`), or approval statement failing the deterministic phrase gate.
- **`ready_for_future_apply_sprint`**: All required fields pass validation. This means only that a **future** apply sprint may continue with apply planning and human workflow — **never** “apply now” from Sprint 49.

**Always true for Sprint 49 outputs:**

- `may_apply_runtime_migration_now` is **false**.
- All `actual_*` execution counts are **zero**.
- All `may_*` capability flags that imply immediate side effects remain **false**.

## Discovery source quality embedding

`build_discovery_source_quality()` may include `active_source_runtime_migration_approval_intake` as a **read-only governance signal** using an **empty approval payload by default** (typically `not_ready`). This embedding does not persist approvals, create operator actions, write database rows, run Alembic, or enable activation.
