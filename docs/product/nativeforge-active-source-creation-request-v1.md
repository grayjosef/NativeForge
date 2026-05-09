# NativeForge active source creation request (v1)

## Sprint 55 purpose

Sprint 55 introduces a **governed request artifact** of type `nf_active_source_creation_request_v1`, produced by `nativeforge.services.active_source_creation_request_service`. The artifact packages everything an operator needs to **propose** the first row in `nf_active_opportunity_sources` for a **future**, human-approved source-creation sprint.

## What this sprint does

- Builds a deterministic, JSON-safe **request packet** from an optional `request_payload` dict.
- Validates required governance fields (identity, target URL or search surface, type/lane, collection method, cadence, Native relevance, legal/TOS posture, provenance plan, rollback reference, and human-review booleans).
- Emits a structured **`future_insert_preview`** that maps request fields to **real ORM / migration 0019 column names** with explicit preview-only boundaries (no SQL strings).
- Aligns with Sprint **54** empty-state discipline by referencing artifact type `nf_active_source_empty_state_read_model_v1` and revision **0019** / table `nf_active_opportunity_sources`.

## What this sprint does not do

- It does **not** insert rows into `nf_active_opportunity_sources` or seed data.
- It does **not** activate sources, scrape, ingest, call external APIs, or call LLMs.
- It does **not** create operator ledger actions, run Alembic, or change schema.
- It does **not** open any execution path where `may_create_source_rows_now` or `may_write_database_now` becomes true; those flags remain **false** even when `readiness_decision` is `ready_for_human_source_creation_review`.

## Human review and next sprint

A payload that passes validation sets `readiness_decision` to `ready_for_human_source_creation_review`. That means the packet is **ready for human source-creation review**, not that automation may insert. The **next sprint** is **active source human approval intake**: operators fill `human_approval_requirements` sign-off fields in a controlled process before any future insert sprint.

## Readiness decision values

The artifact documents three deterministic readiness values in `governance_readiness_decision_values`:

- `not_ready` — absent payload, missing/blank required fields, invalid cadence, or governance booleans not satisfied.
- `blocked_requires_human_review` — reserved governance vocabulary for future edge routing (Sprint 55 defaults to `not_ready` when validation fails).
- `ready_for_human_source_creation_review` — complete valid request payload; still **no** row creation in Sprint 55.

## Discovery integration

`discovery_source_quality_service` may embed `active_source_creation_request` using `build_discovery_read_only_active_source_creation_request_attachment()`, which calls the builder with **no** payload so operators always see a read-only `not_ready` baseline unless they invoke the builder directly with a payload elsewhere.
