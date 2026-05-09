# NativeForge active source human approval intake (v1)

## Sprint 56 purpose

Sprint 56 introduces **`nf_active_source_human_approval_intake_v1`**, a deterministic, JSON-only artifact produced by **`build_active_source_human_approval_intake`** in `active_source_human_approval_intake_service.py`. It validates that a **human operator** has reviewed and formally acknowledged a **Sprint 55** **`nf_active_source_creation_request_v1`** package before any future sprint may plan **active source creation execution** (for example, a future dry-run command package for row creation).

## What this sprint does

- Consumes an optional Sprint 55 **source creation request** artifact and an optional **approval payload** (operator paperwork for a *future* source-creation sprint).
- Validates **completeness and consistency** of human approval fields, including Sprint 56 **acknowledgement booleans** that restate execution boundaries.
- Emits **`future_source_creation_authorization_preview`**: structured metadata and echoes only—**no executable SQL**, shell commands, or insert strings.

## What this sprint does not do

- **Does not** insert into **`nf_active_opportunity_sources`** or create registry rows.
- **Does not** activate sources or open activation paths.
- **Does not** scrape, ingest, call external APIs, call LLMs, or create operator ledger actions.
- **Does not** run Alembic, create revisions, or modify schema.
- **Does not** open database sessions from this builder; it is side-effect free.

Even when **`readiness_decision`** is **`ready_for_future_source_creation_sprint`** and **`approval_status`** matches, the artifact keeps **`may_create_source_rows_now`** and all other **`may_*_now`** flags **false**, and all **`actual_*`** execution counters at **zero**. Approval only **authorizes a future explicit source creation execution sprint** (for example, a dry-run package)—never immediate creation in Sprint 56.

## Discipline inherited from prior sprints

- **Sprint 54** empty-state read model discipline remains: this intake does not change ORM or table contents; it only references governance targets (`target_table`, `target_revision_id`).
- **Sprint 55** request-only discipline remains: the Sprint 55 artifact is still a **proposal**; Sprint 56 adds a **human approval paperwork layer** without mutating data.

## Readiness decisions

Deterministic values:

- **`not_ready`** — missing or invalid request artifact, request not at **`ready_for_human_source_creation_review`**, missing or incomplete approval payload, invalid acknowledgements, or weak **`approval_statement`** phrasing.
- **`blocked_requires_human_review`** — listed in **`governance_readiness_decision_values`** for governance vocabulary alignment; primary gating outcomes in Sprint 56 use **`not_ready`** until paperwork is complete.
- **`ready_for_future_source_creation_sprint`** — Sprint 55 artifact and approval payload are both structurally valid and consistent; next work belongs to a **future** source creation execution / dry-run sprint, not Sprint 56.

## Discovery integration

`build_discovery_source_quality` may embed **`active_source_human_approval_intake`** using **`build_discovery_read_only_active_source_human_approval_intake_attachment()`**, which invokes the builder with **no** request artifact and **no** approval payload. Operators therefore see a baseline **`not_ready`** snapshot unless a higher layer supplies explicit artifacts. The embedding **does not persist** and does not create operator actions.

## Next sprint

Sprint 56 sets up the **next sprint**: an **active source creation execution dry-run package** (governance-only planning for a future sprint), after human approval intake is **`ready_for_future_source_creation_sprint`**.
