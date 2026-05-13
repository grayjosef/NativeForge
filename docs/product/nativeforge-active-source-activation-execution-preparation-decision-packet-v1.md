# NativeForge active source activation execution preparation decision packet (v1)

## Sprint 87 purpose

Sprint 87 adds a deterministic, side-effect-free Python service that builds **`nf_active_source_activation_execution_preparation_decision_packet_v1`** artifacts. Each packet consumes a Sprint 86 **`nf_active_source_activation_execution_preparation_review_packet_v1`** artifact and records whether that descriptive execution preparation review artifact may advance to a **later source activation readiness packet** gate.

Sprint 87 creates an **execution preparation decision packet**. It consumes Sprint 86. It records a decision on whether the reviewed preparation artifact may advance to a source activation readiness packet. It does **not** execute the plan. It does **not** activate sources. It does **not** create active source rows. It does **not** create commands. It does **not** scrape or ingest. It does **not** write runtime state. It is **deterministic** and **side-effect-free**.

Sprint 86 only created a **descriptive execution preparation review packet**. Sprint 87 does **not** permit live execution or source activation. Sprint 87 does **not** grant source activation readiness.

The **next gate** after an approved Sprint 87 packet is the **source activation readiness packet**. Live execution and activation authority remain deferred to later gated artifacts.

It does **not** emit runnable shell commands, copy-paste runnable plans, `command_preview` payloads, scheduler instructions, worker payloads, SQL mutations, external URL fetches, database sessions, runtime database writes, ledger mutations, or Alembic revisions.

## Inputs

- **`execution_preparation_review_packet_artifact`**: a dict representing `nf_active_source_activation_execution_preparation_review_packet_v1` from Sprint 86, with `artifact_version: 1` and semantic `version: "v1"` when present on the Sprint 86 artifact.
- **`human_execution_preparation_decision_input`**: optional dict carrying operator-style approval signals (`approved`, `decision`, `rationale`, `operator_identifier`) using the same documentation-only posture as Sprint 84 decision inputs.

## Outputs

The execution preparation decision packet includes:

- **`artifact_type`**: `nf_active_source_activation_execution_preparation_decision_packet_v1`
- **`artifact_version`**: `1` (integer schema version for this artifact family)
- **`version`**: `v1` (string packet version, consistent with Sprint 86 and adjacent sprint artifacts)
- **`generated_at`**: fixed deterministic timestamp (`1970-01-01T00:00:00Z`) for reproducible artifacts
- **`source_sprint_86_execution_preparation_review_packet_reference`**: key fields copied from the Sprint 86 packet for traceability
- **`execution_preparation_decision_status`**: approved-for-source-activation-readiness-packet, or blocked; never a statement that live execution is allowed, activation is allowed, source activation is authorized, or source activation readiness is granted
- **`execution_preparation_decision_approved`**, **`execution_preparation_decision_recorded`**, **`execution_preparation_decision_only`**, **`source_activation_readiness_packet_required`**, **`source_activation_readiness_not_granted`**: aligned decision and later-readiness posture
- **`future_activation_execution_plan_execution_allowed`**, **`future_source_activation_allowed`**: always `false`
- **Top-level guardrails**: **`preview_only`**, **`no_execution`**, **`no_activation`**, **`no_runnable_plan`**
- **`next_gate_required`**: `source_activation_readiness_packet` when approved; `blocked_until_execution_preparation_decision_blockers_resolved` when blocked
- **`explicit_preview_only_no_execution_no_activation_no_runnable_plan_execution_preparation_decision_only_guardrail`**: explicit string guardrail including preview-only, no-execution, no-activation, no-runnable-plan, execution-preparation-decision-only, source-activation-readiness-packet-required, source-activation-readiness-not-granted, no-execution-performed, no-activation-performed, and no-runnable-command-created posture
- **`execution_preparation_decision_blockers`**: aligned list explaining a blocked outcome
- **`decision_scope_summary`**, **`decision_boundary_summary`**, **`decision_evidence_summary`**, **`decision_authorization_summary`**, **`decision_readiness_requirements_summary`**: descriptive, non-runnable narrative boundaries for the later source activation readiness packet gate
- **`decision_rationale`**: non-runnable descriptive rationale copied from a valid human decision input on approved outcomes only
- **`prohibited_runtime_actions_summary`**: descriptive prohibition narrative carried forward from Sprint 86 when present, otherwise a safe documentation-only fallback
- **`source_execution_preparation_review_summary`**: compact summary of Sprint 86 review fields used for traceability
- **Guardrails**: zero **`actual_*`** counts, false **`may_*`** flags, and Sprint 87 proof dict — consistent with prior NativeForge activation-review artifact posture

## Decision rules

- **Approved (for source activation readiness packet)** when the Sprint 86 packet satisfies all Sprint 87 checks for a ready execution preparation review packet that is ready for execution preparation decision, all guardrails pass, no forbidden language appears in scanned Sprint 86 nested string values outside standard defensive prohibition narratives, and a valid human approval decision is recorded. This outcome **does not** authorize live execution or source activation; it only documents that the reviewed preparation artifact may advance to the **source activation readiness packet** gate for a separate readiness evaluation.
- **Blocked** when Sprint 86 input is missing or invalid, the Sprint 86 execution preparation review packet is blocked, the Sprint 86 packet is not ready for decision, any required guardrail fails, the human decision is missing or conflicting, or forbidden language appears anywhere in the scanned input surfaces including decision rationale.

The strongest positive outcome after approval remains **readiness to consider a separate source activation readiness packet**, not execution, activation, scraping, ingestion, scheduling, runtime mutation, or a grant of source activation readiness.

## Relationship to Sprint 86

Sprint 86 remains the execution preparation review packet layer over Sprint 85. Sprint 87 consumes that review packet locally and produces an execution preparation decision artifact for the next documentation gate without changing runtime state.
