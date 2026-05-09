# NativeForge active source creation execution readiness gate (v1)

## Sprint 58 purpose

This sprint adds **`nf_active_source_creation_execution_readiness_gate_v1`**, a deterministic, JSON-only readiness gate that decides whether a **future** governed sprint may perform the first controlled **`nf_active_opportunity_sources`** row creation.

The gate **consumes**:

- **Sprint 55** — `nf_active_source_creation_request_v1` (`readiness_decision`: `ready_for_human_source_creation_review`, `request_status` aligned, `future_insert_preview` preview-only).
- **Sprint 56** — `nf_active_source_human_approval_intake_v1` (`readiness_decision`: `ready_for_future_source_creation_sprint`, `approval_status` aligned, `future_source_creation_authorization_preview` preview-only).
- **Sprint 57** — `nf_active_source_creation_execution_dry_run_v1` (`readiness_decision`: `ready_for_future_source_creation_execution_sprint`, `dry_run_status` aligned, `dry_run_insert_preview` preview-only, all top-level `may_*` flags false).

It also accepts **`runtime_preconditions`**: a caller-supplied map of boolean observations. The builder **does not** open a database session or inspect live catalog state.

## What Sprint 58 does *not* do

- Does **not** insert, update, delete, or seed **`nf_active_opportunity_sources`** rows.
- Does **not** activate sources or expose activation commands.
- Does **not** scrape, ingest, call external HTTP/API clients, or call LLMs.
- Does **not** create operator ledger actions or persist governance payloads.
- Does **not** apply or roll back Alembic revisions or mutate schema.
- Does **not** emit executable SQL `INSERT` strings or shell / Alembic invocation fragments as live commands.

Even when **`readiness_decision`** is **`ready_for_future_source_creation_execution`**, **`may_create_source_rows_now`** and related **`may_*`** execution flags remain **`false`**. A **readiness** outcome only authorizes scheduling a **later** explicit execution sprint (command package or controlled execution plan).

## Readiness outcomes

Deterministic values:

- **`not_ready`** — missing or invalid upstream artifacts, invalid Sprint 57 dry-run semantics (including forbidden `may_*` on the dry-run artifact), missing or incomplete **`runtime_preconditions`**, or required precondition booleans not satisfied.
- **`blocked_requires_human_review`** — upstream artifacts and precondition map are structurally complete but **`duplicate_source_found`** is **`true`** in **`runtime_preconditions`**.
- **`ready_for_future_source_creation_execution`** — all three upstream artifacts are valid and aligned, runtime preconditions are complete with every required **`true`** flag set and **`duplicate_source_found`** explicitly **`false`**.

## Discipline with Sprints 54–57

Sprint 58 **preserves** the empty-state / request / human approval / execution dry-run posture: it is a **governance compositor** only. It continues the pattern that **preview** and **authorization preview** objects are metadata for operators and must not be treated as executable plans by themselves.

## Operator integration

**`build_discovery_source_quality`** may embed **`active_source_creation_execution_readiness_gate`** via **`build_discovery_read_only_active_source_creation_execution_readiness_gate_attachment()`**, which invokes the gate with **no** upstream artifacts and **no** runtime map. Operators therefore see a default **`not_ready`** snapshot unless a higher layer supplies explicit inputs. Embedding is **read-only** and non-persisting.

## Next sprint

After Sprint 58, the logical successor is an **active source creation execution command package** or **first controlled execution plan** sprint that consumes this gate artifact while still honoring Sprint 58 execution boundaries.
