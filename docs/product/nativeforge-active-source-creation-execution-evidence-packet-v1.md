# NativeForge active source creation execution evidence packet (v1)

## Sprint 61 purpose

Sprint 61 is the **first** governed sprint that may **materialize exactly one** row in the runtime table **`nf_active_opportunity_sources`**. It produces artifact type **`nf_active_source_creation_execution_evidence_packet_v1`** via `nativeforge.services.active_source_creation_execution_evidence_service.execute_single_active_source_creation_and_build_evidence_packet`.

The service consumes the full governance chain from **Sprints 55–60** (request, human approval intake, execution dry-run, execution readiness gate, execution command package, execution plan) plus an explicit **`operator_confirmation`** object. It validates every upstream artifact before any database write.

## What the service does

- Validates Sprint **55** `nf_active_source_creation_request_v1` with `readiness_decision = ready_for_human_source_creation_review` (and matching `request_status`).
- Validates Sprint **56** `nf_active_source_human_approval_intake_v1` with `readiness_decision` / `approval_status = ready_for_future_source_creation_sprint`.
- Validates Sprint **57** `nf_active_source_creation_execution_dry_run_v1` with `readiness_decision` / `dry_run_status = ready_for_future_source_creation_execution_sprint`.
- Validates Sprint **58** `nf_active_source_creation_execution_readiness_gate_v1` with `readiness_decision` / `gate_status = ready_for_future_source_creation_execution`.
- Requires Sprint **59** `nf_active_source_creation_execution_command_package_v1` with `readiness_decision = ready_for_future_source_creation_execution_command_review`.
- Requires Sprint **60** `nf_active_source_creation_execution_plan_v1` with `readiness_decision = ready_for_future_single_source_row_creation_execution_review`.
- Requires strict **`operator_confirmation`** booleans and target table / revision **0019** alignment.
- Reads the materialized field map from **`request_payload_echo`** on the Sprint 55 request artifact (same keys as Sprint 59/60 future field payload).
- Counts active sources **before** and **after** the insert using the **caller-supplied** SQLAlchemy session only (the module does not construct `SessionLocal`, engines, or sessionmakers).
- Performs a **duplicate** probe on `(organization_id, source_name, source_type, source_url_or_search_target)` before insert; if a match exists, it returns **`blocked_duplicate_source_exists`** and performs **no** insert.
- Inserts **one** `NfActiveOpportunitySource` with **inactive** defaults (`source_status = activation_pending`, no activation approval fields, `source_health_status` unknown). Optional **`proposed_activation_notes`** from the request echo map to existing **`activation_notes`** when present.
- Flushes the row, reloads it by primary key, and records **pre** / **post** execution evidence, rollback-contract evidence, and **no-activation / no-side-pipeline** evidence flags.

## What the service does not do

- It does **not** activate the source, scrape, ingest, call external HTTP APIs, call LLMs, or create operator ledger actions.
- It does **not** run Alembic, create revisions, or change schema.
- It does **not** open its own database session; the caller passes **`db_session`**.

## Evidence contract

The returned dict includes **`pre_execution_evidence`**, **`post_execution_evidence`**, **`rollback_contract_evidence`**, **`no_activation_evidence`**, **`no_scrape_ingest_api_llm_ledger_evidence`**, **`forbidden_action_boundaries`**, **`sprint_61_execution_proof`**, and strict **`actual_*`** counters. On success, **`active_source_count_delta`** is **1**, **`actual_source_row_create_count`** / **`actual_source_row_insert_count`** / **`actual_database_write_count`** / **`actual_command_execution_count`** are **1**, and all forbidden pipeline counts remain **0**.

## Next sprint

After a successful evidence packet, the recommended **`next_allowed_step`** is **post-creation verification** and/or an **activation readiness gate** in a future sprint—still without automatic activation in Sprint 61.
