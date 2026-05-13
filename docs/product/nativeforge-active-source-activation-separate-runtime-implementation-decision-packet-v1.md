# NativeForge active source activation separate runtime implementation decision packet (v1)

## Sprint 95 purpose

Sprint 95 adds a deterministic, side-effect-free Python service that builds **`nf_active_source_activation_separate_runtime_implementation_decision_packet_v1`** artifacts. Each packet consumes a Sprint 94 **`nf_active_source_activation_separate_runtime_implementation_review_packet_v1`** artifact and records whether that review packet may advance to a **separate runtime implementation preparation packet** gate.

Sprint 95 creates a **separate runtime implementation decision packet**. It consumes Sprint 94. It decides whether the review packet may advance to a later **separate runtime implementation preparation packet**. It does **not** execute the plan. It does **not** activate sources. It does **not** create active source rows. It does **not** create commands. It does **not** scrape or ingest. It does **not** write runtime state. It is **deterministic** and **side-effect-free**.

Sprint 94 only created a **separate runtime implementation review packet**. Sprint 95 does **not** permit live execution or runtime source activation. Sprint 95 does **not** complete source activation.

The **next gate** is the **separate runtime implementation preparation packet** when the decision packet is approved. Live execution, activation authority, runtime source activation, and source activation completion, remain out of scope for this artifact.

It does **not** emit runnable shell commands, copy-paste runnable plans, `command_preview` payloads, scheduler instructions, worker payloads, SQL mutations, external URL fetches, database sessions, runtime database writes, ledger mutations, or Alembic revisions.

## Inputs

- **`separate_runtime_implementation_review_packet_artifact`**: a dict representing `nf_active_source_activation_separate_runtime_implementation_review_packet_v1` from Sprint 94, with `artifact_version: 1` and semantic `version: "v1"` when present on the Sprint 94 artifact.

## Outputs

The separate runtime implementation decision packet includes:

- **`artifact_type`**: `nf_active_source_activation_separate_runtime_implementation_decision_packet_v1`
- **`artifact_version`**: `1` (integer schema version for this artifact family)
- **`version`**: `v1` (string packet version, consistent with adjacent sprint artifacts)
- **`generated_at`**: fixed deterministic timestamp (`1970-01-01T00:00:00Z`) for reproducible artifacts
- **`source_sprint_94_separate_runtime_implementation_review_packet_reference`**: key fields copied from the Sprint 94 packet for traceability
- **`separate_runtime_implementation_decision_status`**: approved-for-separate-runtime-implementation-preparation-packet, or blocked; never a statement that live execution is allowed, runtime source activation occurred, source activation is complete, or source activation is authorized in the runtime sense
- **`separate_runtime_implementation_decision_ready`**, **`separate_runtime_implementation_decision_only`**, **`runtime_implementation_preparation_required`** (true on ready outcomes when the decision packet approves the preparation gate), **`source_activation_authorized`**, **`source_activation_executed`**, **`source_activation_completed`**, **`source_activation_readiness_granted`** (always `false` on the artifact type)
- **`future_activation_execution_plan_execution_allowed`**, **`future_source_activation_allowed`**: always `false`
- **Top-level guardrails**: **`preview_only`**, **`no_execution`**, **`no_activation`**, **`no_runnable_plan`**
- **`next_gate_required`**: `separate_runtime_implementation_preparation_packet` when approved; `blocked_until_separate_runtime_implementation_decision_blockers_resolved` when blocked
- **`explicit_preview_only_no_execution_no_activation_no_runnable_plan_separate_runtime_implementation_decision_only_guardrail`**: explicit string guardrail including preview-only, no-execution, no-activation, no-runnable-plan, separate-runtime-implementation-decision-only, runtime-implementation-preparation-required, source-activation-authorized-false, source-activation-executed-false, source-activation-completed-false, source-activation-readiness-granted-false, no-execution-performed, no-activation-performed, and no-runnable-command-created posture
- **`separate_runtime_implementation_decision_blockers`**: aligned list explaining a blocked outcome
- **`runtime_decision_scope_summary`**, **`runtime_decision_boundary_summary`**, **`runtime_decision_evidence_summary`**, **`runtime_decision_non_runtime_summary`**, **`separate_runtime_implementation_preparation_requirements_summary`**: descriptive, non-runnable narrative boundaries for the separate runtime implementation preparation packet gate
- **`prohibited_runtime_actions_summary`**: descriptive prohibition narrative carried forward from Sprint 94 when present, otherwise a safe documentation-only fallback
- **`separate_runtime_implementation_review_summary`**: compact summary of Sprint 94 review fields used for traceability
- **Guardrails**: zero **`actual_*`** counts, false **`may_*`** flags, and Sprint 95 proof dict — consistent with prior NativeForge activation-review artifact posture

## Design rules

- **Approved (for separate runtime implementation preparation packet)** when the Sprint 94 packet satisfies all Sprint 95 checks for a ready separate runtime implementation review artifact, all guardrails pass, no forbidden language appears in scanned nested string values outside standard defensive prohibition narratives, and the Sprint 94 packet is ready for separate runtime implementation decision documentation only. This outcome **does not** authorize live execution or runtime source activation; it does **not** complete source activation; it only documents that the review artifact may advance to the **separate runtime implementation preparation packet** gate for separately gated preparation documentation.
- **Blocked** when Sprint 94 input is missing or invalid, the Sprint 94 review packet is blocked, the Sprint 94 packet is not ready for separate runtime implementation decision documentation, any required guardrail fails, forbidden language appears in scanned inputs, or required Sprint 94 proof or summary fields are missing or invalid.

The strongest positive outcome after this decision packet remains **readiness to consider a separate runtime implementation preparation packet**, not execution, activation, scraping, ingestion, scheduling, runtime mutation, or source activation completion.

## Relationship to Sprint 94

Sprint 94 remains the separate runtime implementation review packet layer over Sprint 93. Sprint 95 consumes that review packet locally and produces a separate runtime implementation decision artifact for the next documentation gate without changing runtime state.
