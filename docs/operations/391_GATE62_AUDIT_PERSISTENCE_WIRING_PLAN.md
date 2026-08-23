# 391 — Gate 62: Audit persistence wiring plan

Security-critical audit events are currently **modeled, not stored**. Six
service modules emit event dictionaries carrying `"persisted": False`, and that
flag is honest: nothing writes them anywhere. This plan says what it would take
to make it true, and what must not be claimed until it is.

## Current state

### The table exists and works

`nf_audit_events` was created by migration 0002 and carries:

```text
id, organization_id, is_demo, review_artifact_id, tribal_profile_id,
extraction_run_id, action, payload (JSON), actor_id, created_at
```

It is org-scoped, `is_demo`-scoped, and covered by the RLS policy migration 0002
installed (and which Gate 62 proved actually executes).

### The repository exists and works

`src/nativeforge/repositories/audit_events.py` provides
`append_org_audit_event(...)` and `list_audit_events_for_org(...)`, with scoping
in `repositories/scoping.py`. It is already used in anger by
`repositories/pursuits.py` and `repositories/evidence_pack.py`.

**So audit persistence is not missing infrastructure. It is missing wiring.**

### What is already persisted

Workflow events, through the existing repository: artifact lifecycle, profile
changes, pursuit and task changes, form packages, discovery runs, operator
actions. Roughly 38 verbs in `AuditAction`.

### What is not persisted

Every event in the Gate 64D list. Checked against `domain/enums.py`: **none of
the thirteen exists as an `AuditAction` member.**

| Event | Emitted by | In `AuditAction`? | Persisted? |
| --- | --- | --- | --- |
| `tenant_access_denied` | `membership_directory_service`, `postgres_membership_directory_service`, `api_enforcement_service` | no | no |
| `cross_org_access_attempt` | `postgres_membership_directory_service`, tenant guard | no | no |
| `membership_created` | not yet emitted (Gate 67) | no | no |
| `membership_revoked` | not yet emitted (Gate 67) | no | no |
| `membership_expired` | derived in resolution, not emitted as an event | no | no |
| `role_changed` | not yet emitted (Gate 67) | no | no |
| `authority_proof_submitted` | `authority_proof_workflow_service` | no | no |
| `authority_proof_verified` | `authority_proof_workflow_service` | no | no |
| `authority_sensitive_action_blocked` | `authority_proof_workflow_service` | no | no |
| `source_candidate_promoted` | `continuous_source_discovery_service` | no | no |
| `source_candidate_blocked` | `continuous_source_discovery_service` | no | no |
| `feedback_alert_attempted` | modeled only | no | no |
| `feedback_alert_failed` | modeled only | no | no |

## Schema gaps

The existing table was designed for *workflow* audit. Security audit needs
fields it does not have:

1. **No actor identity beyond `actor_id UUID`.** A denial usually has no
   `actor_id` — the whole point is that the caller could not be resolved to one.
   The `(issuer, subject)` pair that *was* presented is the useful record, and
   there is nowhere to put it except `payload`.
2. **No outcome column.** `action` conflates verb and result. `allowed` /
   `denied` should be queryable without JSON extraction, because "show me every
   denial in the last hour" is the first question anyone asks.
3. **No request correlation id.** A single denied request can produce several
   events; without a correlation id they cannot be stitched back together.
4. **`organization_id` is `NOT NULL`.** A cross-org attempt has *two* relevant
   organizations, and a denial where no organization could be resolved has
   none. Writing the attacker's claimed org into the scoped column would make
   the row invisible to the org that was actually targeted — exactly backwards.
   This is the sharpest gap: it means `cross_org_access_attempt` **cannot be
   correctly stored in the current schema.**
5. **No severity.** Routine denials and isolation-boundary violations would be
   indistinguishable in the same stream.

Gap 4 requires a migration. The others can be carried in `payload` initially,
with columns promoted later once query patterns are known.

## Retention

Not yet decided, and it must be before anything is written.

- Security audit typically wants 12–24 months; workflow audit does not need it.
- The table has no partitioning and no retention job. An unbounded denial
  stream is a cheap denial-of-service against our own storage bill.
- Recommendation: separate retention class for security events, partition by
  month, and a documented purge job — decided before wiring, not after.

## Personal data

Denial events are the most personal-data-dense records in the product, and they
are about people who may not be customers.

- `subject` and `issuer` are pseudonymous identifiers — storable, but they are
  personal data under GDPR-style regimes.
- **Email must not be written into audit payloads.** It is directly
  identifying, is not needed to investigate a denial, and would make the audit
  table a shadow user directory.
- IP addresses and user agents: not currently collected, and should not be
  added without a specific decision.
- A denied party has no account, so there is no self-service deletion path.
  Retention is therefore the only control, which is another reason to decide it
  first.
- Cross-org attempts record that org A's credentials touched org B. That row is
  evidence about *both* tenants and must not be exposed through either org's
  normal audit read path.

## Wiring plan

Ordered, with each step gated on the previous.

**Step 1 — vocabulary.** Add the thirteen verbs to `AuditAction`. Pure
enum addition, no migration, no behaviour change. Safe now.

**Step 2 — schema.** Migration `0028`: nullable `target_organization_id`,
`outcome`, `severity`, `correlation_id`, and a `subject_hint` sized for an OIDC
subject. Nullable throughout so existing rows stay valid. Requires owner
approval, same as 0023–0027.

**Step 3 — a security-audit repository.** Separate from
`repositories/audit_events.py`, because the scoping rule differs: a
cross-org attempt must be visible to the *targeted* org, not the claiming one.
Reusing the existing repository would silently apply the wrong scope.

**Step 4 — a sink interface.** Services keep returning modeled events; a sink
persists them. Services must not import a session — they are pure functions and
that property is worth keeping. The sink is injected at the API boundary.

**Step 5 — flip `persisted`.** The flag becomes computed from whether a sink
was configured and the write succeeded, rather than a hardcoded `False`. A
failed audit write must fail the request, not be swallowed: an unlogged denial
is worse than a refused request.

**Step 6 — retention job.** Before the first production write, not after.

## When persistence can be claimed

`audit_persistence_live=true` requires **all** of:

1. A provisioned managed PostgreSQL instance with `DATABASE_URL` configured.
2. Migrations at the expected head, including step 2's `0028`.
3. `verify_nativeforge_postgres_rls.sh --verify-rls` returning `RESULT=PASS`
   against that instance.
4. The sink wired and a write proved end-to-end, with a captured artifact.
5. A documented retention policy and a working purge job.
6. Confirmation that no email or other directly-identifying field is written.

None of the six hold today. **Audit persistence is not live, and nothing in
Gate 64 wires it live.** Steps 1 and 4 are safe to do without a database and are
the natural start of Gate 68; steps 2, 3, 5 and 6 are owner-blocked on
provisioning.
