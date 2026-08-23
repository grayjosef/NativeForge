# 408 — Gate 68A: Audit sink survey

## Current table schema

`nf_audit_events`, migration 0002:

```text
id                  Uuid        PK
organization_id     Uuid        NOT NULL  FK organizations, RLS scoping column
is_demo             Boolean     NOT NULL  RLS scoping column
review_artifact_id  Uuid        NULL      FK
tribal_profile_id   Uuid        NULL      FK
extraction_run_id   Uuid        NULL      FK
action              String(64)  NOT NULL  no CHECK constraint
payload             JSON        NULL
actor_id            Uuid        NULL
created_at          DateTime(tz) NOT NULL
```

RLS enabled and forced; Gate 62 proved the policies execute.

## Current repository behavior

`repositories/audit_events.py`:

- `append_org_audit_event(session, *, organization_id, is_demo, action, payload, actor_id)` — inserts and flushes
- `list_audit_events_for_org(...)` — org-scoped read
- Gate 65 added a guard that **raises `ValueError`** when `action in UNPERSISTABLE_AUDIT_ACTIONS`

Already used in anger by `repositories/pursuits.py` and
`repositories/evidence_pack.py` for workflow events.

## Current verbs

50 in `AuditAction`: 37 workflow + 13 security (Gate 65).

## Events modeled but not persisted

| Source | Events |
| --- | --- |
| `membership_invite_approval_service` (Gate 67) | `membership_created`, `membership_revoked`, `membership_expired`, `role_changed`, `tenant_access_denied`, `authority_sensitive_action_blocked` |
| `postgres_membership_directory_service` (Gate 64) | `tenant_access_denied`, `cross_org_access_attempt` |
| `membership_directory_service` (Gate 61) | `tenant_access_denied` |
| `api_enforcement_service` (Gate 58) | `authority_sensitive_action_blocked`, `tenant_access_denied` |
| `api/tenant_guard.py` | denial decisions, in-memory ring buffer of 200 |
| `rbac_privilege_matrix_service` | `role_changed` (as a string, not the enum) |
| `continuous_source_discovery_service` | `source_candidate_promoted`, `source_candidate_blocked` |
| `authority_proof_workflow_service` | `authority_proof_submitted`, `authority_proof_verified`, `authority_sensitive_action_blocked` |

Every one carries `persisted: false`.

## Events that can be safely persisted today

Those needing exactly **one** organization, which the schema has:

```text
membership_created
membership_revoked
membership_expired
role_changed
tenant_access_denied
authority_proof_submitted
authority_proof_verified
authority_sensitive_action_blocked
source_candidate_promoted
source_candidate_blocked
feedback_alert_attempted
feedback_alert_failed
```

Twelve of the thirteen. Each concerns one org: the one whose data or seat is
involved.

## Events that must be refused until 0028

```text
cross_org_access_attempt
```

One event, and it is the important one. A cross-org attempt has at least three
org concepts:

| Concept | Meaning |
| --- | --- |
| `actor_org_id` | the org whose credentials were used |
| `target_org_id` | the org whose data was reached for |
| `claimed_org_id` | the org the caller asserted, when it differs from both |

`organization_id` is `NOT NULL` and is the RLS predicate, so there is exactly
one slot:

- put the **actor** org in it → the event is scoped to the attacker's tenant and
  **invisible to the tenant that was attacked**
- put the **target** org in it → visible to the victim, but the row now reads as
  though the victim performed the action

Neither is acceptable. Migration 0028 (doc 401) adds the three columns and
widens the read policy so a targeted tenant can see events aimed at it.

## Exact persistence boundary

```text
Persistable today (needs 1 org):   12 verbs
Refused until 0028:                 1 verb  (cross_org_access_attempt)
Refused always:                     unknown/unrecognised actions
Refused always:                     events missing organization_id
Refused always:                     events arriving with persisted:true
Actually persisted right now:       0 — no provisioned database
```

## Gaps the sink must close

1. Nothing collects modeled events. Each service returns them to its caller and
   the caller drops them.
2. No classification exists, so a caller cannot tell a persistable event from an
   unpersistable one without knowing the schema.
3. The Gate 65 guard raises at the repository, which is correct but late — by
   then a caller believes it is writing. Classification should happen before.
4. `tenant_guard` keeps denials in a 200-entry in-memory ring buffer that is
   lost on restart. That is not an audit trail.
5. Nothing detects an event that arrives already claiming `persisted: true` —
   the one input shape that would let a false persistence claim through.

## What the sink must not do

- Not persist `cross_org_access_attempt`.
- Not silently drop any security event. A dropped denial is worse than a failed
  request, because nobody finds out.
- Not claim production audit persistence. There is no database.
