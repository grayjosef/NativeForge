# NativeForge active source activation separate runtime implementation preparation packet (v1)

## Sprint 96 purpose

Sprint 96 adds a deterministic, side-effect-free Python service that builds **`nf_active_source_activation_separate_runtime_implementation_preparation_packet_v1`** artifacts. Each packet consumes a Sprint 95 **`nf_active_source_activation_separate_runtime_implementation_decision_packet_v1`** artifact and records whether that decision packet may advance to a **separate runtime implementation authorization packet** gate.

Sprint 96 creates a **separate runtime implementation preparation packet**. It consumes Sprint 95. It prepares **non-runnable** implementation preparation context for a later **separate runtime implementation authorization packet**. It does **not** execute the plan. It does **not** activate sources. It does **not** create active source rows. It does **not** create commands. It does **not** scrape or ingest. It does **not** write runtime state. It is **deterministic** and **side-effect-free**.

Sprint 95 only created a **decision packet**. Sprint 96 does **not** permit live execution or runtime source activation. Sprint 96 does **not** complete source activation.

The **next gate** is the **separate runtime implementation authorization packet** when the preparation packet is ready.

It does **not** emit runnable shell commands, copy-paste runnable plans, `command_preview` payloads, scheduler instructions, worker payloads, SQL mutations, external URL fetches, database sessions, runtime database writes, ledger mutations, or Alembic revisions.

## Inputs

- **`separate_runtime_implementation_decision_packet_artifact`**: a dict representing `nf_active_source_activation_separate_runtime_implementation_decision_packet_v1` from Sprint 95, with `artifact_version: 1` and semantic `version: "v1"` when present on the Sprint 95 artifact.

## Outputs

The separate runtime implementation preparation packet includes:

- **`artifact_type`**: `nf_active_source_activation_separate_runtime_implementation_preparation_packet_v1`
- **`artifact_version`**: `1` (integer schema version for this artifact family)
- **`version`**: `v1` (string packet version, consistent with adjacent sprint artifacts)
- **`generated_at`**: fixed deterministic timestamp (`1970-01-01T00:00:00Z`) for reproducible artifacts
- **`source_sprint_95_separate_runtime_implementation_decision_packet_reference`**: key fields copied from the Sprint 95 packet for traceability
- **`separate_runtime_implementation_preparation_status`**: ready-for-separate-runtime-implementation-authorization-packet, or blocked; never a statement that live execution is allowed, runtime source activation occurred, source activation is complete, or source activation is authorized in the runtime sense
- **`separate_runtime_implementation_preparation_ready`**, **`separate_runtime_implementation_preparation_only`**, **`runtime_implementation_authorization_required`** (true on ready outcomes when the preparation packet anticipates the authorization gate), **`source_activation_authorized`**, **`source_activation_executed`**, **`source_activation_completed`**, **`source_activation_readiness_granted`** (always `false` on the artifact type)
- **`future_activation_execution_plan_execution_allowed`**, **`future_source_activation_allowed`**: always `false`
- **Top-level guardrails**: **`preview_only`**, **`no_execution`**, **`no_activation`**, **`no_runnable_plan`**
- **`next_gate_required`**: `separate_runtime_implementation_authorization_packet` when ready; `blocked_until_separate_runtime_implementation_preparation_blockers_resolved` when blocked
- **`explicit_preview_only_no_execution_no_activation_no_runnable_plan_separate_runtime_implementation_preparation_only_guardrail`**: explicit string guardrail including preview-only, no-execution, no-activation, no-runnable-plan, separate-runtime-implementation-preparation-only, runtime-implementation-authorization-required, source-activation-authorized-false, source-activation-executed-false, source-activation-completed-false, source-activation-readiness-granted-false, no-execution-performed, no-activation-performed, and no-runnable-command-created posture
- **`separate_runtime_implementation_preparation_blockers`**: aligned list explaining a blocked outcome
- **`runtime_preparation_scope_summary`**, **`runtime_preparation_boundary_summary`**, **`runtime_preparation_evidence_summary`**, **`runtime_preparation_non_runtime_summary`**, **`separate_runtime_implementation_authorization_requirements_summary`**: descriptive, non-runnable narrative boundaries for the separate runtime implementation authorization packet gate
- **`prohibited_runtime_actions_summary`**: descriptive prohibition narrative carried forward from Sprint 95 when present, otherwise a safe documentation-only fallback
- **`separate_runtime_implementation_decision_summary`**: compact summary of Sprint 95 decision fields used for traceability
- **Guardrails**: zero **`actual_*`** counts, false **`may_*`** flags, and Sprint 96 proof dict — consistent with prior NativeForge activation-review artifact posture

## Design rules

- **Ready (for separate runtime implementation authorization packet)** when the Sprint 95 packet satisfies all Sprint 96 checks for an approved separate runtime implementation decision artifact, all guardrails pass, no forbidden language appears in scanned nested string values outside standard defensive prohibition narratives, and the Sprint 95 packet is ready for separate runtime implementation preparation documentation only. This outcome **does not** authorize live execution or runtime source activation; it does **not** complete source activation; it only documents that the decision artifact may advance to the **separate runtime implementation authorization packet** gate for separately gated authorization documentation.
- **Blocked** when Sprint 95 input is missing or invalid, any required guardrail fails, forbidden language appears in scanned inputs, or required Sprint 95 proof or summary fields are missing or invalid.

The strongest positive outcome after this preparation packet remains **readiness to consider a separate runtime implementation authorization packet**, not execution, activation, scraping, ingestion, scheduling, runtime mutation, or source activation completion.

## Relationship to Sprint 95

Sprint 95 remains the separate runtime implementation decision packet layer over Sprint 94. Sprint 96 consumes that decision packet locally and produces a separate runtime implementation preparation artifact for the next documentation gate without changing runtime state.
