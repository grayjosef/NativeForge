# NativeForge active source activation separate runtime implementation authorization packet (v1)

## Sprint 97 purpose

Sprint 97 adds a deterministic, side-effect-free Python service that builds **`nf_active_source_activation_separate_runtime_implementation_authorization_packet_v1`** artifacts. Each packet consumes a Sprint 96 **`nf_active_source_activation_separate_runtime_implementation_preparation_packet_v1`** artifact and records whether that preparation packet may advance to a **separate runtime implementation handoff packet** gate.

Sprint 97 creates a **separate runtime implementation authorization packet**. It consumes Sprint 96. It authorizes whether the preparation packet may advance to a later **separate runtime implementation handoff packet**. It does **not** execute the plan. It does **not** activate sources. It does **not** create active source rows. It does **not** create commands. It does **not** scrape or ingest. It does **not** write runtime state. It is **deterministic** and **side-effect-free**.

Sprint 96 only created a **preparation packet**. Sprint 97 does **not** permit live execution or runtime source activation. Sprint 97 does **not** complete source activation.

The **next gate** is the **separate runtime implementation handoff packet** when the authorization packet is ready.

It does **not** emit runnable shell commands, copy-paste runnable plans, `command_preview` payloads, scheduler instructions, worker payloads, SQL mutations, external URL fetches, database sessions, runtime database writes, ledger mutations, or Alembic revisions.

## Inputs

- **`separate_runtime_implementation_preparation_packet_artifact`**: a dict representing `nf_active_source_activation_separate_runtime_implementation_preparation_packet_v1` from Sprint 96, with `artifact_version: 1` and semantic `version: "v1"` when present on the Sprint 96 artifact.

## Outputs

The separate runtime implementation authorization packet includes:

- **`artifact_type`**: `nf_active_source_activation_separate_runtime_implementation_authorization_packet_v1`
- **`artifact_version`**: `1` (integer schema version for this artifact family)
- **`version`**: `v1` (string packet version, consistent with adjacent sprint artifacts)
- **`generated_at`**: fixed deterministic timestamp (`1970-01-01T00:00:00Z`) for reproducible artifacts
- **`source_sprint_96_separate_runtime_implementation_preparation_packet_reference`**: key fields copied from the Sprint 96 packet for traceability
- **`separate_runtime_implementation_authorization_status`**: authorized-for-separate-runtime-implementation-handoff-packet, or blocked; never a statement that live execution is allowed, runtime source activation occurred, source activation is complete, or source activation is authorized in the runtime sense
- **`separate_runtime_implementation_authorization_ready`**, **`separate_runtime_implementation_authorization_only`**, **`runtime_implementation_handoff_required`** (true on ready outcomes when the authorization packet anticipates the handoff gate), **`source_activation_authorized`**, **`source_activation_executed`**, **`source_activation_completed`**, **`source_activation_readiness_granted`** (always `false` on the artifact type)
- **`future_activation_execution_plan_execution_allowed`**, **`future_source_activation_allowed`**: always `false`
- **Top-level guardrails**: **`preview_only`**, **`no_execution`**, **`no_activation`**, **`no_runnable_plan`**
- **`next_gate_required`**: `separate_runtime_implementation_handoff_packet` when ready; `blocked_until_separate_runtime_implementation_authorization_blockers_resolved` when blocked
- **`explicit_preview_only_no_execution_no_activation_no_runnable_plan_separate_runtime_implementation_authorization_only_guardrail`**: explicit string guardrail including preview-only, no-execution, no-activation, no-runnable-plan, separate-runtime-implementation-authorization-only, runtime-implementation-handoff-required, source-activation-authorized-false, source-activation-executed-false, source-activation-completed-false, source-activation-readiness-granted-false, no-execution-performed, no-activation-performed, and no-runnable-command-created posture
- **`separate_runtime_implementation_authorization_blockers`**: aligned list explaining a blocked outcome
- **`runtime_authorization_scope_summary`**, **`runtime_authorization_boundary_summary`**, **`runtime_authorization_evidence_summary`**, **`runtime_authorization_non_runtime_summary`**, **`separate_runtime_implementation_handoff_requirements_summary`**: descriptive, non-runnable narrative boundaries for the separate runtime implementation handoff packet gate
- **`prohibited_runtime_actions_summary`**: descriptive prohibition narrative carried forward from Sprint 96 when present, otherwise a safe documentation-only fallback
- **`separate_runtime_implementation_preparation_summary`**: compact summary of Sprint 96 preparation fields used for traceability
- **Guardrails**: zero **`actual_*`** counts, false **`may_*`** flags, and Sprint 97 proof dict — consistent with prior NativeForge activation-review artifact posture

## Design rules

- **Ready (for separate runtime implementation handoff packet)** when the Sprint 96 packet satisfies all Sprint 97 checks for a ready separate runtime implementation preparation artifact, all guardrails pass, no forbidden language appears in scanned nested string values outside standard defensive prohibition narratives, and the Sprint 96 packet is ready for separate runtime implementation authorization documentation only. This outcome **does not** authorize live execution or runtime source activation; it does **not** complete source activation; it only documents that the preparation artifact may advance to the **separate runtime implementation handoff packet** gate for separately gated handoff documentation.
- **Blocked** when Sprint 96 input is missing or invalid, any required guardrail fails, forbidden language appears in scanned inputs, or required Sprint 96 proof or summary fields are missing or invalid.

The strongest positive outcome after this authorization packet remains **readiness to consider a separate runtime implementation handoff packet**, not execution, activation, scraping, ingestion, scheduling, runtime mutation, or source activation completion.

## Relationship to Sprint 96

Sprint 96 remains the separate runtime implementation preparation packet layer over Sprint 95. Sprint 97 consumes that preparation packet locally and produces a separate runtime implementation authorization artifact for the next documentation gate without changing runtime state.
