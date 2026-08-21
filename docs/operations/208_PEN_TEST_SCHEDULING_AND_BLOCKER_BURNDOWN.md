# Pen-Test Scheduling + Blocker Burn-Down (Gate 16 / Block 38)

## Recommended window

Friday–Saturday before Sunday readiness gate.

## Inventory reference

* `/?view=sc_customer_demo`
* `/api/*`
* `docs/operations/189_EXTERNAL_PEN_TEST_EXECUTION_PACKET.md`

## Accounts / seed

* Operator fixture, customer org A, customer org B (cross-org deny)
* SC curated demo pack, multi-org cohort, evidence intake samples

## Out of scope

* Collaboration matching (dark/OFF)
* Live SAM/AOR verification
* Production customer data mutation

## Top blockers

| Blocker | Severity | Owner | Sunday? |
|---------|----------|-------|---------|
| external_auth_not_configured | critical | Mayhem | yes |
| production_storage_not_approved | critical | Mayhem | yes |
| pen_test_not_scheduled | high | Mayhem/vendor | yes |
| python_sca_incomplete_or_findings | high | build_agent | yes |
| live_authority_verification | medium | Mayhem | unlikely |

## Claims

* pen_test_passed: **false**
* pen_test_scheduled: **false** (packet ready only)
* controlled customer pilot: **NO_GO**
