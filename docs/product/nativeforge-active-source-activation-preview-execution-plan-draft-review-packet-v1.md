# NativeForge active source activation preview execution plan draft review packet (v1)

## Sprint 76 purpose

Sprint 76 adds a deterministic, side-effect-free Python service that builds **`nf_active_source_activation_preview_execution_plan_draft_review_packet_v1`** artifacts. Each packet consumes a Sprint 75 **`nf_active_source_activation_preview_execution_plan_draft_packet_v1`** artifact and records whether that preview-only, non-runnable execution plan draft is ready for a **future human approval gate** (documentation and review posture only).

Sprint 76 creates a **preview execution plan draft review packet**. It consumes Sprint 75. It reviews a **non-runnable human-review draft only**. It does **not** execute the plan. It does **not** activate sources. It does **not** create active source rows. It does **not** create commands. It does **not** scrape or ingest. It does **not** write runtime state. It is **deterministic** and **side-effect-free**. It prepares only the next gate: **human approval decision for the preview draft**, not execution or activation.

It does **not** emit runnable shell commands, copy-paste runnable plans, `command_preview` payloads, scheduler instructions, worker payloads, SQL mutations, external URL fetches, database sessions, runtime database writes, ledger mutations, or Alembic revisions.

## Inputs

- **`preview_execution_plan_draft_packet_artifact`**: output of `build_active_source_activation_preview_execution_plan_draft_packet` (Sprint 75), type `nf_active_source_activation_preview_execution_plan_draft_packet_v1`, with `artifact_version: 1` and semantic `version: "v1"` when present on the Sprint 75 artifact.

## Outputs

The preview execution plan draft review packet includes:

- **`artifact_type`**: `nf_active_source_activation_preview_execution_plan_draft_review_packet_v1`
- **`artifact_version`**: `1` (integer schema version for this artifact family)
- **`version`**: `v1` (string packet version, consistent with Sprint 75 and adjacent sprint artifacts)
- **`generated_at`**: fixed deterministic timestamp (`1970-01-01T00:00:00Z`) for reproducible artifacts
- **`source_sprint_75_preview_execution_plan_draft_packet_reference`**: key fields copied from the Sprint 75 packet for traceability
- **`preview_execution_plan_draft_review_status`**: either `ready_for_future_human_preview_execution_plan_approval_review` or `blocked_preview_execution_plan_draft_review_packet` — never a statement that live activation is authorized, executed, scheduled, complete, active, running, or authorized for execution
- **`preview_execution_plan_draft_review_ready`**, **`future_human_preview_execution_plan_approval_required`**: readiness flags aligned with the review outcome (the future human approval decision gate is in scope only when the Sprint 75 draft packet is fully valid and safe to review as documentation)
- **`future_activation_execution_plan_execution_allowed`**, **`future_source_activation_allowed`**: always `false`
- **Top-level guardrails**: **`preview_only`**, **`no_execution`**, **`no_activation`**, **`no_runnable_plan`**, **`non_runnable_review_only`**, **`human_approval_required`**
- **`next_gate_required`**: always `future_human_preview_execution_plan_approval_decision_packet` for this artifact family (the next intended gate is a human approval decision packet, not execution or activation)
- **`explicit_preview_only_no_execution_no_activation_no_runnable_plan_non_runnable_review_only_guardrail`**: explicit string guardrail including preview-only, no-execution, no-activation, no-runnable-plan, non-runnable-review-only, human-approval-required, and future-human-approval-required-before-any-activation posture
- **`draft_field_review_results`**: deterministic per-field pass/fail details for Sprint 75 descriptive draft sections
- **`review_reasons`**, **`review_blockers`**: aligned lists explaining the outcome
- **Guardrails**: zero **`actual_*`** counts, false **`may_*`** flags, and Sprint 76 proof dict — consistent with prior NativeForge activation-review artifact posture

## Review rules

- **Ready (for future human preview execution plan approval review only)** when the Sprint 75 draft packet is a dict with matching artifact type, **`artifact_version`** is `1`, declares **`preview_only`**, **`no_execution`**, **`no_activation`**, **`no_runnable_plan`**, **`non_runnable_draft_only`**, **`human_review_required`**, reports **`preview_execution_plan_draft_status`** as `drafted_for_human_review_only`, sets **`preview_execution_plan_draft_created`** and **`preview_execution_plan_draft_human_review_required`** to `true`, keeps **`future_activation_execution_plan_execution_allowed`** and **`future_source_activation_allowed`** false, preserves zero **`actual_*`** counts with no true **`may_*`** flags on the Sprint 75 artifact, includes a non-empty Sprint 75 explicit non-runnable draft guardrail string with required assertions (including **`future_human_approval_required_before_any_activation`**), contains Sprint 75’s deterministic descriptive draft fields unchanged, contains no forbidden live-activation/runnable-command/automation language embedded anywhere in nested string values (see service constants), and each draft field passes non-runnable and later-human-approval posture checks without URL-like substrings or risky shell-operator substrings.
- **Blocked** when any of the above fails — including malformed Sprint 75 output, missing guardrails, non-zero **`actual_*`** counts, true **`may_*`** flags on the Sprint 75 artifact, forbidden language embedded anywhere in the Sprint 75 artifact, draft field mismatch with Sprint 75 deterministic drafting, or per-field posture validation failures.

The strongest positive outcome remains **readiness for a future human approval decision review of a preview-only, non-runnable draft packet**. Execution, activation, scraping, ingestion, scheduling, and runtime mutation still require separate workflows outside this artifact.

## Relationship to Sprint 75

Sprint 75 remains the preview-only execution plan draft packet layer over Sprint 74. Sprint 76 consumes that draft packet locally and produces review posture for a future human approval decision gate without changing runtime state.
