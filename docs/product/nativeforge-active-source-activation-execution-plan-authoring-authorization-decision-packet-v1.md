# NativeForge active source activation execution plan authoring authorization decision packet (v1)

## Sprint 73 purpose

Sprint 73 adds a deterministic, side-effect-free Python service that builds **`nf_active_source_activation_execution_plan_authoring_authorization_decision_packet_v1`** artifacts. Each packet consumes a Sprint 72 **`nf_active_source_activation_execution_plan_authoring_authorization_request_packet_v1`** artifact and records whether that execution-plan-authoring authorization request context is **approved for future activation execution plan authoring** (documentation, review posture, human authorization decision recording, and guardrail proof only).

Sprint 73 creates an **authorization decision packet** for future activation execution plan authoring only. It consumes Sprint 72. It records a **decision posture only**. It does **not** author a plan. It does **not** create a runnable execution plan. It does **not** authorize execution. It does **not** activate sources. It does **not** execute commands. It is **review-only**, **preview-only**, **deterministic**, and **side-effect-free**. It prepares only the next gate: **future execution plan authoring**, not execution or activation.

It does **not** emit a runnable execution plan, execute `command_preview` entries, schedule activation, open database sessions, scrape, ingest, call external URLs or LLMs, write to the runtime database, mutate ledgers, or create Alembic revisions.

## Inputs

- **`execution_plan_authoring_authorization_request_packet_artifact`**: output of `build_active_source_activation_execution_plan_authoring_authorization_request_packet` (Sprint 72), type `nf_active_source_activation_execution_plan_authoring_authorization_request_packet_v1`, with `artifact_version: 1` and semantic `version: "v1"` when present.

## Outputs

The execution plan authoring authorization decision packet includes:

- **`artifact_type`**: `nf_active_source_activation_execution_plan_authoring_authorization_decision_packet_v1`
- **`artifact_version`**: `1` (integer schema version for this artifact family)
- **`version`**: `v1` (string packet version, consistent with Sprint 72 and adjacent sprint artifacts)
- **`generated_at`**: fixed deterministic timestamp (`1970-01-01T00:00:00Z`) for reproducible artifacts
- **`source_sprint_72_execution_plan_authoring_authorization_request_packet_reference`**: key fields copied from the Sprint 72 packet for traceability
- **`execution_plan_authoring_authorization_decision_status`**: either `approved_for_future_activation_execution_plan_authoring_only` or `blocked_execution_plan_authoring_authorization_decision_packet` — never a statement that live activation is authorized, executed, scheduled, complete, active, running, or authorized for execution
- **`approved_for_future_activation_execution_plan_authoring_only`**, **`future_activation_execution_plan_authoring_allowed`**: `true` only when the decision status is the approved outcome; **`future_activation_execution_plan_execution_allowed`** and **`future_source_activation_allowed`** are always `false`
- **`review_reasons`**, **`review_blockers`**: aligned lists explaining the outcome
- **`explicit_preview_only_no_execution_no_activation_no_runnable_plan_authorization_decision_only_guardrail`**: explicit string guardrail for preview-only, no-execution, no-activation, no-runnable-plan, authorization-decision-only, and future-plan-authoring-only posture
- **Guardrails**: top-level **`preview_only`**, **`no_execution`**, **`no_activation`**, **`no_runnable_plan`**, zero **`actual_*`** counts, false **`may_*`** flags, and Sprint 73 proof dict — consistent with prior NativeForge activation-review artifact posture

## Decision rules

- **Approved (for future activation execution plan authoring only)** when the Sprint 72 request packet is a dict with matching artifact type, **`artifact_version`** is `1`, **`version`** is `v1`, declares **`preview_only`**, **`no_execution`**, **`no_activation`**, **`no_runnable_plan`**, reports **`execution_plan_authoring_authorization_request_status`** as `ready_for_human_execution_plan_authoring_authorization_decision`, includes a non-empty **`explicit_preview_only_no_execution_no_activation_no_runnable_plan_authorization_request_only_guardrail`** string with explicit **`preview_only`**, **`no_execution`**, **`no_activation`**, **`no_runnable_plan`**, and **`authorization_request_only`** assertions (substring matches), preserves zero **`actual_*`** counts with no true **`may_*`** flags on the Sprint 72 artifact, and contains no string values implying live activation, executable plan, runnable shell-style command payloads, source activation complete, command execution, external calls, scraping, ingestion, scheduling, or production/runtime mutation (see service constants).
- **Blocked** when any of the above fails — including malformed Sprint 72 output, missing guardrails, non-zero **`actual_*`** counts, true **`may_*`** flags on the request artifact, or forbidden language embedded anywhere in the Sprint 72 artifact.

The strongest positive outcome remains **approval for future activation execution plan authoring posture only**; runnable execution plans, live activation, scheduling, and execution still require separate workflows outside this artifact.

## Relationship to Sprint 72

Sprint 72 remains the execution plan authoring authorization request layer over Sprint 71. Sprint 73 consumes that request packet locally and produces authorization-decision context for future plan authoring without changing runtime state.
