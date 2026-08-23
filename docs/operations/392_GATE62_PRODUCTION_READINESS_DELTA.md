# 392 — Gate 62: Production readiness delta

Written retroactively in Gate 64. Gate 62 was interrupted before it could
produce this, so this records what that gate actually moved — no more.

## What Gate 62 proved

For the first time in the campaign, RLS was executed rather than asserted.

| Claim | Before Gate 62 | After Gate 62 |
| --- | --- | --- |
| RLS policies exist in a migration | yes (0002, since Sprint 0) | yes |
| RLS policies have ever executed | **no** | **yes** |
| Cross-org read denied under a real non-owner role | no | **yes, 0 rows** |
| Unscoped read fails closed | no | **yes, 0 rows** |
| Membership cross-org read denied | no | **yes, 0 rows** |
| Membership cross-org write refused by `WITH CHECK` | no | **yes** |
| Migrations 0023–0027 applied against real Postgres | no | **yes** |

Environment: rootless PostgreSQL 16.2 via `pgserver` in a throwaway `/tmp`
venv. No sudo, no Docker daemon, project venv and `uv.lock` untouched. Full
output in doc 389.

One result was recorded deliberately rather than hidden: **the table owner sees
both organizations.** That is correct PostgreSQL behaviour, and recording it is
what makes the non-owner requirement legible as load-bearing rather than
decorative. An RLS proof run as the owner proves nothing, and the harness now
refuses to pretend otherwise.

## What Gate 62 did not move

| Claim | Status |
| --- | --- |
| Production storage live | **NO** — the proof ran against a throwaway `/tmp` instance |
| Customer persistence | **NO** — nothing survives that instance |
| Membership persistence | **NO** — no adapter existed to read the tables |
| Audit persistence | **NO** — 13 security events remain `persisted: false` |
| Backup / PITR | **NO** — not configured |
| Restore drill | **NO** — never run |
| Customer login live | **NO** — unrelated gate |
| Controlled customer pilot | **NO_GO** |

## The gap Gate 62 left

The proof was real but not repeatable. `verify_nativeforge_rls_isolation.sh`
targets an admin URL passed by hand, which is right for a one-off proof and
wrong as a control: nothing in the repo could re-run it against a managed
instance, and the schema could drift away from the proof without anything
noticing.

Gate 62 also stopped before the membership adapter, so the tables migration
0024 created had no reader. The schema existed; nothing could use it.

## What Gate 64 adds on top

- `scripts/verify_nativeforge_postgres_rls.sh` — the proof as a repeatable
  artifact, with `--dry-run` runnable by a reviewer holding no credentials.
- `PostgresMembershipDirectory` — a reader for those tables that fails closed
  without a database.
- `tests/test_gate62_storage_membership_rls_path.py` — coverage for both.
- Doc 391 — the audit wiring plan, including the finding that
  `cross_org_access_attempt` **cannot be correctly stored in the current
  schema** because `organization_id` is `NOT NULL`.

## Expected check names

The harness emits machine-readable lines. Reference list, so a reviewer can
tell a missing check from a passing one:

```text
database_url_present
database_url_redacted
postgres_dialect
app_role_not_superuser
app_role_not_table_owner
rls_enabled
rls_forced
same_org_read_allowed
cross_org_read_blocked
unscoped_read_blocked
membership_cross_org_read_blocked
membership_cross_org_write_blocked
result
```

## Net delta

Gate 62 moved storage/RLS from *designed* to *proven in a throwaway
environment*. It moved nothing else, and it did not bring a controlled customer
pilot any closer to GO.

```text
Controlled customer pilot: NO_GO
Production rollout:        NO_GO
Customer login live:       NO
Production storage live:   NO
Customer persistence:      NO
Pen-test passed:           NO
```
