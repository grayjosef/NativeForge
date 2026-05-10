# NativeForge active source activation authorization readiness packet (v1)

## Sprint 68 purpose

Sprint 68 adds a deterministic, side-effect-free Python service that builds **`nf_active_source_activation_authorization_readiness_packet_v1`** artifacts. Each packet summarizes whether a Sprint 67 **`nf_active_source_activation_operator_decision_review_v1`** artifact is aligned with prior preview-only review layers so a **future** human authorization workflow can review an authorization packet later. It does **not** authorize activation, activate sources, create active source rows, execute `command_preview` entries, open database sessions, scrape, ingest, call external URLs or LLMs, write to the runtime database, mutate ledgers, or run Alembic.

## Inputs

- **`operator_decision_review_artifact`**: output of `build_active_source_activation_operator_decision_review` (Sprint 67), type `nf_active_source_activation_operator_decision_review_v1`.

## Outputs

The authorization readiness packet includes:

- **`artifact_type`**: `nf_active_source_activation_authorization_readiness_packet_v1`
- **`version`**: `v1`
- **`generated_at`**: fixed deterministic timestamp (`1970-01-01T00:00:00Z`) for reproducible artifacts
- **`operator_decision_review_reference`**: key fields copied from the Sprint 67 review for traceability
- **`authorization_readiness`**: either `ready_for_future_human_authorization_packet_review` or `blocked_authorization_readiness_packet_review` — never a statement that live activation is authorized, approved, executed, or scheduled
- **`readiness_reasons`**, **`authorization_blockers`**: aligned lists explaining the outcome
- **`required_human_authorization_actions`**: reminders that this artifact is readiness-only and defers to a separate human authorization workflow
- **`prior_review_chain`**: ordered summary linking this packet to Sprint 67 and the Sprint 66 command package reference carried on the review
- **`guardrail_review`**: structured comparison of input guardrails versus output posture
- **`command_preview_summary`**: distilled fields from Sprint 67 `command_preview_review` when present
- **`risk_and_rollback_summary`**: distilled notes from Sprint 67 risk and rollback reviews plus packet-level caveats
- **Guardrails**: top-level **`preview_only`**, **`no_execution`**, **`no_authorization`**, **`explicit_preview_only_no_execution_no_authorization_guardrail`**, **`future_human_authorization_required`**, zero **`actual_*`** counts, false **`may_*`** flags, and Sprint 68 proof dict — consistent with prior NativeForge activation-review artifact posture

## Decision rules

- **Ready (for future human authorization packet review only)** when the operator decision review is Sprint 67 v1, declares **`preview_only`**, **`no_execution`**, and **`future_authorization_required`**, carries a non-empty **`explicit_preview_only_no_execution_guardrail`**, reports **`operator_decision`** as `ready_for_future_activation_authorization_review`, includes a valid **`command_package_reference`** to **`nf_active_source_activation_command_package_v1`** v1 with readiness `ready_activation_command_package_preview_scaffold`, includes a dict **`command_preview_review`**, preserves zero **`actual_*`** counts with no true **`may_*`** flags, and contains no string values implying live authorization or executed activation (see service constants).
- **Blocked** when any of the above fails — including a blocked Sprint 67 operator decision, malformed artifact, missing guardrails, missing or inconsistent command package reference, non-zero **`actual_*`** counts, true **`may_*`** flags, or forbidden authorization/execution language embedded in the Sprint 67 artifact.

The strongest positive outcome remains **readiness for a future human authorization packet review**; live activation and authorization still require separate workflows outside this artifact.

## Relationship to Sprint 67

Sprint 67 remains the operator-facing decision review over the Sprint 66 preview command package. Sprint 68 consumes that review locally and produces an authorization-readiness alignment packet without changing runtime state.
