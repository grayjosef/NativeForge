# NativeForge active source activation operator decision review (v1)

## Sprint 67 purpose

Sprint 67 adds a deterministic, side-effect-free Python service that builds **`nf_active_source_activation_operator_decision_review_v1`** artifacts. Each artifact summarizes whether a Sprint 66 **`nf_active_source_activation_command_package_v1`** preview package is structurally suitable for a **future** activation authorization workflow review. It does **not** activate sources, create active source rows, execute `command_preview` entries, open database sessions, scrape, ingest, call external URLs or LLMs, write to the runtime database, mutate ledgers, or run Alembic.

## Inputs

- **`activation_command_package_artifact`**: output of `build_active_source_activation_command_package` (Sprint 66), type `nf_active_source_activation_command_package_v1`.

## Outputs

The operator decision review includes:

- **`artifact_type`**: `nf_active_source_activation_operator_decision_review_v1`
- **`version`**: `v1`
- **`generated_at`**: fixed deterministic timestamp (`1970-01-01T00:00:00Z`) for reproducible artifacts
- **`command_package_reference`**: key fields copied from the Sprint 66 package for traceability
- **`package_readiness_summary`**: validation summary (counts, failure codes) for operator scanning
- **`operator_decision`**: either `ready_for_future_activation_authorization_review` or `blocked_operator_decision_review` — never an activation approval or execution claim
- **`decision_reasons`**, **`approval_blockers`**: aligned lists explaining the outcome
- **`required_operator_actions`**: reminders that preview artifacts are not executable authorization
- **`risk_review`**, **`rollback_review`**, **`command_preview_review`**: structured notes derived from the command package where present
- **Guardrails**: top-level **`preview_only`**, **`no_execution`**, **`explicit_preview_only_no_execution_guardrail`**, **`future_authorization_required`**, zero **`actual_*`** counts, false **`may_*`** flags, and Sprint 67 proof dict — consistent with prior NativeForge activation-review artifact posture

## Decision rules

- **Ready (for future authorization review only)** when the command package is Sprint 66 v1, declares preview-only posture at the package and `preview_guardrail` level, reports `readiness_decision` as the Sprint 66 preview-ready value, has **no** `blocked_candidates`, carries a **non-empty** `command_preview` whose entries all declare `preview_only` and `no_execution`, includes a valid `source_review_packet_reference` to `nf_active_source_activation_review_packet_v1` with candidate id and target metadata, and preserves zero `actual_*` counts with no true `may_*` flags.
- **Blocked** when any of the above fails — including empty `command_preview`, missing preview-only guardrails, non-zero `actual_*` counts, true `may_*` flags, or blocked candidates on the incoming package.

The strongest positive outcome remains **readiness for a future authorization review**; live activation still requires separate operator execution and authorization paths.

## Relationship to Sprint 66

Sprint 66 remains the **preview-only** command package. Sprint 67 consumes that artifact locally and produces an operator-facing decision review scaffold without changing runtime state.
