# NativeForge active source activation operator release decision packet (v1)

## Sprint 106 purpose

Sprint 106 adds a deterministic, side-effect-free Python service that builds **`nf_active_source_activation_operator_release_decision_packet_v1`** artifacts. Each packet consumes a Sprint 105 **`nf_active_source_activation_operator_release_review_packet_v1`** artifact and records whether that operator release review packet may advance to a later **operator release authorization packet** gate.

Sprint 106 creates an **operator release decision packet**. It consumes Sprint 105. It decides whether the operator release review packet may advance to a later **operator release authorization packet**. It does **not** execute the plan. It does **not** activate sources. It does **not** create active source rows. It does **not** create commands. It does **not** scrape or ingest. It does **not** write runtime state. It is **deterministic** and **side-effect-free**.

Sprint 105 only created an **operator release review packet**. Sprint 106 does **not** permit live execution or runtime source activation. Sprint 106 does **not** complete source activation.

The **next gate** is the **operator release authorization packet** when the operator release decision packet is approved.

It does **not** emit runnable shell commands, copy-paste runnable plans, `command_preview` payloads, scheduler instructions, worker payloads, SQL mutations, outbound fetches, database sessions, runtime database writes, ledger mutations, or Alembic revisions.

## Inputs

- **`operator_release_review_packet_artifact`**: a dict representing `nf_active_source_activation_operator_release_review_packet_v1` from Sprint 105, with `artifact_version: 1` and semantic `version: "v1"` when present on the Sprint 105 artifact.

## Outputs

The operator release decision packet includes:

- **`artifact_type`**: `nf_active_source_activation_operator_release_decision_packet_v1`
- **`artifact_version`**: `1` (integer schema version for this artifact family)
- **`version`**: `v1` (string packet version, consistent with adjacent sprint artifacts)
- **`source_sprint_105_operator_release_review_packet_reference`**: key fields copied from the Sprint 105 packet for traceability
- **`operator_release_decision_status`**: approved-for-operator-release-authorization-packet, or blocked; never a statement that live execution is allowed, runtime source activation occurred, source activation is complete, or source activation is authorized in the runtime sense
- **`operator_release_decision_ready`**, **`operator_release_decision_only`**, **`operator_release_authorization_required`** (aligned with whether the artifact anticipates operator release authorization documentation), **`source_activation_authorized`**, **`source_activation_executed`**, **`source_activation_completed`**, **`source_activation_readiness_granted`** (always `false` on the artifact type)
- **`future_activation_execution_plan_execution_allowed`**, **`future_source_activation_allowed`**: always `false`
- **Top-level guardrails**: **`preview_only`**, **`no_execution`**, **`no_activation`**, **`no_runnable_plan`**
- **`next_gate_required`**: `operator_release_authorization_packet` when ready; `blocked_until_operator_release_decision_blockers_resolved` when blocked
- **`explicit_preview_only_no_execution_no_activation_no_runnable_plan_operator_release_decision_only_guardrail`**: explicit string guardrail including preview-only, no-execution, no-activation, no-runnable-plan, operator-release-decision-only posture, source-activation flags false, no-execution-performed, no-activation-performed, and no-runnable-command-created posture
- **`operator_release_decision_blockers`**: aligned list explaining a blocked outcome
- **`operator_release_decision_scope_summary`**, **`operator_release_decision_boundary_summary`**, **`operator_release_decision_evidence_summary`**, **`operator_release_decision_non_runtime_summary`**, **`operator_release_authorization_requirements_summary`**: descriptive, non-runnable narrative boundaries for the operator release authorization packet gate
- **`prohibited_runtime_actions_summary`**: descriptive prohibition narrative carried forward from Sprint 105 when present, otherwise a safe documentation-only fallback
- **`operator_release_review_summary`**: compact summary of Sprint 105 review fields used for traceability
- **Guardrails**: zero **`actual_*`** counts, false **`may_*`** flags, and Sprint 106 proof dict — consistent with prior NativeForge activation-review artifact posture

## Design rules

- **Ready (for operator release authorization packet)** when the Sprint 105 packet satisfies all Sprint 106 checks for a ready operator release review artifact, all guardrails pass, no forbidden language appears in scanned nested string values outside standard defensive prohibition narratives, and the Sprint 105 packet is ready for operator release decision documentation only. This outcome **does not** authorize live execution or runtime source activation; it does **not** complete source activation; it only documents that the review artifact may advance to the **operator release authorization packet** gate for separately gated operator authorization documentation.
- **Blocked** when Sprint 105 input is missing or invalid, any required guardrail fails, forbidden language appears in scanned inputs, or required Sprint 105 proof or summary fields are missing or invalid.

The strongest positive outcome after this operator release decision packet remains **readiness to consider an operator release authorization packet**, not execution, activation, scraping, ingestion, scheduling, runtime mutation, or source activation completion.

## Relationship to Sprint 105

Sprint 105 remains the operator release review packet layer over Sprint 104. Sprint 106 consumes that review packet locally and produces an operator release decision artifact for the next documentation gate without changing runtime state.
