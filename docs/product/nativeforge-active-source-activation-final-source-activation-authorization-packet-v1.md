# NativeForge active source activation final source activation authorization packet (v1)

## Sprint 91 purpose

Sprint 91 adds a deterministic, side-effect-free Python service that builds **`nf_active_source_activation_final_source_activation_authorization_packet_v1`** artifacts. Each packet consumes a Sprint 90 **`nf_active_source_activation_source_activation_readiness_decision_packet_v1`** artifact and records a **final** human/operator authorization decision for whether that readiness decision may advance to a **later non-runnable activation handoff packet** gate.

Sprint 91 creates a **final source activation authorization packet**. It consumes Sprint 90. It records a **final authorization** decision for whether the source activation readiness decision may advance to a later non-runnable activation handoff packet. It does **not** execute the plan. It does **not** activate sources. It does **not** create active source rows. It does **not** create commands. It does **not** scrape or ingest. It does **not** write runtime state. It is **deterministic** and **side-effect-free**.

Sprint 90 only created a **descriptive source activation readiness decision packet**. Sprint 91 does **not** permit live execution or runtime source activation. Sprint 91 does **not** complete source activation.

The **next gate** after an authorized Sprint 91 packet is the **later non-runnable activation handoff packet**. Live execution, activation authority, runtime source activation, and source activation completion, remain out of scope for this artifact.

It does **not** emit runnable shell commands, copy-paste runnable plans, `command_preview` payloads, scheduler instructions, worker payloads, SQL mutations, external URL fetches, database sessions, runtime database writes, ledger mutations, or Alembic revisions.

## Inputs

- **`source_activation_readiness_decision_packet_artifact`**: a dict representing `nf_active_source_activation_source_activation_readiness_decision_packet_v1` from Sprint 90, with `artifact_version: 1` and semantic `version: "v1"` when present on the Sprint 90 artifact.
- **`human_final_source_activation_authorization_input`**: optional dict with operator authorization fields (`authorized`, `authorization_decision`, `decision`, `authorization_rationale` or `rationale`, `operator_identifier`) used only as descriptive, non-runnable authorization metadata.

## Outputs

The final source activation authorization packet includes:

- **`artifact_type`**: `nf_active_source_activation_final_source_activation_authorization_packet_v1`
- **`artifact_version`**: `1` (integer schema version for this artifact family)
- **`version`**: `v1` (string packet version, consistent with adjacent sprint artifacts)
- **`generated_at`**: fixed deterministic timestamp (`1970-01-01T00:00:00Z`) for reproducible artifacts
- **`source_sprint_90_source_activation_readiness_decision_packet_reference`**: key fields copied from the Sprint 90 packet for traceability
- **`final_source_activation_authorization_status`**: authorized-for-later-non-runnable-activation-handoff-packet, or blocked; never a statement that live execution is allowed, runtime source activation occurred, source activation is complete, or source activation is authorized in the runtime sense
- **`final_source_activation_authorization_recorded`**, **`final_source_activation_authorization_approved`**, **`final_source_activation_authorization_only`** (always `true` on the artifact type), **`source_activation_authorized_for_later_non_runnable_handoff`** (only `true` when authorized; always `false` when blocked), **`source_activation_authorized`** (always `false`), **`source_activation_executed`** (always `false`), **`source_activation_completed`** (always `false`), **`source_activation_readiness_granted`** (always `false`)
- **`future_activation_execution_plan_execution_allowed`**, **`future_source_activation_allowed`**: always `false`
- **Top-level guardrails**: **`preview_only`**, **`no_execution`**, **`no_activation`**, **`no_runnable_plan`**
- **`next_gate_required`**: `later_non_runnable_activation_handoff_packet` when authorized; `blocked_until_final_source_activation_authorization_blockers_resolved` when blocked
- **`explicit_preview_only_no_execution_no_activation_no_runnable_plan_final_source_activation_authorization_only_guardrail`**: explicit string guardrail including preview-only, no-execution, no-activation, no-runnable-plan, final-source-activation-authorization-only, source-activation-authorized-false, source-activation-executed-false, source-activation-completed-false, source-activation-readiness-granted-false, no-execution-performed, no-activation-performed, and no-runnable-command-created posture
- **`final_source_activation_authorization_blockers`**: aligned list explaining a blocked outcome
- **`final_authorization_scope_summary`**, **`final_authorization_boundary_summary`**, **`final_authorization_evidence_summary`**, **`final_authorization_non_runtime_summary`**, **`later_non_runnable_handoff_requirements_summary`**, **`final_authorization_rationale`**: descriptive, non-runnable narrative boundaries for the later non-runnable activation handoff packet gate
- **`prohibited_runtime_actions_summary`**: descriptive prohibition narrative carried forward from Sprint 90 when present, otherwise a safe documentation-only fallback
- **`source_activation_readiness_decision_summary`**: compact summary of Sprint 90 decision fields used for traceability
- **Guardrails**: zero **`actual_*`** counts, false **`may_*`** flags, and Sprint 91 proof dict — consistent with prior NativeForge activation-review artifact posture

## Authorization rules

- **Authorized (for later non-runnable activation handoff packet)** when the Sprint 90 packet satisfies all Sprint 91 checks for an approved readiness decision artifact, all guardrails pass, no forbidden language appears in scanned nested string values outside standard defensive prohibition narratives, and a valid human final authorization decision is present (`authorized: true` and/or `authorization_decision: "authorized"` and/or `decision: "authorized"`). This outcome **does not** authorize live execution or runtime source activation; it does **not** complete source activation; it only documents that the readiness decision artifact may advance to the **later non-runnable activation handoff packet** gate for separate non-runnable handoff documentation.
- **Blocked** when Sprint 90 input is missing or invalid, the Sprint 90 decision packet is blocked, the Sprint 90 packet is not approved for final source activation authorization, any required guardrail fails, forbidden language appears in scanned inputs or authorization rationale, or the human final authorization decision is missing, rejected, denied, blocked, ambiguous, conflicting, or otherwise invalid.

The strongest positive outcome after final authorization remains **authorization to consider a separate later non-runnable activation handoff packet**, not execution, activation, scraping, ingestion, scheduling, runtime mutation, or source activation completion.

## Relationship to Sprint 90

Sprint 90 remains the source activation readiness decision packet layer over Sprint 89. Sprint 91 consumes that decision packet locally and produces a final authorization artifact for the next documentation gate without changing runtime state.
