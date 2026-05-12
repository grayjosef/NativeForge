# NativeForge active source activation execution plan authoring authorization request packet (v1)

## Sprint 72 purpose

Sprint 72 adds a deterministic, side-effect-free Python service that builds **`nf_active_source_activation_execution_plan_authoring_authorization_request_packet_v1`** artifacts. Each packet consumes a Sprint 71 **`nf_active_source_activation_execution_plan_review_packet_v1`** artifact and records whether that execution-plan-review context is **ready for a future human authorization decision about authoring** an activation execution plan (documentation and guardrail posture only).

Sprint 72 creates an **authorization request packet** for that future execution plan authoring authorization decision. It does **not** author a plan. It does **not** authorize execution. It does **not** activate sources. It does **not** execute commands. It is **review-only**, **preview-only**, **deterministic**, and **side-effect-free**. It consumes Sprint 71 and prepares only the next human authorization decision gate.

It does **not** emit a runnable execution plan, execute `command_preview` entries, schedule activation, open database sessions, scrape, ingest, call external URLs or LLMs, write to the runtime database, mutate ledgers, or create Alembic revisions.

## Inputs

- **`execution_plan_review_packet_artifact`**: output of `build_active_source_activation_execution_plan_review_packet` (Sprint 71), type `nf_active_source_activation_execution_plan_review_packet_v1`, semantic version carried as `version: "v1"` (and optional `artifact_version: 1` when present).

## Outputs

The execution plan authoring authorization request packet includes:

- **`artifact_type`**: `nf_active_source_activation_execution_plan_authoring_authorization_request_packet_v1`
- **`artifact_version`**: `1` (integer schema version for this artifact family)
- **`version`**: `v1` (string packet version, consistent with adjacent sprint artifacts)
- **`generated_at`**: fixed deterministic timestamp (`1970-01-01T00:00:00Z`) for reproducible artifacts
- **`execution_plan_review_packet_reference`**: key fields copied from the Sprint 71 packet for traceability
- **`execution_plan_authoring_authorization_request_status`**: either `ready_for_human_execution_plan_authoring_authorization_decision` or `blocked_execution_plan_authoring_authorization_request_packet` — never a statement that live activation is authorized, executed, scheduled, complete, active, running, or authorized for execution
- **`review_reasons`**, **`review_blockers`**: aligned lists explaining the outcome
- **`required_authorization_request_actions`**: operator-facing handoffs; inherits Sprint 71 `required_execution_plan_authoring_actions` entries when present
- **`required_pre_authorization_guardrails`**: fixed guardrails that must hold before any future plan-authoring authorization work outside this artifact
- **`prior_review_chain_summary`**: ordered summary starting with this packet, then entries from Sprint 71 `prior_review_chain_summary` when present
- **`guardrail_summary`**: structured comparison of Sprint 71 input guardrails versus Sprint 72 output posture (including **`authorization_request_only`**)
- **`command_preview_summary`**, **`risk_and_rollback_summary`**: distilled from the Sprint 71 packet when structurally valid
- **`explicit_preview_only_no_execution_no_activation_no_runnable_plan_authorization_request_only_guardrail`**: explicit string guardrail for preview-only, no-execution, no-activation, no-runnable-plan, and authorization-request-only posture
- **`future_human_execution_plan_authoring_authorization_decision_required`**: `true` only when the request status is the ready outcome (future human authorization decision gate for plan authoring), otherwise `false`
- **Guardrails**: top-level **`preview_only`**, **`no_execution`**, **`no_activation`**, **`no_runnable_plan`**, zero **`actual_*`** counts, false **`may_*`** flags, and Sprint 72 proof dict — consistent with prior NativeForge activation-review artifact posture

## Decision rules

- **Ready (for a future human execution plan authoring authorization decision only)** when the Sprint 71 review packet is a dict with matching artifact type, `version` is `v1`, any present **`artifact_version`** is `1`, declares **`preview_only`**, **`no_execution`**, **`no_activation`**, **`no_runnable_plan`**, and **`future_activation_execution_plan_authoring_review_required`**, reports **`execution_plan_review_status`** as `ready_for_future_activation_execution_plan_authoring_review`, includes a non-empty **`explicit_preview_only_no_execution_no_activation_no_runnable_plan_guardrail`** string with explicit **`no_activation`** and **`no_runnable_plan`** assertions (substring matches), preserves zero **`actual_*`** counts with no true **`may_*`** flags on the Sprint 71 artifact, and contains no string values implying live authorization, executed activation, runnable shell-style command payloads (for example substrings such as `curl ` / `wget ` / `bash -c`), or “source is active” style activation language (see service constants).
- **Blocked** when any of the above fails — including malformed Sprint 71 output, missing guardrails, non-zero **`actual_*`** counts, true **`may_*`** flags on the review artifact, or forbidden authorization/execution/activation-implied-live language embedded anywhere in the Sprint 71 artifact.

The strongest positive outcome remains **readiness for a future human authorization decision about execution plan authoring**; runnable execution plans, live activation, scheduling, and execution still require separate workflows outside this artifact.

## Relationship to Sprint 71

Sprint 71 remains the execution plan authoring review layer over Sprint 70. Sprint 72 consumes that review packet locally and produces authorization-request context for a future human decision without changing runtime state.
