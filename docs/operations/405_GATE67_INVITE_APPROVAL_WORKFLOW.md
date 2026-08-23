# 405 — Gate 67G: Invite / approval workflow

How a person becomes a member of an organization in NativeForge, and every place
that path refuses.

**Nothing in this workflow persists.** There is no provisioned database. This is
a decision service: given a proposed action it says whether it is permitted and
what would be recorded.

## Who can invite

Only a role holding the `manage_seats` capability: **`org_owner`** and
**`org_admin`**.

The holder set is read from `ROLE_CAPABILITIES` in
`rbac_privilege_matrix_service` rather than hardcoded here, so a change to the
Gate 57 matrix cannot silently diverge from this gate. A test asserts the set is
exactly `{org_owner, org_admin}` — if the matrix changes, that test fails and
someone has to think about it.

This closes the gap the survey found: `evaluate_seat_invite` takes an
`actor_id`, writes it into an audit event, and never checks it. Seat-cap
enforcement was real; inviter authorization did not exist.

## Who can approve

The same capability, `manage_seats`. Approval and invitation are separate acts
even when the same person may perform both.

**For a seat override the approver must be a different person from the
requester.** Self-approving your own exception to the seat cap is what makes a
cap decorative. Ordinary invites do not carry this restriction — in a five-person
organization the owner inviting and approving is normal — but exceeding the
contracted cap is exactly where separation of duties earns its cost.

## How the seat cap works

Default cap is **5** (`DEFAULT_SEAT_CAP`), matching the Gate 51 seat model.

- Roles in `ORG_ROLES` consume a seat.
- **`operator_internal` does not consume a seat** and cannot be invited as a
  customer role at all. Internal support access is granted by us, not requested
  by a customer, and it never implies customer authority.
- Below the cap: allowed.
- At or above the cap: **blocked**, unless an override is approved.

## How the override works

Three separate things, and only the third permits anything:

1. `seat_override_requested=True` — someone asked. **Not an approval.** Denied
   with `seat_override_requested_but_not_approved`.
2. `seat_override_approved_by` set, but that person lacks `manage_seats` —
   denied.
3. `seat_override_approved_by` set, holds `manage_seats`, and **differs from the
   requester** — permitted, and the resulting `membership_created` event records
   `seat_override_used: true`.

## How an invite becomes a membership

```
draft → pending_approval → approved → sent → accepted → membership
```

Two independent conditions must both hold at the final step:

| Condition | If unmet |
| --- | --- |
| `invite_state == "accepted"` | no membership |
| `approval_state ∈ {approved, not_required}` | membership is `pending_approval`, **not** `active` |

**Acceptance is not activation.** An accepted invite whose approval is still
pending yields a `pending_approval` membership. That is the core rule of this
gate.

Approval is required by default — `approval_required=True` — and a test asserts
the default, because a safe default that silently flips is not a safe default.

### Derived state beats the state column

- A `revoked_at` timestamp means revoked, whatever `invite_state` says.
- An elapsed `expires_at` means expired.

Trusting the column over the timestamp is how a revoked invite gets accepted.

### Deny by default

`INVITE_DENYING_STATES` and `APPROVAL_DENYING_STATES` are computed by
set-difference from the full vocabularies. A state added later denies until
someone deliberately adds it to the live set. Unknown input normalises to
`unknown`, which denies.

## Membership provenance

The gate's central claim, in one function. A membership row is trusted only when
its provenance is `completed_invite` **and** it names the invite:

| Provenance | Trusted |
| --- | --- |
| `completed_invite` with an `invite_id` | yes |
| `completed_invite` with no `invite_id` | **no** — unfalsifiable |
| `operator_direct_write` | **no** |
| `migration_backfill` | **no** |
| `unknown` / unrecognised | **no** |

An operator direct-write is the specific case this gate exists to refuse, and it
emits `authority_sensitive_action_blocked`.

## How membership revokes and expires

**Revocation** requires `manage_seats`. Releases the seat. Emits
`membership_revoked`, or `tenant_access_denied` if the actor was not authorized.

**Expiry** takes no actor and requires no authorization. It is a fact about
time, not an action someone performs — modelling it as an action would imply
somebody must remember to do it, and a membership that stays live because nobody
ran a job is a security failure. Emits `membership_expired` only when the
expiry has actually elapsed against a caller-supplied `now`.

## Role changes

Authorized here; described by `record_role_change` in the RBAC service, which
had the same missing-authorization gap.

- Requires `manage_seats`.
- Cannot change **into** `operator_internal`, or **out of** it through this path.
- No-op changes are denied.
- Upgrade and downgrade are distinguishable via a seniority ranking.
- Escalation into `org_owner` / `org_admin` / `authorized_representative` is
  flagged.
- **A denied change does not alter the role** — the returned `new_role` stays
  equal to `old_role`, and an invariant enforces it.
- `grants_customer_authority_immediately` is always `False`. A role is
  permission to ask; authority still requires a verified authority proof at use
  time.

## Which audit events fire

| Situation | Event |
| --- | --- |
| Invite activates a membership | `membership_created` |
| Any invite denial | `tenant_access_denied` |
| Untrusted membership provenance | `authority_sensitive_action_blocked` |
| Authorized role change | `role_changed` |
| Denied role change | `tenant_access_denied` |
| Authorized revocation | `membership_revoked` |
| Denied revocation | `tenant_access_denied` |
| Elapsed expiry | `membership_expired` |

All carry `persisted: false`. An invariant fails any event claiming otherwise,
and separately fails any attempt to emit `cross_org_access_attempt`, which
Gate 65 established the current schema cannot represent.

## What is still not persisted

All of it. No invite row, no approval row, no membership row, no audit row.
Persistence design is in doc 404; it needs a provisioned database and its own
migration.

## Why the pilot remains NO_GO

A customer cannot log in — login is not live. Their membership cannot be stored
— no database is provisioned. Their denials cannot be audited — no sink is
wired. This gate made the membership *creation path* safe; it did not make any
of those three true.

```text
Controlled customer pilot: NO_GO
Production rollout:        NO_GO
Customer login live:       NO
Production storage live:   NO
```
