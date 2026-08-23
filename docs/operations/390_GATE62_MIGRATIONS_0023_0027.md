# 390 — Gate 62: Migrations 0023–0027

Approved by `MAYHEM_APPROVES_NATIVEFORGE_PROD_STORAGE_GATE61`, scope as specified
in doc 384 §5. Head moves `0022` → `0027`.

Verified from scratch on **both** dialects:

```text
PostgreSQL 16.2  -> head 0027, all 5 applied, RLS policies created
SQLite (file)    -> head 0027, all 3 new tables present
```

## What each migration adds

| Rev | Table / change | Notes |
| --- | --- | --- |
| `0023` | `nf_identities` | verified OIDC subject → internal id. Unique on `(issuer, subject)`, **not** email — an email can be reassigned, a subject cannot. `verification_source` constrained to `oidc_token_signature`. |
| `0024` | `nf_org_memberships` | the trusted membership record. FKs to `organizations` and `nf_identities`, unique `(organization_id, identity_id)`. |
| `0025` | `organizations` enrichment | `display_name`, `seat_cap` default **5** (Gate 51), `created_at`. |
| `0026` | `nf_authority_proof_records` | Gate 52 lifecycle, 8 states. |
| `0027` | RLS policies | `nf_org_memberships` + `nf_authority_proof_records`, Postgres-only, same `USING`/`WITH CHECK` predicate as `0002`. |

## Constraints that encode the Gate 51–61 rules in the schema

The point of putting these in the database rather than only in application code
is that a future writer cannot bypass them by forgetting a service call:

- **`ck_nf_org_memberships_source_trusted`** — `membership_source` is restricted
  to `verified_directory`, `operator_approved`, `org_owner_approved`.
  `client_header`, `dev_header`, `cloudflare_access` and `email_domain_only` are
  **not storable at all**. An untrusted membership cannot exist as a row.
- **`ck_nf_org_memberships_role_source`** — `role_source` may only be
  `membership_record`. An IdP group claim cannot be persisted as a role source.
- **`ck_nf_org_memberships_approver_required`** — a membership from an
  approval-requiring source must name its `approved_by`. Approval by nobody is
  not approval.
- **`ck_nf_authority_proof_verifier_required`** — a `verified` authority proof
  must name its `verified_by`, matching the Gate 52 derivation.
- **`ck_organizations_seat_cap_positive`** — `seat_cap >= 1`.

`nf_identities` is deliberately **not** org-scoped and has no RLS policy: an
identity exists independently of any organization, and scoping it would make
membership lookup impossible for a user who belongs to more than one org.

## Two dialect bugs the dev-proof requirement caught

Both would have shipped silently if migrations had only ever been written and
reviewed rather than run. This is the concrete value of "staging/dev proof
first".

### 1. `server_default=sa.text("now()")` — 98 test failures

I used a raw SQL literal. `now()` is a PostgreSQL function; SQLite has no such
function, so every insert into an affected table failed with
`sqlite3.OperationalError: unknown function: now()`. Since the whole test suite
migrates SQLite, this broke **98 tests**.

Fixed by using `sa.func.now()`, which SQLAlchemy renders per-dialect
(`CURRENT_TIMESTAMP` on SQLite, `now()` on Postgres) — and which is the
convention migration `0002` already used. I should have matched the existing
convention rather than reaching for `sa.text`. 81 of the 98 failures were the
same root cause; the fix took the selection from 98 failed to 17.

### 2. The seat-cap CHECK constraint is PostgreSQL-only

Two obvious approaches both fail on SQLite:

1. `op.create_check_constraint` → `NotImplementedError`, SQLite cannot ALTER a
   constraint into an existing table.
2. `op.batch_alter_table` (copy-and-move, the documented Alembic workaround) →
   fails with `no such table: main.organizations`, because migration `0002`
   created triggers (`trg_nf_review_artifacts_demo_align_ins` and siblings) that
   reference `organizations`. Renaming the table out from under them breaks them.

So the constraint is added **only on PostgreSQL**, the approved production
backend. On SQLite the seat cap is enforced in application code
(`org_tenant_seat_model_service`, Gate 51).

**This asymmetry is real and worth stating plainly:** the local test path does
not enforce the seat cap at the database level. It is documented in a comment in
the migration itself rather than left for someone to discover.

## What these migrations do NOT do

- **No production instance exists.** They have been applied to a local dev
  Postgres and to SQLite. `production_storage_live` remains `false`.
- **Nothing is seeded.** No identity, membership or authority row is created by
  a migration. Memberships must come from a human approval path, which does not
  exist yet (doc 386, unblock step 5).
- **No excluded data.** Nothing from doc 384 §3 — no documents, prose, tribal
  facts, or SAM/UEI status.
- **The models are not updated.** `db/models.py` has no ORM classes for the new
  tables yet; the schema exists ahead of the mapped models, deliberately, so the
  membership directory can be reviewed before it is wired.

## Re-running the proof

```bash
# SQLite
rm -f /tmp/nf_check.db
DATABASE_URL="sqlite+pysqlite:////tmp/nf_check.db" alembic upgrade head

# Postgres (see doc 389 for the rootless dev server)
DATABASE_URL="postgresql+psycopg://postgres@/nf_pg3?host=/tmp/nfpgdata" alembic upgrade head
./scripts/verify_nativeforge_rls_isolation.sh
```
