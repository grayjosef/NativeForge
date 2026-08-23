# 398 — Gate 64: Production readiness delta

Gate 64 completed the artifacts Gate 62 was interrupted before producing. It
turned a one-off proof into a repeatable one and gave the membership tables a
reader. It provisioned nothing, so it moved no production claim.

## Gate 62 completion

| Artifact | Before | After |
| --- | --- | --- |
| `scripts/verify_nativeforge_postgres_rls.sh` | absent | created, 4 modes |
| `postgres_membership_directory_service.py` | absent | created |
| `tests/test_gate62_storage_membership_rls_path.py` | absent | created |
| doc 391 — audit persistence wiring plan | absent | created |
| doc 392 — Gate 62 readiness delta | absent | created |

Gate 62's residual list is now empty.

## RLS proof harness

Four modes, each honest about what it can and cannot show without credentials:

| Mode | Without `DATABASE_URL` |
| --- | --- |
| `--dry-run` | `RESULT=SKIP` — self-tests pass, nothing to prove against |
| `--check-config` | `RESULT=SKIP` |
| `--verify-rls` | `RESULT=SKIP` |
| `--strict` | `RESULT=FAIL` |

Credential handling: `DATABASE_URL` is never echoed. Only a redacted form is
printed, and the redaction is asserted before anything derived from the URL
reaches stdout. `--dry-run` self-tests the redaction against a synthetic
password-bearing URL and confirms the password does not appear in output.

Two defects were found and fixed while building it, both of which would have
produced a misleading pass:

1. **Password detection was fooled by the scheme's own colon.** The naive test
   `*:*@*` matches `postgresql://user@host` — every URL has a colon in its
   scheme. A legitimately passwordless URL would have been reported as a
   redaction failure. Replaced with authority-section parsing.
2. **Zero-row isolation checks could pass vacuously.** "Cross-org read returned
   0 rows" proves nothing when the other organization has no rows. The harness
   now seeds a fixture over a separate admin connection (`NF_RLS_SEED_URL`),
   asserts a positive control (org A sees exactly its own row), and marks the
   isolation results `VACUOUS` when no fixture was seeded.

The second one matters: without it, the harness would have reported a clean
pass against an empty database.

## Rootless Postgres proof — executed

Run against PostgreSQL 16.2 via `pgserver`, rootless, in `/tmp`, no sudo, no
Docker. Project venv and `uv.lock` untouched. Migrations applied to head `0027`.
App role `nf_app`: `NOSUPERUSER`, owns 0 tables.

```text
check=postgres_dialect                     status=PASS server_version=16.2
check=app_role_not_superuser               status=PASS current_user=nf_app
check=app_role_not_table_owner             status=PASS owns=0
check=rls_enabled                          status=PASS tables=20
check=rls_forced                           status=PASS tables=20
check=cross_org_fixture_seeded             status=PASS rows=2 (one per organization)
check=same_org_read_allowed                status=PASS rows=1 (own row visible)
check=cross_org_read_blocked               status=PASS rows=0
check=unscoped_read_blocked                status=PASS rows=0
check=membership_cross_org_read_blocked    status=PASS rows=0
check=membership_cross_org_write_blocked   status=PASS refused by WITH CHECK
RESULT=PASS
```

`--check-config` returns `SKIP` on this environment because the connection is a
Unix-domain socket, where TLS is not applicable. A TCP connection without TLS
still fails.

**This is a throwaway instance.** It proves the policies work. It proves nothing
about durability, backups, or a managed provider.

## Postgres membership adapter

`PostgresMembershipDirectory` reads `nf_identities` and `nf_org_memberships`
through an injected row source. Without one it denies — there is no in-memory
fallback that could be mistaken for persistence.

`production_storage_live` requires **all five** of:

```text
approval_token_present
database_url_present
migrations_at_expected_head
rls_proof_passed
backup_restore_posture_documented
```

Each is individually load-bearing and tested as such. `customer_persistence_claimed`
requires live storage **and** a proof artifact on top.

Denials: missing identity, missing membership, non-active state, revocation
timestamp overriding an `active` column, expiry against a caller-supplied clock,
untrusted membership source, untrusted role source, internal role, unrecognised
role, `unknown` role, and organization mismatch (audited as
`cross_org_access_attempt`). Every denial emits an audit event.

Identity is keyed on `(issuer, subject)`, never email.

**Not wired to live routes.** There is no configured database, so wiring it
would add a code path that can only fail.

## Audit persistence

Still `persisted: false`. The table and repository exist and work — this is
missing wiring, not missing infrastructure. Doc 391 has the plan.

The sharpest finding: `nf_audit_events.organization_id` is `NOT NULL`, so
`cross_org_access_attempt` **cannot be correctly stored in the current schema**.
Writing the attacker's claimed org into the scoped column would hide the event
from the org that was actually targeted. That needs migration `0028`.

## Status

```text
Controlled customer pilot: NO_GO
Production rollout:        NO_GO
Customer login live:       NO
Production storage live:   NO
Customer persistence:      NO
Pen-test passed:           NO
Slack live alert:          NOT PROVEN
```

### Owner-blocked

- A managed PostgreSQL 16+ instance and its `DATABASE_URL`, supplied out-of-band
- Backup / PITR configuration
- A restore drill with a recorded artifact
- Real `OIDC_*` credentials and a provider token for Gate 69
- Independent pen test
- Live Slack webhook and a redaction decision

### Engineering-blocked

- Migration `0028` for security-audit columns (doc 391 step 2)
- The thirteen `AuditAction` verbs (doc 391 step 1 — safe to do now)
- A security-audit repository with targeted-org scoping (step 3)
- Invite / approval workflow (Gate 67)
- Capability enforcement on live read then write routes (Gates 71–72)
- Source registry and the discovery baseline (Gates 76–85)

## Why the pilot stays NO_GO

A customer needs to log in, and login is not live. Their data needs to persist,
and no store is provisioned. Their denials need to be auditable, and audit is
not wired. Any one of those alone is disqualifying.

What changed is narrower and worth stating plainly: the isolation boundary is
now provable on demand rather than remembered from a terminal session, and the
code that will read membership in production exists and fails closed.
