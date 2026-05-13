# NativeForge active source activation operator full source packet (v1)

## Sprint 115 purpose

Sprint 115 adds a deterministic, side-effect-free Python service that builds **`nf_active_source_activation_operator_full_source_packet_v1`** artifacts. Each packet consumes a Sprint 114 **`nf_active_source_activation_operator_live_source_packet_v1`** artifact and records whether that operator live source packet may advance to a later **final source activation** documentation gate.

Sprint 115 creates an **operator full source packet** only. It consumes Sprint 114. It determines whether the Sprint 114 operator live source packet may proceed to final source activation documentation at the **final source activation packet** gate. It does **not** execute anything outside simulation, activate sources as an operational outcome, create active rows, or run commands. It does **not** scrape or ingest. It does **not** write unrelated runtime state. It is **deterministic** and **side-effect-free**.

Sprint 114 only created an **operator live source packet**. Sprint 115 does **not** permit live execution or runtime source activation as an outcome of this builder. Sprint 115 does **not** complete source activation.

The **next gate** is the **final source activation packet** when the operator full source packet is ready.

It does **not** emit runnable shell commands, copy-paste runnable plans, `command_preview` payloads, scheduler instructions, worker payloads, SQL mutations, outbound fetches, database sessions, runtime database writes, ledger mutations, or Alembic revisions.

## Inputs

- **`operator_live_source_packet_artifact`**: a dict representing `nf_active_source_activation_operator_live_source_packet_v1` from Sprint 114, with `artifact_version: 1` and semantic `version: "v1"` when present on the Sprint 114 artifact.

## Preconditions (approved path)

Input must be a Sprint 114 operator live source packet with expected guardrails intact: **`preview_only`**, **`no_execution`**, **`no_activation`**, and **`no_runnable_plan`** true; all **`actual_*`** counts zero; all **`may_*`** flags false; **`operator_live_source_status`** approved for live source activation documentation; **`operator_live_source_ready`** true; **`operator_live_source_only`** true; **`operator_live_source_blockers`** empty; **`next_gate_required`** equal to the Sprint 114 ready value for the live source packet gate; Sprint 114 explicit guard string and narrative summaries valid; required Sprint 114 proof and traceability fields present; and nested-string language scans clean outside excluded narrative fields.

## Outputs

The operator full source packet includes:

- **`artifact_type`**: `nf_active_source_activation_operator_full_source_packet_v1`
- **`artifact_version`**: `1` (integer schema version for this artifact family)
- **`version`**: `v1` (string packet version, consistent with adjacent sprint artifacts)
- **`source_sprint_114_operator_live_source_packet_reference`**: key fields copied from the Sprint 114 packet for traceability
- **`operator_full_source_status`**: `approved_for_final_source_activation`, or blocked; never a claim that this artifact performed execution, activated sources, or completed activation in the runtime sense
- **`operator_full_source_ready`**, **`operator_full_source_only`**, **`source_activation_required`**, **`source_activation_authorized`**, **`source_activation_executed`**, **`source_activation_completed`**, **`source_activation_readiness_granted`** (source-activation booleans remain documentation posture; **`source_activation_authorized`** is `false` on this artifact type)
- **`future_activation_execution_plan_execution_allowed`**, **`future_source_activation_allowed`**: always `false`
- **Top-level guardrails**: **`preview_only`**, **`no_execution`**, **`no_activation`**, **`no_runnable_plan`**
- **`next_gate_required`**: `final_source_activation_packet` when ready; `blocked_until_operator_full_source_blockers_resolved` when blocked
- **`explicit_preview_only_no_execution_no_activation_no_runnable_plan_operator_full_source_only_guardrail`**: explicit string guardrail including preview-only, no-execution, no-activation, no-runnable-plan, operator-full-source-only posture, source-activation flags false, no-execution-performed, no-activation-performed, and no-runnable-command-created posture
- **`operator_full_source_blockers`**: aligned list explaining a blocked outcome
- **`operator_full_source_scope_summary`**, **`operator_full_source_boundary_summary`**, **`operator_full_source_evidence_summary`**, **`operator_full_source_non_runtime_summary`**, **`operator_full_source_activation_requirements_summary`**: descriptive, non-runnable narrative boundaries for the final source activation packet gate
- **`prohibited_runtime_actions_summary`**: descriptive prohibition narrative carried forward from Sprint 114 when present, otherwise a safe documentation-only fallback
- **`operator_live_source_summary`**: compact summary of Sprint 114 operator live source fields used for traceability
- **Guardrails**: zero **`actual_*`** counts, false **`may_*`** flags, and Sprint 115 proof dict — consistent with prior NativeForge activation-review artifact posture

## Design rules

- **Ready (for final source activation packet)** when the Sprint 114 packet satisfies all Sprint 115 checks for a ready operator live source artifact, all guardrails pass, no forbidden language appears in scanned nested string values outside standard defensive prohibition narratives, and the Sprint 114 packet is approved for live source activation documentation only. This outcome **does not** execute plans or activate sources; it only documents that the Sprint 114 artifact may advance to the **final source activation packet** gate for separately gated final source activation documentation.
- **Blocked** when Sprint 114 input is missing or invalid, any required guardrail fails, Sprint 114 is not in the approved operator live source posture, forbidden language appears in scanned inputs, or required Sprint 114 proof or summary fields are missing or invalid.

The strongest positive outcome after this operator full source packet remains **readiness to consider a final source activation packet**, not execution, activation, scraping, ingestion, scheduling, runtime mutation, or source activation completion.

## Relationship to Sprint 114

Sprint 114 remains the operator live source layer over Sprint 113. Sprint 115 consumes that operator live source packet locally and produces an operator full source artifact for the next documentation gate without changing runtime state.
