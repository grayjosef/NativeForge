# NativeForge active source activation command package (v1)

## Sprint 66 purpose

Sprint 66 adds a deterministic, side-effect-free Python service that builds **`nf_active_source_activation_command_package_v1`** artifacts. Each artifact is a **preview-only** description of what an operator execution sprint would need to activate a candidate source that already passed **Sprint 65**’s activation review packet scaffolding. It does **not** activate sources, open database sessions, scrape, ingest, call external URLs or LLMs, write to the runtime database, mutate ledgers, or run Alembic.

## Inputs

- **`activation_review_packet_artifact`**: output of `build_active_source_activation_review_packet` (Sprint 65), type `nf_active_source_activation_review_packet_v1`.

## Outputs

The command package includes:

- **`artifact_type`**: `nf_active_source_activation_command_package_v1`
- **`version`**: `v1`
- **`generated_at`**: fixed deterministic timestamp (`1970-01-01T00:00:00Z`) for reproducible artifacts
- **`source_review_packet_reference`**: key fields copied from the Sprint 65 packet for traceability
- **`activation_candidates`**: candidate rows eligible for **preview** when the Sprint 65 packet is structurally ready and embedded validations report success
- **`blocked_candidates`**: packet-level blockers when the review packet is missing, not ready, fails embedded validation, or lacks a candidate id
- **`required_operator_actions`**: operator work still required before any live execution
- **`activation_preconditions`**, **`activation_risks`**, **`rollback_notes`**: structured guidance only
- **`command_preview`**: descriptive “would” commands with **`preview_only`** and **`no_execution`** set—never executable from this artifact alone
- **Guardrails**: top-level **`preview_only`**, **`no_execution`**, **`preview_guardrail`**, **`command_execution_boundary`**, zero **`actual_*`** counts, false **`may_*`** flags, and Sprint 66 proof dict—consistent with prior NativeForge activation-review artifact posture

## Relationship to Sprint 65

Sprint 65 remains the legal/policy/operational **review packet** scaffold. Sprint 66 consumes that packet and, only when it declares `ready_for_future_activation_command_package_review` **and** embedded `post_runtime_verification_validation` / `activation_readiness_gate_validation` are valid, describes a **hypothetical** activation command sequence. Individual Sprint 65 sub-artifacts stay scaffolded until human and operator review in a future execution sprint.

## Execution boundary

This artifact is **not** permission to change `nf_active_opportunity_sources`, run fetches, or execute activation. Live activation remains in a dedicated operator execution path with database sessions and explicit approvals.
