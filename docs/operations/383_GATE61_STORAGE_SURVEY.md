# 383 — Gate 61A: Storage survey

Status: survey complete. **Two findings correct earlier statements of mine.**

## Storage systems found

Real storage infrastructure exists and is more complete than earlier gates
implied:

| Component | Location |
| --- | --- |
| SQLAlchemy declarative base | `src/nativeforge/db/base.py` |
| Models — **23 tables** | `src/nativeforge/db/models.py` |
| Session factory | `src/nativeforge/db/session.py` |
| **Postgres RLS session GUCs** | `src/nativeforge/db/rls.py` |
| Alembic — **20 migrations, head 0022** | `alembic/versions/` |
| Repositories — 15 modules | `src/nativeforge/repositories/` |

Tables include `organizations`, `nf_audit_events`, `nf_tribal_profiles`,
`nf_opportunity_sources`, `nf_grant_sparks`, `nf_grant_pursuits`,
`nf_form_packages`, `nf_discovery_*`, `nf_operator_actions`.

## Correction 1 — RLS is written, and inert

`src/nativeforge/db/rls.py` sets per-transaction GUCs `app.current_org_id` and
`app.current_org_is_demo`, and migration `0002_sprint0_demo_rls` runs
`ENABLE ROW LEVEL SECURITY` + `FORCE ROW LEVEL SECURITY` and creates
`{table}_org_demo_scope` policies.

**But all of it is Postgres-only and guarded by `dialect.name == "postgresql"`.**
Verified:

```text
DATABASE_URL          -> NOT SET (defaults to sqlite+pysqlite:///:memory:)
postgres process      -> none
listening on 5432     -> nothing
```

So the RLS code path has **never executed**. Earlier readiness docs listed
row-level security as unbuilt engineering work; it is more accurately *written
but unexercised*, which is a different and slightly more dangerous state —
untested isolation code can look like protection.

## Correction 2 — an audit table already exists

`nf_audit_events` is a real table with a repository
(`repositories/audit_events.py`) and is written to by two discovery routes. My
Gate 58/59 docs said audit persistence did not exist; the accurate statement is
that the **table and repository exist**, and Gate 58's tenant-denial events are
not wired to them. That is a smaller gap than previously described.

## Current dev/local storage status

- Default is **in-memory SQLite**, so nothing persists between processes.
- Local dev artifacts exist on disk: `nativeforge.local.db` (548 KB),
  `artifacts/local_dev_evidence*.sqlite3` — evidence stores from earlier gates,
  local-dev scope only.
- Migrations run cleanly against SQLite (visible in every pytest run,
  `0001` → `0022`).

## Production storage status

**None.** No production database is configured, provisioned or reachable. No
`DATABASE_URL` pointing at a managed instance, no connection secret, no
provisioning script. `psycopg[binary]` is a declared dependency, so Postgres is
the clear intended target, but nothing has been stood up.

## Org / user / membership schema

| Entity | Exists? |
| --- | --- |
| `organizations` | YES — but only two columns: `id`, `org_type` (`real`/`demo`) with a check constraint. No name, no seat cap, no metadata. |
| users / identities | **NO** |
| org_memberships | **NO** |
| roles | **NO** |
| seats / invites | **NO** |
| authority_proof_records | **NO** |

Confirmed by grepping every `__tablename__` for user/identity/member/role/seat/
invite/person — zero matches.

This is the concrete confirmation of doc 381 item 10: the membership directory
has **no schema whatsoever**. Gate 51 modelled memberships as contracts over
caller-supplied state; nothing persists them and nothing can.

## Exact blockers to production storage

1. **No provisioning decision.** No provider, region, tier, or environment has
   been chosen. Owner-blocked.
2. **No connection secret.** Would have to be supplied out-of-band.
3. **No membership/identity schema.** Engineering work, but pointless to migrate
   before (1) — a migration against in-memory SQLite proves nothing about
   production.
4. **RLS unexercised.** The policies exist but have never run. They must be
   proven against a real Postgres before being relied on for tenant isolation.
5. **No backup/restore procedure.** Nothing defined for a production instance.
6. **No pen test.** Independent review has not covered any of the above.

Items 1, 2, 5 and 6 are owner-blocked. Items 3 and 4 are engineering work
gated on item 1.

Proceed to the approval packet (`384`).
