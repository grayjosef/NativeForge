# NativeForge post-runtime active source verification (v1)

## Sprint 64 purpose

Sprint 64 adds a **read-only** verification step that treats the runtime-created row in `nf_active_opportunity_sources` as a **durable governed read-model object**. The service compares the live database row to the committed Sprint 62/63 runtime evidence artifact and emits `nf_active_source_post_runtime_verification_v1`.

## What this sprint does

- Confirms the runtime evidence artifact is present and structurally valid for verification.
- Loads the referenced row using an **explicitly passed** SQLAlchemy session (the service never opens its own session).
- Proves identity and governance fields match the evidence snapshot (organization, name, type, URL target, status, health, rollback contract).
- Proves activation approval fields remain null and pipeline timestamps remain unset for the verified path.
- Preserves the Sprint 63 runtime evidence file as the source of truth; verification does not mutate it.

## What this sprint does not do

- Does **not** activate the source.
- Does **not** scrape, ingest, call external APIs, or call LLMs.
- Does **not** create operator ledger actions.
- Does **not** insert, update, or delete rows in `nf_active_opportunity_sources`.
- Does **not** modify schema or create Alembic revisions.
- Does **not** execute shell commands or Alembic CLI.

## Readiness decisions

The artifact `readiness_decision` may be one of:

- `not_ready`
- `blocked_missing_runtime_evidence`
- `blocked_runtime_evidence_invalid`
- `blocked_source_row_missing`
- `blocked_source_row_mismatch`
- `blocked_source_already_activated`
- `verified_runtime_source_row_ready_for_activation_gate`

## Next sprint

After a successful verification, the next governed step is the **activation review packet scaffolding** (future sprint), not live activation.

## Implementation

- `src/nativeforge/services/active_source_post_runtime_verification_service.py` — `build_post_runtime_active_source_verification`
