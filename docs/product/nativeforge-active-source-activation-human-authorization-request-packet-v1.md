# NativeForge active source activation human authorization request packet (v1)

## Sprint 69 purpose

Sprint 69 adds a deterministic, side-effect-free Python service that builds **`nf_active_source_activation_human_authorization_request_packet_v1`** artifacts. Each packet consumes a Sprint 68 **`nf_active_source_activation_authorization_readiness_packet_v1`** artifact and shapes the information a human operator would need for a **future** explicit human authorization workflow. It does **not** authorize activation, activate sources, create active source rows, execute `command_preview` entries, open database sessions, scrape, ingest, call external URLs or LLMs, write to the runtime database, mutate ledgers, or run Alembic.

## Inputs

- **`authorization_readiness_packet_artifact`**: output of `build_active_source_activation_authorization_readiness_packet` (Sprint 68), type `nf_active_source_activation_authorization_readiness_packet_v1`.

## Outputs

The human authorization request packet includes:

- **`artifact_type`**: `nf_active_source_activation_human_authorization_request_packet_v1`
- **`version`**: `v1`
- **`generated_at`**: fixed deterministic timestamp (`1970-01-01T00:00:00Z`) for reproducible artifacts
- **`authorization_readiness_packet_reference`**: key fields copied from the Sprint 68 packet for traceability
- **`human_authorization_request_status`**: either `ready_for_future_explicit_human_authorization_request_review` or `blocked_human_authorization_request_packet_review` — never a statement that live activation is authorized, approved, executed, scheduled, or complete
- **`request_reasons`**, **`request_blockers`**: aligned lists explaining the outcome
- **`required_human_review_actions`**: operator-facing review steps; inherits Sprint 68 `required_human_authorization_actions` handoffs when present
- **`required_human_acknowledgements`**: fixed acknowledgements that this artifact is request-context only
- **`prior_review_chain_summary`**: ordered summary starting with this packet, then entries from Sprint 68 `prior_review_chain` when present
- **`guardrail_summary`**: structured comparison of Sprint 68 input guardrails versus Sprint 69 output posture
- **`command_preview_summary`**, **`risk_and_rollback_summary`**: distilled from the Sprint 68 packet when structurally valid
- **Guardrails**: top-level **`preview_only`**, **`no_execution`**, **`no_authorization`**, **`no_activation`**, **`explicit_preview_only_no_execution_no_authorization_no_activation_guardrail`**, **`future_explicit_human_authorization_required`**, zero **`actual_*`** counts, false **`may_*`** flags, and Sprint 69 proof dict — consistent with prior NativeForge activation-review artifact posture

## Decision rules

- **Ready (for future explicit human authorization request review only)** when the authorization readiness packet is Sprint 68 v1, declares **`preview_only`**, **`no_execution`**, **`no_authorization`**, and **`future_human_authorization_required`**, carries an **`explicit_preview_only_no_execution_no_authorization_guardrail`** string that includes an explicit **`no_activation`** assertion (substring match), reports **`authorization_readiness`** as `ready_for_future_human_authorization_packet_review`, includes a valid **`operator_decision_review_reference`** to **`nf_active_source_activation_operator_decision_review_v1`** with **`operator_decision`** `ready_for_future_activation_authorization_review`, preserves zero **`actual_*`** counts with no true **`may_*`** flags on the Sprint 68 artifact, and contains no string values implying live authorization or executed activation (see service constants).
- **Blocked** when any of the above fails — including blocked or malformed Sprint 68 output, missing guardrails, missing or inconsistent operator decision review reference, non-zero **`actual_*`** counts, true **`may_*`** flags on the readiness artifact, or forbidden authorization/execution language embedded anywhere in the Sprint 68 artifact.

The strongest positive outcome remains **readiness for future explicit human authorization request review**; live activation and authorization still require separate workflows outside this artifact.

## Relationship to Sprint 68

Sprint 68 remains the authorization-readiness alignment layer over Sprint 67. Sprint 69 consumes that readiness packet locally and produces human-facing request context without changing runtime state.
