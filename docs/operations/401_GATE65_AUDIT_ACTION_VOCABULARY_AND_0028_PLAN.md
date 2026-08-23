# 401 — Gate 65E/F: Security audit vocabulary and the migration 0028 plan

## What was added

Thirteen security-critical verbs, taking `AuditAction` from 37 members to 50:

```text
tenant_access_denied                 membership_created
cross_org_access_attempt             membership_revoked
role_changed                         membership_expired
authority_proof_submitted            source_candidate_promoted
authority_proof_verified             source_candidate_blocked
authority_sensitive_action_blocked   feedback_alert_attempted
                                     feedback_alert_failed
```

All 37 pre-existing verbs are untouched.

### Why this was safe without a migration

`nf_audit_events.action` is `sa.String(64)` with **no `CHECK` constraint**.
Migration 0018 does add enumerated CHECKs to `nf_operator_actions`, so the
absence here was worth confirming rather than assuming. The longest new verb,
`authority_sensitive_action_blocked`, is 34 characters.

No test asserts an exact `AuditAction` member set, so nothing broke.

Two helper sets were added alongside the verbs so callers do not re-list them
and drift:

- `SECURITY_AUDIT_ACTIONS` — the 13, as a frozenset.
- `UNPERSISTABLE_AUDIT_ACTIONS` — verbs the current schema cannot store
  correctly. Currently `{cross_org_access_attempt}`.
- `audit_action_is_persistable(action)` — deny-by-default on unknown input,
  because a verb this code has never heard of does not belong in a security
  audit trail.

## Having a verb is not having persistence

Nothing writes any of these. There is no provisioned database, and the modeled
events emitted by the six services still carry `"persisted": false`. This gate
added vocabulary, which is step 1 of doc 391's plan; steps 2–6 remain.

## Why `cross_org_access_attempt` cannot be stored today

This is the concrete blocker, and it is a design problem rather than a missing
column count.

A cross-org access attempt involves **two** organizations:

- the **actor org** — whose credentials or session were used
- the **target org** — whose data was reached for

`nf_audit_events.organization_id` is `NOT NULL`, and it is the column the RLS
policy scopes on:

```sql
USING (organization_id = current_setting('app.current_org_id', true)::uuid
       AND is_demo = current_setting('app.current_org_is_demo', true)::boolean)
```

There is exactly one slot, and whichever value goes in it decides who can ever
read the row:

- Write the **actor** org → the event is visible to the tenant that did it, and
  **invisible to the tenant that was attacked**. The reader who most needs it
  cannot see it.
- Write the **target** org → the event is visible to the victim, but the row now
  reads as though the victim performed the action. That is a false accusation
  stored in an audit trail.

Neither is acceptable. So rather than pick the less-bad option and document the
caveat, `append_org_audit_event` now **raises** on this verb:

```python
if action in UNPERSISTABLE_AUDIT_ACTIONS:
    raise ValueError(...)
```

It raises rather than silently dropping. A security event that vanishes is worse
than a request that fails, because nobody finds out. Once 0028 lands, the guard
is removed in the same change that adds the columns.

## Proposed migration 0028

Not written in this gate. It needs owner approval like 0023–0027 did, and it
should be authored against a provisioned instance so the RLS policy change can
actually be proved rather than reasoned about.

### Columns

| Column | Type | Null | Purpose |
| --- | --- | --- | --- |
| `actor_identity_id` | `Uuid` FK `nf_identities.id` | yes | Resolved actor, when there is one |
| `actor_subject` | `String(255)` | yes | The `(issuer, subject)` presented. Usually the only actor fact available on a denial |
| `actor_issuer` | `String(512)` | yes | Subject is only unique per issuer |
| `actor_org_id` | `Uuid` FK `organizations.id` | yes | Org the actor belonged to |
| `target_org_id` | `Uuid` FK `organizations.id` | yes | Org whose data was reached for |
| `claimed_org_id` | `Uuid` FK `organizations.id` | yes | Org the caller *asserted*, when it differs from both |
| `outcome` | `String(32)` | yes | `allowed` / `denied` / `blocked` / `error`. Queryable without JSON extraction |
| `severity` | `String(16)` | yes | `info` / `warning` / `critical` |
| `correlation_id` | `String(64)` | yes | Stitches multiple events from one request together |
| `request_id` | `String(64)` | yes | Ties an event to a request log line |
| `event_metadata` | `JSONB` (Postgres) / `JSON` | yes | Structured detail |

Every column nullable, so existing rows stay valid and the migration needs no
backfill.

Note on naming: `event_metadata`, not `metadata` — `metadata` is reserved on
SQLAlchemy declarative classes and would collide with `Base.metadata`.

### The RLS policy change is the hard part

Adding columns is trivial. Making the row readable by the *right* tenant is not.
The policy has to become something like:

```sql
USING (
  is_demo = current_setting('app.current_org_is_demo', true)::boolean
  AND (
    organization_id = current_setting('app.current_org_id', true)::uuid
    OR target_org_id = current_setting('app.current_org_id', true)::uuid
  )
)
```

so a targeted tenant can see events aimed at it. That widens read visibility on
a table that currently has exactly one predicate, which means:

1. It must be proved with `verify_nativeforge_postgres_rls.sh --verify-rls`,
   including a new check that an actor org **cannot** read an event where it is
   only the target — otherwise the widening leaks in the other direction.
2. `WITH CHECK` must stay narrow. Read visibility widening must not let a tenant
   *write* a row naming another tenant as target, which would be a way to forge
   accusations.
3. Deciding what the victim sees needs thought: they should learn that an
   attempt happened, and probably not learn the attacker's subject identifier.
   That may mean the victim reads a redacted projection rather than the raw row.

Point 3 is a product and privacy decision, not an engineering one, and it should
be settled before the migration is written.

### Also required before any write

- **Retention.** Still undecided (doc 391). An unbounded denial stream is a
  cheap denial-of-service against our own storage bill. Decide before wiring.
- **No email in payloads.** Denial events concern people who may not be
  customers. `subject`/`issuer` are pseudonymous and storable; email is directly
  identifying, is not needed to investigate a denial, and would turn the audit
  table into a shadow user directory.

## Status

```text
Audit vocabulary:          COMPLETE (50 verbs)
Audit persistence:         NOT WIRED
cross_org_access_attempt:  BLOCKED from persistence, enforced at the write path
Migration 0028:            PLANNED, not written, needs owner approval
Production storage live:   NO
```
