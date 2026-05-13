# NativeForge active source activation future execution authorization decision packet (v1)

## Sprint 79 purpose

Sprint 79 adds a deterministic, side-effect-free Python service that builds **`nf_active_source_activation_future_execution_authorization_decision_packet_v1`** artifacts. Each packet consumes a Sprint 78 **`nf_active_source_activation_future_execution_authorization_review_packet_v1`** artifact and records a **human authorize or deny decision** for the **next non-runnable execution planning gate** (documentation and decision record only).

Sprint 79 creates a **future execution authorization decision packet**. It consumes Sprint 78. It records a **human decision for the next non-runnable execution planning gate only**. It does **not** execute the plan. It does **not** activate sources. It does **not** create active source rows. It does **not** create commands. It does **not** scrape or ingest. It does **not** write runtime state. It is **deterministic** and **side-effect-free**.

A Sprint 79 authorization **only permits the next non-runnable planning packet**. A Sprint 79 authorization **does not permit live execution or source activation**.

It does **not** emit runnable shell commands, copy-paste runnable plans, `command_preview` payloads, scheduler instructions, worker payloads, SQL mutations, external URL fetches, database sessions, runtime database writes, ledger mutations, or Alembic revisions.

## Inputs

- **`future_execution_authorization_review_packet_artifact`**: output of `build_active_source_activation_future_execution_authorization_review_packet` (Sprint 78), type `nf_active_source_activation_future_execution_authorization_review_packet_v1`, with `artifact_version: 1` and semantic `version: "v1"` when present on the Sprint 78 artifact.
- **`human_future_execution_authorization_decision`**: one of the allowed string decision values (authorize or deny the future non-runnable execution planning gate only).
- **`human_future_execution_authorizer_identifier`** (optional): opaque reviewer identifier string when safe.
- **`human_future_execution_authorization_notes`** (optional): reviewer notes when safe.

## Outputs

The future execution authorization decision packet includes:

- **`artifact_type`**: `nf_active_source_activation_future_execution_authorization_decision_packet_v1`
- **`artifact_version`**: `1` (integer schema version for this artifact family)
- **`version`**: `v1` (string packet version, consistent with Sprint 78 and adjacent sprint artifacts)
- **`generated_at`**: fixed deterministic timestamp (`1970-01-01T00:00:00Z`) for reproducible artifacts
- **`source_sprint_78_future_execution_authorization_review_packet_reference`**: key fields copied from the Sprint 78 packet for traceability
- **`future_execution_authorization_decision_status`**: authorized-for-future-non-runnable-execution-planning-gate-only, denied-for-future-execution-planning-gate, or blocked — never a statement that live execution is allowed, that activation is allowed, or that source activation is authorized
- **`future_execution_authorization_decision_recorded`**, **`future_non_runnable_execution_planning_gate_authorized`**, **`future_execution_planning_gate_denied`**: aligned booleans for the decision outcome
- **`future_activation_execution_plan_execution_allowed`**, **`future_source_activation_allowed`**: always `false`
- **Top-level guardrails**: **`preview_only`**, **`no_execution`**, **`no_activation`**, **`no_runnable_plan`**, **`future_execution_authorization_decision_only`**
- **`next_gate_required`**: `future_non_runnable_execution_planning_packet` after a valid authorize decision; `none_until_future_execution_authorization_revisited` after a valid deny decision; `blocked_until_review_blockers_resolved` when blocked
- **`explicit_preview_only_no_execution_no_activation_no_runnable_plan_future_execution_authorization_decision_only_guardrail`**: explicit string guardrail including preview-only, no-execution, no-activation, no-runnable-plan, future-execution-authorization-decision-only, no-execution-performed, no-activation-performed, and no-runnable-command-created posture
- **`review_blockers`**: aligned list explaining a blocked outcome
- **`human_future_execution_authorization_decision`**, optional **`human_future_execution_authorizer_identifier`**, optional **`human_future_execution_authorization_notes`** (notes and identifier omitted when unsafe)
- **`source_execution_authorization_review_summary`**: compact summary of Sprint 78 execution-authorization review fields used for traceability
- **Guardrails**: zero **`actual_*`** counts, false **`may_*`** flags, and Sprint 79 proof dict — consistent with prior NativeForge activation-review artifact posture

## Decision rules

- **Authorized (for future non-runnable execution planning gate only)** when the Sprint 78 packet is fully valid and ready per Sprint 78 readiness rules for this gate, the human decision is the authorize string, no forbidden language appears in nested Sprint 78 strings or in optional human inputs, and all guardrails pass. This outcome **does not** authorize live execution; it only records permission to proceed to the **next non-runnable planning packet**.
- **Denied (for future execution planning gate)** when the Sprint 78 packet is fully valid and ready, the human decision is the deny string, inputs are safe, and all guardrails pass.
- **Blocked** when Sprint 78 input is missing or invalid, the human decision is missing or invalid, any required guardrail fails, or forbidden language appears anywhere in nested Sprint 78 string values or in optional authorization notes or identifier strings.

The strongest positive outcome after authorization remains **readiness for a separate future non-runnable execution planning packet**, not execution, activation, scraping, ingestion, scheduling, or runtime mutation.

## Relationship to Sprint 78

Sprint 78 remains the future execution authorization review packet layer over Sprint 77. Sprint 79 consumes that review packet locally and produces a human decision record for the next non-runnable planning gate without changing runtime state.
