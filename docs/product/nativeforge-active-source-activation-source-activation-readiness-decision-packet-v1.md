# NativeForge active source activation source activation readiness decision packet (v1)

## Sprint 90 purpose

Sprint 90 adds a deterministic, side-effect-free Python service that builds **`nf_active_source_activation_source_activation_readiness_decision_packet_v1`** artifacts. Each packet consumes a Sprint 89 **`nf_active_source_activation_source_activation_readiness_review_packet_v1`** artifact and records a decision on whether the reviewed readiness artifact may advance to a **later final source activation authorization packet** gate.

Sprint 90 creates a **source activation readiness decision packet**. It consumes Sprint 89. It records a **decision** on whether the reviewed readiness artifact may advance to final source activation authorization. It does **not** execute the plan. It does **not** activate sources. It does **not** create active source rows. It does **not** create commands. It does **not** scrape or ingest. It does **not** write runtime state. It is **deterministic** and **side-effect-free**.

Sprint 89 only created a **descriptive source activation readiness review packet**. Sprint 90 does **not** permit live execution or source activation. Sprint 90 does **not** grant source activation readiness. Sprint 90 does **not** authorize source activation.

The **next gate** after an approved Sprint 90 packet is the **final source activation authorization packet**. Live execution, activation authority, and source activation readiness itself, remain deferred to that later gated artifact.

It does **not** emit runnable shell commands, copy-paste runnable plans, `command_preview` payloads, scheduler instructions, worker payloads, SQL mutations, external URL fetches, database sessions, runtime database writes, ledger mutations, or Alembic revisions.

## Inputs

- **`source_activation_readiness_review_packet_artifact`**: a dict representing `nf_active_source_activation_source_activation_readiness_review_packet_v1` from Sprint 89, with `artifact_version: 1` and semantic `version: "v1"` when present on the Sprint 89 artifact.
- **`human_source_activation_readiness_decision_input`**: optional dict with operator decision fields (`approved`, `decision`, `rationale`, `operator_identifier`) used only as descriptive, non-runnable decision metadata.

## Outputs

The source activation readiness decision packet includes:

- **`artifact_type`**: `nf_active_source_activation_source_activation_readiness_decision_packet_v1`
- **`artifact_version`**: `1` (integer schema version for this artifact family)
- **`version`**: `v1` (string packet version, consistent with adjacent sprint artifacts)
- **`generated_at`**: fixed deterministic timestamp (`1970-01-01T00:00:00Z`) for reproducible artifacts
- **`source_sprint_89_source_activation_readiness_review_packet_reference`**: key fields copied from the Sprint 89 packet for traceability
- **`source_activation_readiness_decision_status`**: approved-for-final-source-activation-authorization-packet, or blocked; never a statement that live execution is allowed, activation is allowed, source activation is authorized, or source activation readiness is granted
- **`source_activation_readiness_decision_approved`**, **`source_activation_readiness_decision_recorded`**, **`source_activation_readiness_decision_only`**, **`final_source_activation_authorization_packet_required`** (only `true` when approved; always `false` when blocked), **`source_activation_readiness_granted`** (always `false`), **`source_activation_authorized`** (always `false`): aligned decision and deferred-authorization posture
- **`future_activation_execution_plan_execution_allowed`**, **`future_source_activation_allowed`**: always `false`
- **Top-level guardrails**: **`preview_only`**, **`no_execution`**, **`no_activation`**, **`no_runnable_plan`**
- **`next_gate_required`**: `final_source_activation_authorization_packet` when approved; `blocked_until_source_activation_readiness_decision_blockers_resolved` when blocked
- **`explicit_preview_only_no_execution_no_activation_no_runnable_plan_source_activation_readiness_decision_only_guardrail`**: explicit string guardrail including preview-only, no-execution, no-activation, no-runnable-plan, source-activation-readiness-decision-only, final-source-activation-authorization-packet-required, source-activation-readiness-granted-false, source-activation-authorized-false, no-execution-performed, no-activation-performed, and no-runnable-command-created posture
- **`source_activation_readiness_decision_blockers`**: aligned list explaining a blocked outcome
- **`readiness_decision_scope_summary`**, **`readiness_decision_boundary_summary`**, **`readiness_decision_evidence_summary`**, **`readiness_decision_authorization_summary`**, **`final_authorization_requirements_summary`**, **`readiness_decision_rationale`**: descriptive, non-runnable narrative boundaries for the later final source activation authorization packet gate
- **`prohibited_runtime_actions_summary`**: descriptive prohibition narrative carried forward from Sprint 89 when present, otherwise a safe documentation-only fallback
- **`source_activation_readiness_review_summary`**: compact summary of Sprint 89 review fields used for traceability
- **Guardrails**: zero **`actual_*`** counts, false **`may_*`** flags, and Sprint 90 proof dict — consistent with prior NativeForge activation-review artifact posture

## Decision rules

- **Approved (for final source activation authorization packet)** when the Sprint 89 packet satisfies all Sprint 90 checks for a readiness review artifact that is ready for a readiness decision, all guardrails pass, no forbidden language appears in scanned Sprint 89 nested string values outside standard defensive prohibition narratives, and a valid human approval decision is present (`approved: true` and/or `decision: "approved"`). This outcome **does not** authorize live execution or source activation; it does **not** grant source activation readiness; it only documents that the readiness review artifact may advance to the **final source activation authorization packet** gate for a separate authorization decision.
- **Blocked** when Sprint 89 input is missing or invalid, the Sprint 89 readiness review packet is blocked, the Sprint 89 packet is not ready for decision, any required guardrail fails, forbidden language appears in scanned inputs, the human decision is missing, rejected, denied, blocked, ambiguous, conflicting, or contains forbidden language in rationale or other string fields.

The strongest positive outcome after readiness decision remains **readiness to consider a separate final source activation authorization packet**, not execution, activation, scraping, ingestion, scheduling, runtime mutation, source activation readiness grant, or source activation authorization.

## Relationship to Sprint 89

Sprint 89 remains the source activation readiness review packet layer over Sprint 88. Sprint 90 consumes that review packet locally and produces a readiness decision artifact for the next documentation gate without changing runtime state.
