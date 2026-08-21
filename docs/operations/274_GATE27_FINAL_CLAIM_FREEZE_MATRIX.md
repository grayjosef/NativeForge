# Gate 27 — Final Claim Freeze Matrix

| Class | Examples |
|-------|----------|
| Allowed | monday_demo_internal_go, conditional_internal_only, unlock packet exists, SCA Gate 16 preserved |
| Conditional | mode_b_ready (≠ GO), ready_for_owner_review |
| Forbidden | login_live, production_auth/storage, customer_persistence, pen_test_passed, pilot GO, rollout GO, production_ready |

Frozen booleans all **false** until validators pass.
