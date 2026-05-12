# NativeForge active source activation execution plan review packet (v1)

## Sprint 71 purpose

Sprint 71 adds a deterministic, side-effect-free Python service that builds **`nf_active_source_activation_execution_plan_review_packet_v1`** artifacts. Each packet consumes a Sprint 70 **`nf_active_source_activation_human_authorization_decision_packet_v1`** artifact and records whether that decision context is **review-ready for future activation execution plan authoring** (documentation and guardrail posture only). It does **not** emit a runnable execution plan, authorize live activation, activate sources, create active source rows, execute `command_preview` entries, schedule activation, open database sessions, scrape, ingest, call external URLs or LLMs, write to the runtime database, mutate ledgers, or create Alembic revisions.

## Inputs

- **`human_authorization_decision_packet_artifact`**: output of `build_active_source_activation_human_authorization_decision_packet` (Sprint 70), type `nf_active_source_activation_human_authorization_decision_packet_v1`.

## Outputs

The execution plan review packet includes:

- **`artifact_type`**: `nf_active_source_activation_execution_plan_review_packet_v1`
- **`version`**: `v1`
- **`generated_at`**: fixed deterministic timestamp (`1970-01-01T00:00:00Z`) for reproducible artifacts
- **`human_authorization_decision_packet_reference`**: key fields copied from the Sprint 70 packet for traceability
- **`execution_plan_review_status`**: either `ready_for_future_activation_execution_plan_authoring_review` or `blocked_activation_execution_plan_review_packet` — never a statement that live activation is authorized, executed, scheduled, complete, active, running, or authorized for execution
- **`review_reasons`**, **`review_blockers`**: aligned lists explaining the outcome
- **`required_execution_plan_authoring_actions`**: operator-facing authoring steps; inherits Sprint 70 `required_human_decision_actions` handoffs when present
- **`required_pre_execution_guardrails`**: fixed guardrails that must hold before any future execution plan work outside this artifact
- **`prior_review_chain_summary`**: ordered summary starting with this packet, then entries from Sprint 70 `prior_review_chain_summary` when present
- **`guardrail_summary`**: structured comparison of Sprint 70 input guardrails versus Sprint 71 output posture (including **`no_runnable_plan`**)
- **`command_preview_summary`**, **`risk_and_rollback_summary`**: distilled from the Sprint 70 packet when structurally valid
- **`explicit_preview_only_no_execution_no_activation_no_runnable_plan_guardrail`**: explicit string guardrail for preview-only, no-execution, no-activation, no-runnable-plan posture
- **`future_activation_execution_plan_authoring_review_required`**: `true` only when the review status is the ready outcome (future execution plan authoring review gate), otherwise `false`
- **Guardrails**: top-level **`preview_only`**, **`no_execution`**, **`no_activation`**, **`no_runnable_plan`**, zero **`actual_*`** counts, false **`may_*`** flags, and Sprint 71 proof dict — consistent with prior NativeForge activation-review artifact posture

## Decision rules

- **Ready (for future activation execution plan authoring review only)** when the Sprint 70 decision packet is v1 with matching artifact type, declares **`preview_only`**, **`no_execution`**, **`no_activation`**, and **`future_activation_execution_plan_review_required`**, reports **`human_authorization_decision_status`** as `ready_for_future_activation_execution_plan_review`, carries a valid **`human_authorization_request_packet_reference`** to **`nf_active_source_activation_human_authorization_request_packet_v1`**, includes a non-empty **`explicit_preview_only_no_execution_no_activation_guardrail`** string with an explicit **`no_activation`** assertion (substring match), preserves zero **`actual_*`** counts with no true **`may_*`** flags on the Sprint 70 artifact, and contains no string values implying live authorization, executed activation, runnable shell-style command payloads (for example substrings such as `curl ` / `wget ` / `bash -c`), or “source is active” style activation language (see service constants).
- **Blocked** when any of the above fails — including malformed Sprint 70 output, missing guardrails, missing or inconsistent request packet reference, non-zero **`actual_*`** counts, true **`may_*`** flags on the decision artifact, or forbidden authorization/execution/activation-implied-live language embedded anywhere in the Sprint 70 artifact.

The strongest positive outcome remains **readiness for future activation execution plan authoring review**; runnable execution plans, live activation, scheduling, and execution still require separate workflows outside this artifact.

## Relationship to Sprint 70

Sprint 70 remains the explicit human authorization decision layer over Sprint 69. Sprint 71 consumes that decision packet locally and produces execution-plan authoring review context without changing runtime state.
