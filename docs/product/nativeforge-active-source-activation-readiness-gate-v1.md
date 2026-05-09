# NativeForge active source activation readiness gate (v1)

## Sprint 64 purpose

Sprint 64 introduces the first **activation readiness gate** artifact: `nf_active_source_activation_readiness_gate_v1`. This gate consumes the post-runtime verification artifact and states what must exist before any **future** activation review or execution sprint, without performing activation.

## What this gate does

- Validates that a Sprint 64 post-runtime verification artifact is present and, when the artifact type matches, whether its `readiness_decision` is `verified_runtime_source_row_ready_for_activation_gate`.
- Optionally cross-checks a Sprint 62/63 runtime evidence artifact when the caller supplies it; omission is allowed.
- Copies the verified row id and snapshot from post-runtime verification into `activation_candidate_source_row_id` and `activation_candidate_snapshot`.
- Enumerates **required future activation review artifacts** and operator, legal, access, provenance, duplicate, rate-limit, failure-mode, and rollback review requirements.
- For Sprint 64’s default path, returns `blocked_requires_activation_review_artifacts` because the dedicated review artifacts do not exist yet.

## What this gate does not do

- Does **not** activate the source or open database sessions.
- Does **not** scrape, ingest, call external APIs, or call LLMs.
- Does **not** create operator ledger actions or modify schema.
- Does **not** insert, update, or delete `nf_active_opportunity_sources` rows.

## Readiness decisions

- `not_ready`
- `blocked_missing_post_runtime_verification`
- `blocked_post_runtime_verification_invalid` (wrong artifact type)
- `blocked_source_not_verified` (artifact type ok but post-runtime readiness not verified)
- `blocked_requires_activation_review_artifacts` (default success chain for Sprint 64)
- `ready_for_future_activation_review_packet` (only when explicit placeholder review artifacts are supplied to the gate)

## Required future activation review artifacts (enumerated)

The gate lists the following keys under `activation_required_future_artifacts`:

- `legal_tos_activation_review_artifact`
- `public_access_activation_review_artifact`
- `provenance_capture_activation_review_artifact`
- `duplicate_source_activation_review_artifact`
- `rate_limit_and_fetch_cadence_activation_plan`
- `failure_mode_and_backoff_plan`
- `rollback_activation_plan`
- `operator_activation_confirmation_packet`

## Next sprint

Build the **activation review packet scaffolding** and populate these artifacts under operator control; this remains distinct from live activation.

## Implementation

- `src/nativeforge/services/active_source_activation_readiness_gate_service.py` — `build_active_source_activation_readiness_gate`
