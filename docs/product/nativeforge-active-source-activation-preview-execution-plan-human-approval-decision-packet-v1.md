# NativeForge active source activation preview execution plan human approval decision packet (v1)

## Sprint 77 purpose

Sprint 77 adds a deterministic, side-effect-free Python service that builds **`nf_active_source_activation_preview_execution_plan_human_approval_decision_packet_v1`** artifacts. Each packet consumes a Sprint 76 **`nf_active_source_activation_preview_execution_plan_draft_review_packet_v1`** artifact and records a **human approval or denial decision** for that preview-only, non-runnable execution plan draft review posture (documentation and decision record only).

Sprint 77 creates a **preview execution plan human approval decision packet**. It consumes Sprint 76. It records a **human approval or denial decision only**. It does **not** execute the plan. It does **not** activate sources. It does **not** create active source rows. It does **not** create commands. It does **not** scrape or ingest. It does **not** write runtime state. It is **deterministic** and **side-effect-free**. Approval only prepares the next gate: **future execution authorization review**, not execution or activation.

It does **not** emit runnable shell commands, copy-paste runnable plans, `command_preview` payloads, scheduler instructions, worker payloads, SQL mutations, external URL fetches, database sessions, runtime database writes, ledger mutations, or Alembic revisions.

## Inputs

- **`preview_execution_plan_draft_review_packet_artifact`**: output of `build_active_source_activation_preview_execution_plan_draft_review_packet` (Sprint 76), type `nf_active_source_activation_preview_execution_plan_draft_review_packet_v1`, with `artifact_version: 1` and semantic `version: "v1"` when present on the Sprint 76 artifact.
- **`human_approval_decision`**: one of the allowed string decision values (approve or deny for future execution authorization review posture only).
- **`human_approver_identifier`** (optional): opaque reviewer identifier string when safe.
- **`human_approval_notes`** (optional): reviewer notes when safe.

## Outputs

The human approval decision packet includes:

- **`artifact_type`**: `nf_active_source_activation_preview_execution_plan_human_approval_decision_packet_v1`
- **`artifact_version`**: `1` (integer schema version for this artifact family)
- **`version`**: `v1` (string packet version, consistent with Sprint 76 and adjacent sprint artifacts)
- **`generated_at`**: fixed deterministic timestamp (`1970-01-01T00:00:00Z`) for reproducible artifacts
- **`source_sprint_76_preview_execution_plan_draft_review_packet_reference`**: key fields copied from the Sprint 76 packet for traceability
- **`preview_execution_plan_human_approval_decision_status`**: approved-for-future-execution-authorization-review-only, denied-for-future-execution-authorization-review, or blocked — never a statement that live activation is authorized, executed, scheduled, complete, active, running, or authorized for execution
- **`preview_execution_plan_human_approval_decision_recorded`**, **`preview_execution_plan_human_approved_for_future_execution_authorization_review`**, **`preview_execution_plan_human_denied_for_future_execution_authorization_review`**, **`future_execution_authorization_review_required`**: aligned booleans for the decision outcome (the future execution authorization review gate is in scope only after a valid approve decision on a valid Sprint 76 ready packet)
- **`future_activation_execution_plan_execution_allowed`**, **`future_source_activation_allowed`**: always `false`
- **Top-level guardrails**: **`preview_only`**, **`no_execution`**, **`no_activation`**, **`no_runnable_plan`**, **`human_approval_decision_only`**, **`future_execution_gate_required`**
- **`next_gate_required`**: `future_execution_authorization_review_packet` after a valid approve decision; `none_until_preview_draft_revised` after a valid deny decision; `blocked_until_review_blockers_resolved` when blocked
- **`explicit_preview_only_no_execution_no_activation_no_runnable_plan_human_approval_decision_only_guardrail`**: explicit string guardrail including preview-only, no-execution, no-activation, no-runnable-plan, human-approval-decision-only, future-execution-gate-required, and no-activation-without-separate-future-execution-authorization posture
- **`review_blockers`**: aligned list explaining a blocked outcome
- **`human_approval_decision`**, optional **`human_approver_identifier`**, optional **`human_approval_notes`** (notes and identifier omitted when unsafe)
- **Guardrails**: zero **`actual_*`** counts, false **`may_*`** flags, and Sprint 77 proof dict — consistent with prior NativeForge activation-review artifact posture

## Decision rules

- **Approved (for future execution authorization review only)** when the Sprint 76 packet is fully valid and ready per Sprint 76 readiness rules, the human decision is the approve string, no forbidden language appears in nested Sprint 76 strings or in optional human inputs, and all guardrails pass.
- **Denied (for future execution authorization review)** when the Sprint 76 packet is fully valid and ready, the human decision is the deny string, inputs are safe, and all guardrails pass.
- **Blocked** when Sprint 76 input is missing or invalid, the human decision is missing or invalid, any required guardrail fails, or forbidden language appears anywhere in nested Sprint 76 string values or in optional human approval notes or identifier strings.

The strongest positive outcome after approval remains **readiness for a separate future execution authorization review packet**, not execution, activation, scraping, ingestion, scheduling, or runtime mutation.

## Relationship to Sprint 76

Sprint 76 remains the preview execution plan draft review packet layer over Sprint 75. Sprint 77 consumes that draft review packet locally and produces a human decision record for a future execution authorization gate without changing runtime state.
