# 403 — Gate 67A: Invite / approval survey

Surveyed before implementing. Two existing services already touch this ground,
and the interesting finding is not that they are missing pieces — it is that
both **record an actor without ever authorizing one**.

## Files inspected

| File | Relevant surface |
| --- | --- |
| `services/org_tenant_seat_model_service.py` (416 ln) | `DEFAULT_SEAT_CAP=5`, `ORG_ROLES`, `INTERNAL_ROLES`, `SEAT_CONSUMING_ROLES`, `INVITE_STATES`, `evaluate_seat_invite` |
| `services/rbac_privilege_matrix_service.py` (316 ln) | `CAPABILITIES` incl. `manage_seats`, `ROLE_CAPABILITIES`, `record_role_change`, `PERMANENTLY_BLOCKED_CAPABILITIES` |
| `services/membership_directory_service.py` | Gate 61 in-memory adapter, trust derivation |
| `services/postgres_membership_directory_service.py` | Gate 64 production-path reader |
| `services/api_enforcement_service.py` | Gate 58 request-path enforcement |
| `domain/enums.py` | `AuditAction` (50), `SECURITY_AUDIT_ACTIONS`, `UNPERSISTABLE_AUDIT_ACTIONS` |
| `repositories/audit_events.py` | append/list, with the Gate 65 unpersistable guard |
| `alembic/versions/0023–0027` | identities, memberships, org enrichment, authority, RLS |
| docs 391 / 401 / 402 | audit wiring plan, 0028 plan, Gate 65 delta |

## What membership path exists

Complete as a *read* path: verified token → `(issuer, subject)` identity →
membership row → trusted role → capability decision. Gate 64's
`PostgresMembershipDirectory` reads it; Gate 61's in-memory adapter models it.

**There is no creation path.** Nothing in the codebase creates a membership row
through any workflow. The only way a row could exist is a direct write.

## What invite path exists

Partial. `evaluate_seat_invite(tenant, invitee_id, role, actor_id,
override_approved_by)` decides the **seat question** well:

- `operator_internal` does not consume a seat and carries no customer authority
- `unknown` role is denied
- within cap → allowed
- at cap → blocked unless `override_approved_by` is supplied
- every branch emits an audit event

**The gap: `actor_id` is recorded but never checked.** The function takes an
actor, writes it into the audit event, and never asks whether that actor holds
`manage_seats`. Any caller can pass any string. Seat-cap enforcement is real;
inviter authorization does not exist.

`INVITE_STATES` there is a seat-decision vocabulary (`draft`,
`blocked_seat_limit`, `pending_override_approval`, `sent`, `accepted`,
`revoked`, `expired`, `unknown`) — it has no notion of an approval step
distinct from the seat decision.

## What approval path exists

Only the seat **override** approval, and only as "was a non-empty
`override_approved_by` string supplied". There is:

- no approval state machine
- no requirement that an ordinary invite be approved before it activates
- no check that the approver holds `manage_seats`
- no separation between requesting an override and approving one

`record_role_change(organization_profile_id, actor_id, subject_id, old_role,
new_role)` has the same shape of gap: it correctly flags
`is_privilege_escalation` and hardcodes
`grants_customer_authority_immediately=False`, but it **records** a role change
rather than **authorizing** one. Nothing checks the actor.

## What audit verbs exist

All 50, after Gate 65. Relevant here:

| Verb | Emitter today |
| --- | --- |
| `membership_created` | **none** |
| `membership_revoked` | **none** |
| `membership_expired` | **none** |
| `role_changed` | `record_role_change` emits the *string*, not the enum member |
| `tenant_access_denied` | membership directories, API enforcement |
| `authority_sensitive_action_blocked` | authority workflow service |
| `cross_org_access_attempt` | Gate 64 adapter — **refused at the write path** |

Four of the verbs Gate 65 added still have no emitter. Gate 67 gives three of
them one (`membership_created`, `membership_revoked`, `membership_expired`) and
adds an authorized path for `role_changed`.

## What is still not persisted

Everything in this gate. There is no provisioned database, so:

- no invite row is written
- no approval row is written
- no membership row is written
- no audit row is written; every emitted event carries `persisted: false`
- `cross_org_access_attempt` stays unpersistable until migration 0028

## What must remain dry-run

The whole workflow. Gate 67 produces a **decision service**: given a proposed
invite, approval, acceptance, role change, revocation or expiry, it says whether
that is permitted and what audit events it would emit. It writes nothing.

## Exact gaps Gate 67 closes

1. Inviter is never authorized → require `manage_seats`.
2. Approver is never authorized → require `manage_seats`.
3. No approval state distinct from the seat decision → add one.
4. An accepted invite can activate membership with no approval → block it.
5. Override request and override approval are the same act → separate them, and
   require a **different** person for the override.
6. Role change is recorded but not authorized → authorize it.
7. `membership_created` / `_revoked` / `_expired` have no emitter → add one.
8. Direct membership creation is indistinguishable from invited membership →
   make untrusted-provenance explicit and deny it.

## What Gate 67 does not do

No migration, no persistence, no route wiring. The seat model and RBAC services
are **not modified** — the new service composes with them and adds the
authorization layer they lack, so their existing tests keep their meaning.
