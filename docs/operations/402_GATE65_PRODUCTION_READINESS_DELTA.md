# 402 — Gate 65H: Production readiness delta

Gate 65 built the backup/restore proof path and added the security audit
vocabulary. It provisioned nothing and executed no backup or restore, so no
production claim moves.

## Backup / restore path: now

| Requirement from the Gate 61 approval | Before | After |
| --- | --- | --- |
| Backup policy | nothing in the repo | RTO/RPO documented in doc 400 |
| Daily automated backups | nothing | gate exists, **not configured** |
| PITR where supported | nothing | modelled as two separate facts, **neither true** |
| Restore test recorded as an artifact | nothing | format defined, executable path exists, **never run** |
| Documented RTO/RPO | nothing | **RTO 240 min, RPO 60 min** |

What did not exist before this gate: any backup capability at all. `grep -rn
"pg_dump\|pg_restore" src/ scripts/` returned nothing across the whole repo.

### The pre-existing services are not this

`gate32_backup_restore_service` and `gate33_restore_rehearsal_service` (campaign
Blocks 73 and 77) look like they cover this ground. They do not. Both promote
restore status on any **non-empty string** passed as `restore_evidence_ref`, and
`gate33` defaults `restore_attempted=True` with a literal
`nf://gate33/non-prod-restore-rehearsal` reference — called with no arguments it
reports a rehearsal that did not happen.

They are honest demo surfaces and are labelled non-prod. They are not evidence.
Gate 65 left them untouched and built alongside, because the alternative was
extending a layer whose central concept is an unvalidated string.

The new service opens the path it is given. A missing file is
`restore_artifact_path_does_not_exist`, not a pass.

### A gap the documented objectives expose

RPO of 60 minutes **cannot be met by daily backups alone** — daily-only implies
an RPO nearer 1440 minutes. Either PITR gets enabled or backup frequency
increases. Writing the objectives down is what made this visible; it had never
been stated before.

## Restore proof status

**Never executed.** `--verify-restore` is implemented and refuses to run without
an explicit `NF_RESTORE_TARGET_URL` that differs from the source, by both full
URL and database name. A restore proof that overwrites the database it is
proving is an outage, not a proof.

`rls_not_reproven_after_restore` blocks readiness until the RLS harness has been
re-run against the restored target. A database that came back without its
policies is a tenant-isolation incident wearing a recovery costume.

## Audit vocabulary status

**Complete.** `AuditAction` went from 37 to 50 members; all 13 security verbs
added, all 37 pre-existing verbs intact, asserted individually so a future
deletion is caught rather than absorbed.

Safe without a migration because `nf_audit_events.action` is `sa.String(64)`
with no `CHECK` constraint — worth confirming rather than assuming, since
migration 0018 does add enumerated CHECKs to `nf_operator_actions`. Longest new
verb is 34 characters.

## Audit persistence status

**Not wired.** Vocabulary is step 1 of doc 391's six-step plan. Steps 2–6 remain.

`cross_org_access_attempt` is now **refused at the write path**, not merely
documented as problematic:

```python
if action in UNPERSISTABLE_AUDIT_ACTIONS:
    raise ValueError(...)
```

It raises rather than dropping silently. A security event that vanishes is worse
than a request that fails, because nobody finds out. The reason is structural:
the event concerns two organizations and `organization_id` is `NOT NULL` and is
the RLS scoping column. Writing the actor org hides the event from the tenant
that was attacked; writing the target org attributes the attack to the victim.
Migration 0028 is planned in doc 401 and deliberately not written here — the
policy widening it requires needs to be proved against a real instance, not
reasoned about.

## Production storage live

**NO.** Unchanged. The five preconditions in
`postgres_membership_directory_service` are: approval token (held), DB config
(absent), migrations at head (would hold), RLS proof (passed in a throwaway
environment), backup/restore posture (**now gated, not satisfied**).

Gate 65 turned the fifth from undefined into measurable. It did not satisfy it.

## Owner-blocked

- A managed PostgreSQL 16+ instance and its `DATABASE_URL`, out-of-band
- A provider decision on PITR support, and enabling it
- Configuring automated backups at a frequency that meets the 60-minute RPO
- Running the first restore drill so an artifact exists
- Approval for migration 0028
- A retention decision for security audit events
- Real `OIDC_*` credentials (Gate 69), pen test, Slack webhook + redaction

## Engineering-blocked

- Migration 0028 and its RLS policy widening, with the new
  "actor org cannot read target-only events" check
- The victim-visibility privacy decision in doc 401 (product, not engineering)
- A security-audit repository with targeted-org scoping
- A sink interface so services stay pure (doc 391 step 4 — safe now)
- Invite/approval (67), capability enforcement (71–72), discovery (76–85)

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

What genuinely changed: recovery objectives exist and are numbers rather than
intentions; the recovery story can no longer be satisfied by a non-empty string;
and the audit trail has the vocabulary to describe a security incident, plus an
enforced refusal to describe one incorrectly.
