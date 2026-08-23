# 361 — Gate 52: Authority proof + authorized representative workflow

Status: contracts implemented and tested.
Service: `src/nativeforge/services/authority_proof_workflow_service.py`
Tests: `tests/test_tenant_authority_discovery_gate51_57.py`

## The rule

A person must prove they may speak or apply for an organization before any
authority-sensitive action unlocks. **Submitted is not verified**, and
verification lapses.

This models the organization-level proof lifecycle. It composes with
`applicant_authority_contract_service` (Block 28), which models the
per-opportunity authority record that this gates.

## Authority-sensitive actions

`final_eligibility_assertion`, `official_submission_readiness`,
`official_package_approval`, `certify_official_org_facts`,
`represent_board_resolution_approval`,
`authorized_representative_certification`, `claim_sam_uei_ebiz_aor_status`,
`claim_state_portal_authority`, `final_application_package_signoff`.

## States

`not_started`, `requested`, `submitted`, `under_review`, `verified`,
`rejected`, `expired`, `revoked`, `unknown`.

**Only `verified` unlocks.** Every other state, including `unknown`, blocks.
That is enforced structurally: `BLOCKING_STATES` is derived as
`PROOF_STATES - UNLOCKING_STATES`, so a state added later blocks by default
instead of silently permitting.

## Proof types

Organizational email/domain evidence · board or officer attestation · tribal
resolution or authorization letter · grant office assignment ·
SAM.gov / UEI / EBiz / AOR evidence · state portal administrator proof ·
uploaded governance document · operator-reviewed exception.

## Two derived guards

Two things are computed rather than trusted from the caller:

1. **Expiry is derived.** A record passed in as `verified` with an
   `expires_at` in the past becomes `expired`. The caller cannot assert
   freshness it does not have.
2. **Verification requires a verifier.** A `verified` state with no
   `verified_by` degrades to `under_review`. A verified flag with nobody
   attached to it is not verification.

## Two independent gates

`evaluate_authority_sensitive_action` requires **both**:

1. verified, unexpired, unrevoked proof held by an authority-capable role
   (`org_owner`, `org_admin`, `authorized_representative`)
2. no missing evidence

An `authorized_representative` clears gate 1. It can **never** clear gate 2 by
role alone — that is the specific bypass this gate exists to prevent, and it is
asserted in a dedicated test.

`reviewer`, `viewer` and `grant_lead` are not authority-capable at all, so a
verified proof attached to those roles still does not unlock.

## What a proof record never asserts

Every record carries, and invariants enforce, `sam_uei_status_claimed=false`,
`aor_status_claimed=false`, `portal_access_claimed=false`,
`tribal_facts_asserted=false`, `final_eligibility_claimed=false`. Submitting
SAM/UEI evidence records *that evidence was submitted* — it never asserts the
registration is valid.

## Proven by test

- submitted proof is not verified and blocks package approval
- `verified` with no verifier degrades to `under_review`
- rejected / expired / revoked all block final signoff
- verified proof expires against a supplied `now`
- unknown authority blocks submission readiness
- authorized representative cannot bypass missing evidence
- reviewer can never hold authority even when marked verified
- revocation removes the unlock and emits `authority_proof_revoked`
- no external status is ever claimed
