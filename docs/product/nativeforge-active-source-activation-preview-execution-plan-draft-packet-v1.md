# NativeForge active source activation preview execution plan draft packet (v1)

## Sprint 75 purpose

Sprint 75 adds a deterministic, side-effect-free Python service that builds **`nf_active_source_activation_preview_execution_plan_draft_packet_v1`** artifacts. Each packet consumes a Sprint 74 **`nf_active_source_activation_execution_plan_authoring_review_packet_v1`** artifact and emits a **preview-only, non-runnable, human-review draft** of descriptive planning context for a future activation execution plan posture.

Sprint 75 creates a **preview execution plan draft packet** for human review only. It consumes Sprint 74. It emits **descriptive prose sections only** (non-runnable, not mechanically actionable). It does **not** execute the plan. It does **not** activate sources. It does **not** create active source rows. It does **not** create commands or command previews. It does **not** scrape or ingest. It does **not** write runtime state. It is **deterministic** and **side-effect-free**. It prepares only the next gate: **human review of the preview draft**, not execution or activation.

It does **not** emit runnable shell commands, copy-paste runnable plans, `command_preview` payloads, scheduler instructions, worker payloads, SQL mutations, external URL fetches, database sessions, runtime database writes, ledger mutations, or Alembic revisions.

## Inputs

- **`execution_plan_authoring_review_packet_artifact`**: output of `build_active_source_activation_execution_plan_authoring_review_packet` (Sprint 74), type `nf_active_source_activation_execution_plan_authoring_review_packet_v1`, with `artifact_version: 1` and semantic `version: "v1"` when present on the Sprint 74 artifact.

## Outputs

The preview execution plan draft packet includes:

- **`artifact_type`**: `nf_active_source_activation_preview_execution_plan_draft_packet_v1`
- **`artifact_version`**: `1` (integer schema version for this artifact family)
- **`version`**: `v1` (string packet version, consistent with Sprint 74 and adjacent sprint artifacts)
- **`generated_at`**: fixed deterministic timestamp (`1970-01-01T00:00:00Z`) for reproducible artifacts
- **`source_sprint_74_execution_plan_authoring_review_packet_reference`**: key fields copied from the Sprint 74 packet for traceability
- **`preview_execution_plan_draft_status`**: either `drafted_for_human_review_only` or `blocked_preview_execution_plan_draft_packet` — never a statement that live activation is authorized, executed, scheduled, complete, active, running, or authorized for execution
- **`preview_execution_plan_draft_created`**, **`preview_execution_plan_draft_human_review_required`**: `draft_created` is `true` only when the Sprint 74 input satisfies all Sprint 75 readiness checks; human review remains required for any emitted draft posture
- **`future_activation_execution_plan_execution_allowed`**, **`future_source_activation_allowed`**: always `false`
- **Top-level guardrails**: **`preview_only`**, **`no_execution`**, **`no_activation`**, **`no_runnable_plan`**, **`non_runnable_draft_only`**, **`human_review_required`**
- **`explicit_preview_only_no_execution_no_activation_no_runnable_plan_non_runnable_draft_only_guardrail`**: explicit string guardrail including preview-only, no-execution, no-activation, no-runnable-plan, non-runnable-draft-only, human-review-required, and future-human-approval-required-before-any-activation posture
- **Descriptive draft fields** (non-runnable prose): **`activation_scope_summary`**, **`pre_activation_human_review_checklist`**, **`non_runnable_sequence_outline`**, **`required_evidence_before_activation`**, **`source_safety_controls_to_verify`**, **`rollback_and_stop_conditions_summary`**, **`operator_review_notes_template`**, **`next_gate_required`**
- **`review_reasons`**, **`review_blockers`**: aligned lists explaining the outcome
- **Guardrails**: zero **`actual_*`** counts, false **`may_*`** flags, and Sprint 75 proof dict — consistent with prior NativeForge activation-review artifact posture

## Drafting rules

- **Drafted (for human review only)** when the Sprint 74 review packet is a dict with matching artifact type, **`artifact_version`** is `1`, declares **`preview_only`**, **`no_execution`**, **`no_activation`**, **`no_runnable_plan`**, reports **`execution_plan_authoring_review_status`** as `ready_for_future_preview_only_execution_plan_drafting_review`, sets **`future_preview_only_execution_plan_drafting_review_required`** and **`future_activation_execution_plan_authoring_context_ready`** to `true`, keeps **`future_activation_execution_plan_execution_allowed`** and **`future_source_activation_allowed`** false, preserves zero **`actual_*`** counts with no true **`may_*`** flags on the Sprint 74 artifact, includes a non-empty **`explicit_preview_only_no_execution_no_activation_no_runnable_plan_authoring_review_only_guardrail`** string with explicit **`preview_only`**, **`no_execution`**, **`no_activation`**, **`no_runnable_plan`**, **`authoring_review_only`**, and **`future_preview_plan_drafting_context_only`** assertions, contains no string values implying live activation, executable command payloads, shell fragments, SQL mutations, scheduling or worker execution, external calls, scraping, ingestion, or production/runtime mutation (see service constants), and contains no URL-like substrings or risky shell-operator substrings in any optional draft-field strings present on the Sprint 74 input.
- **Blocked** when any of the above fails — including malformed Sprint 74 output, missing guardrails, non-zero **`actual_*`** counts, true **`may_*`** flags on the Sprint 74 artifact, forbidden language embedded anywhere in the Sprint 74 artifact, or failed post-generation safety validation of emitted draft text.

The strongest positive outcome remains **human review of a preview-only, non-runnable draft packet**. Execution, activation, scraping, ingestion, scheduling, and runtime mutation still require separate workflows outside this artifact.

## Relationship to Sprint 74

Sprint 74 remains the execution plan authoring review layer over Sprint 73. Sprint 75 consumes that review packet locally and produces a descriptive preview draft for human review without changing runtime state.
