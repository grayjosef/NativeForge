# NativeForge active source activation human authorization decision packet (v1)

## Sprint 70 purpose

Sprint 70 adds a deterministic, side-effect-free Python service that builds **`nf_active_source_activation_human_authorization_decision_packet_v1`** artifacts. Each packet consumes a Sprint 69 **`nf_active_source_activation_human_authorization_request_packet_v1`** artifact and records whether that request context is **review-ready for a future activation execution plan review**. It does **not** authorize live activation, activate sources, create active source rows, execute `command_preview` entries, open database sessions, scrape, ingest, call external URLs or LLMs, write to the runtime database, mutate ledgers, or create Alembic revisions.

## Inputs

- **`human_authorization_request_packet_artifact`**: output of `build_active_source_activation_human_authorization_request_packet` (Sprint 69), type `nf_active_source_activation_human_authorization_request_packet_v1`.

## Outputs

The human authorization decision packet includes:

- **`artifact_type`**: `nf_active_source_activation_human_authorization_decision_packet_v1`
- **`version`**: `v1`
- **`generated_at`**: fixed deterministic timestamp (`1970-01-01T00:00:00Z`) for reproducible artifacts
- **`human_authorization_request_packet_reference`**: key fields copied from the Sprint 69 packet for traceability
- **`human_authorization_decision_status`**: either `ready_for_future_activation_execution_plan_review` or `blocked_human_authorization_decision_packet_review` — never a statement that live activation is authorized, executed, scheduled, complete, active, or running
- **`decision_reasons`**, **`decision_blockers`**: aligned lists explaining the outcome
- **`required_human_decision_actions`**: operator-facing steps; inherits Sprint 69 `required_human_review_actions` handoffs when present
- **`required_human_acknowledgements`**: fixed acknowledgements that this artifact is decision-context only and not activation
- **`prior_review_chain_summary`**: ordered summary starting with this packet, then entries from Sprint 69 `prior_review_chain_summary` when present
- **`guardrail_summary`**: structured comparison of Sprint 69 input guardrails versus Sprint 70 output posture
- **`command_preview_summary`**, **`risk_and_rollback_summary`**: distilled from the Sprint 69 packet when structurally valid
- **`explicit_preview_only_no_execution_no_activation_guardrail`**: explicit string guardrail for preview-only, no-execution, no-activation posture
- **`explicit_authorization_decision_recorded`**: `false` unless the input carries the explicit Sprint 70 marker key/value pair reserved for recorded-decision testing and integration contracts
- **`future_activation_execution_plan_review_required`**: `true` only when the decision status is the ready outcome (future execution plan review gate), otherwise `false`
- **Guardrails**: top-level **`preview_only`**, **`no_execution`**, **`no_authorization`**, **`no_activation`**, **`future_explicit_human_authorization_required`**, zero **`actual_*`** counts, false **`may_*`** flags, and Sprint 70 proof dict — consistent with prior NativeForge activation-review artifact posture

## Decision rules

- **Ready (for future activation execution plan review only)** when the Sprint 69 request packet is v1 with matching artifact type, declares **`preview_only`**, **`no_execution`**, **`no_authorization`**, **`no_activation`**, and **`future_explicit_human_authorization_required`**, carries the Sprint 69 explicit four-part guardrail string including an explicit **`no_activation`** assertion (substring match), reports **`human_authorization_request_status`** as `ready_for_future_explicit_human_authorization_request_review`, includes a valid **`authorization_readiness_packet_reference`** to **`nf_active_source_activation_authorization_readiness_packet_v1`** `v1`, preserves zero **`actual_*`** counts with no true **`may_*`** flags on the Sprint 69 artifact, and contains no string values implying live authorization, executed activation, or “source is active” style activation language (see service constants).
- **Blocked** when any of the above fails — including malformed Sprint 69 output, missing guardrails, missing or inconsistent readiness reference, non-zero **`actual_*`** counts, true **`may_*`** flags on the request artifact, or forbidden authorization/execution/activation-implied-live language embedded anywhere in the Sprint 69 artifact.

The strongest positive outcome remains **readiness for future activation execution plan review**; live activation, scheduling, and execution still require separate workflows outside this artifact.

## Relationship to Sprint 69

Sprint 69 remains the human authorization request layer over Sprint 68. Sprint 70 consumes that request packet locally and produces explicit decision review context without changing runtime state.
