# 407 — Gate 67H: Production readiness delta

Gate 67 built the invite / approval workflow. It provisioned nothing and
persisted nothing, so no production claim moves.

## Invite path: now

| | Before | After |
| --- | --- | --- |
| Seat cap enforced | yes (Gate 51) | yes, unchanged |
| Inviter authorized | **no** | **yes — requires `manage_seats`** |
| Invite state machine | seat-decision vocabulary only | 9 states, deny-by-default |
| Expiry / revocation derived from timestamps | no | yes, overriding the state column |

The survey's central finding was that `evaluate_seat_invite` takes an `actor_id`,
writes it into an audit event, and never checks whether that actor holds
`manage_seats`. Seat-cap enforcement was real; **inviter authorization did not
exist**. Any caller could pass any string. That is now closed.

## Approval path: now

| | Before | After |
| --- | --- | --- |
| Approval step distinct from seat decision | **no** | yes, 8 states |
| Approver authorized | **no** | **yes — requires `manage_seats`** |
| Ordinary invite requires approval | **no** | yes, and required by default |
| Override request separate from override approval | **no** | yes |
| Override self-approval prevented | **no** | **yes — approver must differ from requester** |

Before this gate, "approval" meant a non-empty `override_approved_by` string.

## Membership lifecycle: now

Three verbs Gate 65 added had no emitter and now have one:
`membership_created`, `membership_revoked`, `membership_expired`. `role_changed`
now fires only after authorization, closing the same missing-check gap in
`record_role_change`.

Membership **provenance** is now a first-class check. A row is trusted only when
it came from a completed invite that names its invite id. `operator_direct_write`
is explicitly untrusted and emits `authority_sensitive_action_blocked` — the
internal-operator overreach risk this gate exists to close.

## Persistence status

**Nothing persists.** No invite row, no approval row, no membership row. The
service is a decision layer: it says whether an action is permitted and what
would be recorded.

Design is in doc 404. No migration written, deliberately: 0023–0027 were authored
against SQLite and only found their real problems when they first met PostgreSQL
(the seat-cap `CHECK`, the `sa.text("now()")` bug that broke 98 tests). An invite
schema needs RLS policies, a partial unique index on live invites, and
transactional seat counting — more places to be subtly wrong, and writing it now
means writing it blind.

Doc 404 also records a gap worth carrying forward: `nf_org_memberships` has no
`source_invite_id`, so provenance is caller-asserted rather than checkable
against stored data.

## Audit persistence status

**Not wired.** Every emitted event carries `persisted: false`, enforced by three
invariant functions. `cross_org_access_attempt` is not emitted by any path here,
and an invariant fails any result that tries — it remains unrepresentable until
migration 0028.

## Production storage live

**NO.** Unchanged. The five preconditions are unmoved: approval token (held), DB
config (absent), migrations at head (would hold), RLS proof (passed in a
throwaway environment), backup/restore posture (gated in Gate 65, unmet).

## Owner-blocked

- Managed PostgreSQL 16+ and its `DATABASE_URL`, out-of-band
- Backup automation, PITR decision, first restore drill
- Approval for migration 0028 (audit) and a future invite-schema migration
- Retention decision, including the shorter class for invite-denial events
- The email-in-audit resolution flagged in doc 406
- Real `OIDC_*` credentials (Gate 69), pen test, Slack webhook

## Engineering-blocked

- Invite/approval persistence and its RLS proof extension
- `source_invite_id` on `nf_org_memberships`
- Transactional seat counting (`SELECT ... FOR UPDATE`) — the service layer
  cannot fix the concurrent-approval race
- Migration 0028 and its policy widening
- Audit sink (doc 391 step 4)
- Capability enforcement on live routes (71–72), discovery (76–85)

## Controlled customer pilot delta

**None. Still NO_GO.**

```text
Controlled customer pilot: NO_GO
Production rollout:        NO_GO
Customer login live:       NO
Production storage live:   NO
Customer persistence:      NO
Pen-test passed:           NO
Slack live alert:          NOT PROVEN
```

What genuinely changed: a membership can no longer become active because someone
typed it in. The path from invitation to active seat now has an authorized
inviter, an authorized approver distinct from the request, a seat cap that cannot
be self-overridden, and a provenance check that refuses rows of unknown origin.

What did not change: none of that is stored anywhere, and a customer still cannot
log in.
