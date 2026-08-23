# 384 — Gate 61B: Production storage approval packet

For owner decision. **No production migration has been created and none will be
until this is approved.** See `387` for the short decision checklist.

## 1. Recommended backend

**Managed PostgreSQL 16+.**

Not a preference — the repo already commits to it:

- `psycopg[binary]>=3.2` is a declared runtime dependency
- `db/rls.py` targets Postgres row-level security GUCs
- migration `0002` already writes `ENABLE/FORCE ROW LEVEL SECURITY` and
  `CREATE POLICY`, guarded by `dialect.name == "postgresql"`

Choosing anything else would abandon isolation machinery that is already
written. Managed rather than self-hosted, because backup, patching and
point-in-time recovery are exactly the operational burden a one-person team
should not carry for tribal customer data.

**Minimum:** PG 16, encryption at rest, TLS required, automated daily backup with
≥7-day point-in-time recovery, private networking or IP allowlist.

## 2. What it holds first

In dependency order — each row scoped to an organization:

| Entity | Why first |
| --- | --- |
| `organizations` | exists (2 columns); needs name, seat cap, timestamps |
| `identities` | verified OIDC subject → stable internal id. The Gate 60 output has nowhere to land. |
| `org_memberships` | the actual blocker. Subject × org × role × state. |
| `roles` | or an enum column; role must come from here, never a token claim |
| `audit_events` | table exists; add tenant-denial and membership events |
| `authority_proof_records` | Gate 52 lifecycle needs somewhere to live |

## 3. What must NOT be stored yet

Explicitly out of scope for the first migration:

- **Customer-uploaded documents / binary evidence.** Needs object storage, a
  retention policy and a deletion path first.
- **Proposal narrative or draft prose.** `generated_prose_produced=false` is a
  standing claim; storing prose would make it false.
- **Tribal facts, resolutions, budgets, award history.** No fabrication risk is
  worth taking here; these need a provenance model.
- **SAM/UEI/AOR status.** Recording a *claim* is fine; recording it as verified
  status is not, until a live registry check exists.
- **Anything from the SC demo pack.** The demo is a curated offline bridge and
  must stay isolated from a real store.

## 4. Environment variables required

Supplied out-of-band, never committed:

| Var | Purpose | Notes |
| --- | --- | --- |
| `DATABASE_URL` | connection string | already read by `lib/settings.py`; defaults to in-memory SQLite |
| `NF_DB_SSL_MODE` | TLS enforcement | recommend `require` or stricter |
| `NF_DB_APP_USER` | least-privilege app role | must NOT be the owner/superuser, or RLS is bypassed |
| `NF_DB_MIGRATION_USER` | migration-only role | separate from the app role |

The app role **must not** be a superuser or table owner: Postgres RLS is
bypassed by both, which would silently void every policy in migration 0002.

## 5. Migrations required

Starting from head `0022`:

```text
0023  identities                    (subject, issuer, email, email_verified, timestamps)
0024  org_memberships               (+ state, role, sources, invited_by, approved_by,
                                     revoked_at, expires_at; unique (identity, org))
0025  organizations enrichment      (name, seat_cap default 5, timestamps)
0026  authority_proof_records       (Gate 52 lifecycle)
0027  RLS policies for the new tables + audit event types
```

**None of these have been written.** Writing them before approval would produce
migrations validated only against in-memory SQLite, which proves nothing about
Postgres RLS behaviour — the single most important thing to get right.

## 6. Backup / restore minimum

1. Automated daily backup, ≥7-day retention.
2. Point-in-time recovery enabled.
3. **A restore actually performed** into a scratch instance, with the result
   recorded as an artifact. An untested backup is not a backup — and the repo
   already has a `test_sprint64`-era claim distinguishing "non-prod proof is not
   production restore".
4. A documented RTO/RPO, even if generous.

## 7. Access controls required

- Separate migration and application roles (§4).
- App role: `SELECT/INSERT/UPDATE` on its tables; no `DDL`, no `SUPERUSER`,
  not table owner.
- No shared human credential; break-glass access logged.
- Connection restricted to the app host by private network or allowlist.
- Secrets out-of-band only; never in the repo, never printed.

## 8. Tenant isolation strategy

**Defence in depth, three layers — none of which replaces the others:**

1. **Application layer (live today).** Gate 58 enforces org scoping on all 205
   org-scoped handlers through one `tenant_guard`, with an anti-bypass test.
2. **Row-level security (written, never executed).** Migration `0002` policies
   plus `rls.py` GUCs. Must be **proven against real Postgres** before being
   relied on — see doc 383, correction 1.
3. **Query-level scoping** in repositories.

Required proof before the pilot: create two organizations, attempt a cross-org
read as the app role with the GUC set to org A, and demonstrate zero rows from
org B — with the app role confirmed as non-owner, non-superuser.

## 9. Audit trail required

`nf_audit_events` exists and is written by two discovery routes. Required
additions:

- tenant denial events from `tenant_guard` (currently modeled, `persisted:false`)
- membership lifecycle: invited / approved / suspended / revoked / expired
- role changes, with the escalation flag Gate 53 already computes
- authority proof transitions (Gate 52)
- append-only in practice: no `UPDATE`/`DELETE` grant for the app role
- retention decision, since audit rows about people are personal data

## 10. Exact approval needed

See `387` for the checklist and the approval token. In summary, the owner must
approve: provider and environment, initial schema scope, permission to write
migrations `0023`–`0027`, the backup/restore minimum, the tenant isolation
posture, whether the membership directory may go live after migration, and that
secrets will be supplied out-of-band.

Until that approval exists, `production_storage_live` stays `false`, the
membership directory stays the in-memory test adapter, and no migration beyond
`0022` is written.
