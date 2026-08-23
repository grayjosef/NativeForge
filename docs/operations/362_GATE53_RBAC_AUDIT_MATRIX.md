# 362 — Gate 53: RBAC privilege matrix + audit events

Status: contracts implemented and tested.
Service: `src/nativeforge/services/rbac_privilege_matrix_service.py`
Tests: `tests/test_tenant_authority_discovery_gate51_57.py`

## Design

Safe by default. A capability is denied unless the matrix grants it, and the
authority-sensitive subset needs a verified authority proof **on top of** the
grant. Two layers, both of which must clear.

Extends rather than replaces `rbac_policy_contract_service` (Block 35), which
uses the older role vocabulary and stays in force for existing surfaces.

## Role capabilities

| Role | Capabilities |
| --- | --- |
| `org_owner` | view workspace, manage org profile, manage seats, approve admins, view org audit events, request authority verification, manage workspace settings, assign grant leads |
| `org_admin` | view workspace, manage seats, manage workspace settings, assign grant leads, request authority verification |
| `authorized_representative` | view workspace, request authority verification, **certify org facts**, **approve package readiness**, **final package signoff** — all three authority-gated |
| `grant_lead` | view workspace, manage pursuit workflow, assemble evidence, draft package, request review |
| `reviewer` | view workspace, comment/review, flag issues |
| `viewer` | view workspace |
| `operator_internal` | support review access, view workspace — audited, never customer authority |
| `unknown` | nothing |

Note `org_admin` cannot self-certify: `certify_org_facts` is not in its set. An
admin who is also a verified authorized representative gets it through that
role, not through being an admin.

## Authority-gated capabilities

`certify_org_facts`, `approve_package_readiness`,
`final_application_package_signoff`. Each maps to an authority-sensitive action
and is evaluated through `evaluate_authority_sensitive_action`, so the Gate 52
rules (verified, unexpired, unrevoked, no missing evidence) apply unchanged.

## Permanently blocked capabilities

`controlled_customer_pilot_go`, `production_rollout_go`, `enable_login_live`,
`enable_production_storage`, `declare_pen_test_passed`,
`final_submit_to_portal`.

These are checked **first**, before the role lookup, and return denied for
every role including `org_owner` and `operator_internal`. There is no role in
the system that can flip a production gate. An invariant additionally fails the
matrix if any role is ever granted one.

## Audit events

21 event types:
`tenant_access_denied`, `seat_invite_created`, `seat_invite_blocked_limit`,
`seat_limit_override_requested`, `seat_limit_override_approved`,
`role_changed`, `authority_proof_requested`, `authority_proof_submitted`,
`authority_proof_verified`, `authority_proof_rejected`,
`authority_proof_expired`, `authority_proof_revoked`,
`authority_sensitive_action_blocked`, `cross_org_access_attempt`,
`feedback_alert_attempted`, `feedback_alert_failed`,
`source_candidate_discovered`, `source_candidate_promoted`,
`source_candidate_blocked`, `opportunity_duplicate_flagged`,
`opportunity_source_stale`.

Every emitted event carries `persisted: false`. Audit events are **modeled, not
stored** — customer persistence is not live and this must not be mistaken for
an audit log.

## Role changes

`record_role_change` flags `is_privilege_escalation` when someone moves into
`org_owner` / `org_admin` / `authorized_representative` from a lower role, and
always sets `grants_customer_authority_immediately=false`. Becoming an
authorized representative starts the authority proof workflow; it does not
complete it.

## Proven by test

- matrix is deny-by-default and passes its invariants
- no role can obtain a permanently blocked capability
- viewer / reviewer / grant_lead cannot certify or approve
- `operator_internal` cannot certify; its support access carries no authority
- authority-gated capability denied without proof, allowed with verified proof,
  denied again when evidence is missing
- role change is audited and grants nothing immediately
