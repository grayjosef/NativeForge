# 404 — Gate 67E: Invite / approval persistence design

Design only. **No migration is written in this gate**, and none should be until
a database exists to prove it against.

## Why no migration now

Migration `0028` is already planned (doc 401) for the *audit* schema, and the
prompt is right that these should stay separate — they have different owners,
different risk, and different approval conversations.

Beyond that, the pattern from Gates 62 and 64 argues for waiting: 0023–0027 were
written against SQLite and only found their real problems when they first met
PostgreSQL. The seat-cap `CHECK` turned out to be Postgres-only. `sa.text("now()")`
broke 98 tests. An invite schema with RLS policies and a partial unique index has
more places to be subtly wrong than those did, and writing it now means writing
it blind.

The workflow it would serve also does not exist yet on any route. There is
nothing to store.

## Proposed tables

### `nf_membership_invites`

| Column | Type | Null | Notes |
| --- | --- | --- | --- |
| `id` | `Uuid` PK | no | |
| `organization_id` | `Uuid` FK `organizations.id` | no | RLS scoping column |
| `is_demo` | `Boolean` | no | matches every other scoped table |
| `invited_email` | `String(320)` | yes | delivery address only, never an identity key |
| `invited_subject` | `String(255)` | yes | populated on acceptance |
| `invited_issuer` | `String(512)` | yes | subject is only unique per issuer |
| `requested_role` | `String(64)` | no | CHECK: in `ORG_ROLES`, never `operator_internal` |
| `requested_by` | `Uuid` FK `nf_identities.id` | no | |
| `invite_state` | `String(32)` | no | CHECK against the 9 states |
| `approval_required` | `Boolean` | no | default `true` |
| `seat_override_requested` | `Boolean` | no | default `false` |
| `token_hash` | `String(64)` | yes | **hash only, never the token** |
| `created_at` / `expires_at` / `accepted_at` / `revoked_at` | `DateTime(tz)` | | `created_at` via `sa.func.now()`, never `sa.text("now()")` |

### `nf_membership_approvals`

Separate table rather than columns on the invite, because an override approval
and an invite approval are different decisions by potentially different people,
and a one-to-many keeps both auditable.

| Column | Type | Null | Notes |
| --- | --- | --- | --- |
| `id` | `Uuid` PK | no | |
| `organization_id` | `Uuid` FK | no | RLS scoping |
| `is_demo` | `Boolean` | no | |
| `invite_id` | `Uuid` FK `nf_membership_invites.id` | no | |
| `approval_kind` | `String(32)` | no | `invite` \| `seat_override` |
| `approval_state` | `String(32)` | no | CHECK against the 8 states |
| `approved_by` | `Uuid` FK `nf_identities.id` | yes | |
| `decided_at` | `DateTime(tz)` | yes | |

**Constraint worth writing into the schema:** for
`approval_kind='seat_override'`, `approved_by` must differ from the invite's
`requested_by`. Enforcing separation of duties in the database as well as the
service means it survives a future caller that forgets.

### `nf_membership_lifecycle_events`

Deliberately **not proposed.** It would duplicate `nf_audit_events`, which
already exists, is org-scoped, is RLS-covered, and now has the vocabulary
(`membership_created`, `membership_revoked`, `membership_expired`,
`role_changed`) added in Gate 65. A second event table would split the security
audit trail across two places, which is worse than having one imperfect one.

Lifecycle events should go to `nf_audit_events` via doc 391's sink, once
migration 0028 gives it the actor/target columns it needs.

## Required org scoping and RLS

Both tables carry `organization_id NOT NULL` and `is_demo`, and both need the
same policy migration 0027 applied to memberships:

```sql
ALTER TABLE nf_membership_invites ENABLE ROW LEVEL SECURITY;
ALTER TABLE nf_membership_invites FORCE ROW LEVEL SECURITY;
CREATE POLICY nf_membership_invites_org_demo_scope ON nf_membership_invites
  USING (organization_id = current_setting('app.current_org_id', true)::uuid
         AND is_demo = current_setting('app.current_org_is_demo', true)::boolean)
  WITH CHECK (same);
```

`WITH CHECK` matters more here than on most tables: without it, a session scoped
to org A could write an invite into org B and effectively grant itself a seat in
someone else's organization. That is the same attack Gate 62 proved was blocked
for `nf_org_memberships`, and the proof would need extending to these tables —
`verify_nativeforge_postgres_rls.sh` gains two more check pairs.

## The pending-invite uniqueness problem

One live invite per (organization, email) at a time, or a race lets two
approvals both land and consume two seats for one person.

A plain unique constraint is wrong — it would block re-inviting someone whose
earlier invite expired. A **partial unique index** is the right shape:

```sql
CREATE UNIQUE INDEX uq_nf_membership_invites_live
  ON nf_membership_invites (organization_id, lower(invited_email))
  WHERE invite_state IN ('draft','pending_approval','approved','sent');
```

Partial indexes are PostgreSQL-only. SQLite supports partial indexes too, but
not `lower()` in an index predicate in all versions — another reason to author
this against a real instance rather than guess, and another reason the seat-cap
asymmetry from migration 0025 is worth remembering.

## Seat counting is a query, not a column

Tempting to keep `seats_used` on `organizations`. It should be derived:

```sql
SELECT count(*) FROM nf_org_memberships
WHERE organization_id = :org AND state = 'active'
```

plus live invites that will consume a seat. A denormalised counter drifts, and a
drifted seat counter either blocks a legitimate sixth person or silently allows a
seventh. If the count becomes a performance problem, that is what a materialized
view is for.

**Counting must happen inside the same transaction as the insert**, or two
concurrent approvals both read 4 and both write, producing 6 seats under a cap of
5. The service layer cannot fix this; it needs `SELECT ... FOR UPDATE` on the
organization row or a serializable transaction.

## How it maps to `nf_org_memberships`

An approved, accepted invite produces exactly one membership row:

| Invite field | Membership field |
| --- | --- |
| `organization_id` | `organization_id` |
| resolved `(issuer, subject)` → identity | `identity_id` |
| `requested_role` | `role` |
| — | `role_source = 'membership_record'` |
| — | `membership_source = 'org_owner_approved'` |
| approval's `approved_by` | `approved_by` |
| — | `state = 'active'` |

Migration 0024's existing CHECK already requires `approved_by IS NOT NULL` for
any source other than `verified_directory`, which lines up with this gate:
an approval-requiring source must name its approver.

**A provenance column is missing.** Today a membership row cannot say which
invite created it, so `evaluate_membership_provenance` has no persisted field to
read. Adding `source_invite_id` (nullable FK) to `nf_org_memberships` would make
provenance checkable rather than caller-asserted — worth including whenever this
migration is written.

## Why live persistence is not claimed

No managed PostgreSQL instance is provisioned. `production_storage_live` is
`false` and requires all five preconditions from
`postgres_membership_directory_service`, of which DB config and backup posture
are unmet.

```text
Invite persistence:      NOT LIVE
Approval persistence:    NOT LIVE
Membership persistence:  NOT LIVE
Audit persistence:       NOT WIRED
Production storage live: NO
```
