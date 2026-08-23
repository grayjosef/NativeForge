# 406 — Gate 67F: Membership lifecycle audit

Gate 65 added 13 security verbs to `AuditAction`. Four concerned membership
lifecycle and **none had an emitter**. This gate gives three of them one and adds
an authorized path for the fourth.

## Emitter status

| Verb | Before Gate 67 | After |
| --- | --- | --- |
| `membership_created` | no emitter | emitted on invite activation |
| `membership_revoked` | no emitter | emitted on authorized revocation |
| `membership_expired` | no emitter | emitted when expiry elapses |
| `role_changed` | described by `record_role_change`, never authorized | emitted only after authorization |
| `tenant_access_denied` | membership directories, API enforcement | + every invite/role/revocation denial |
| `authority_sensitive_action_blocked` | authority workflow | + untrusted membership provenance |
| `cross_org_access_attempt` | Gate 64 adapter; refused at write path | **not emitted here, and an invariant enforces that** |

## Event shape

```json
{
  "event_type": "membership_created",
  "organization_profile_id": "org-profile-1",
  "actor_id": "admin-1",
  "subject_id": "auth0|abc123",
  "detail": { "invite_id": "inv-1", "role": "grant_lead",
              "provenance": "completed_invite", "consumes_seat": true,
              "seat_override_used": false },
  "persisted": false
}
```

`persisted` is hardcoded `false` and three separate invariant functions fail any
event claiming otherwise. It flips only when doc 391's sink is wired against a
provisioned database.

## What each event records, and why that field

**`membership_created`** carries `provenance` and `seat_override_used`. Both are
there so the audit trail answers the questions an incident would ask: did this
membership come through an invite, and did somebody exceed the seat cap to create
it. Without `seat_override_used`, an override is invisible after the fact.

**`membership_revoked`** carries a free-text `reason`. Revocations get disputed
("I was removed without warning"), and the reason is the only context a
reviewer has.

**`membership_expired`** carries both `expires_at` and `observed_at`. The gap
between them is how long a membership stayed live past its expiry, which is a
measure of whether expiry is being enforced promptly or noticed late.

**`role_changed`** carries `direction` (upgrade/downgrade) and
`is_privilege_escalation`. Escalation into `org_owner`, `org_admin`, or
`authorized_representative` is the change worth alerting on; a downgrade to
`viewer` is not.

**Denials** carry the full `reasons` list, not a single summary reason. An invite
usually fails several checks at once, and knowing all of them is the difference
between fixing a misconfiguration in one pass and in four.

## Expiry has no actor, deliberately

Every other lifecycle event takes an `actor_id`. `evaluate_membership_expiry`
does not, and requires no authorization.

Expiry is a fact about time, not an action someone performs. Modelling it as an
action would imply somebody has to remember to do it — and a membership that
stays live because nobody ran a job is a security failure that would then look
like a missing cron entry rather than an access-control defect. The `actor_id` is
explicitly `None` in the emitted event.

## Denial events are emitted on the denial path, not the success path

Every denied action produces either an audit event or an explicit
`blocked_reasons` list, and in practice both. A silent denial is an unobservable
one, and the value of tenant isolation is being able to show it held.

An invariant enforces the weaker half of this: `denied_without_reason` fails any
result that is not `allowed` and carries no reasons.

## Retention and personal data

Both still undecided, and both must be settled before anything here is written
— see doc 391.

The specific concern for this gate: **`invited_email` appears in invite denial
events** via `subject_id` when no subject is known yet. An invite to an address
that never accepts leaves a record of someone who is not a customer and never
became one. That argues for a shorter retention class on invite-denial events
than on membership events, and for dropping `invited_email` from the event once a
subject is resolved.

Doc 391's rule — no email in audit payloads — is in tension with the fact that a
pre-acceptance invite has no other identifier. The honest resolution is probably
to store a hash of the email for correlation and keep the plaintext only on the
invite row, which is deletable. That is a decision for whoever wires the sink,
and it should be made deliberately rather than inherited from this document.

## Not persisted

```text
membership_created:   emitted, persisted=false
membership_revoked:   emitted, persisted=false
membership_expired:   emitted, persisted=false
role_changed:         emitted, persisted=false
tenant_access_denied: emitted, persisted=false
cross_org_access_attempt: NOT EMITTED (unrepresentable until migration 0028)
```
