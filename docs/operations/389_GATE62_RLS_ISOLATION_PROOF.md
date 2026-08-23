# 389 — Gate 62: Postgres RLS isolation proof

Script: `scripts/verify_nativeforge_rls_isolation.sh`
Approved by: `MAYHEM_APPROVES_NATIVEFORGE_PROD_STORAGE_GATE61`

**This is the item that had never been verified in this entire campaign.** Doc
383 found that migration `0002` writes RLS policies but had never executed,
because no Postgres had ever been connected. It has now executed, and the
policies work.

## How the dev proof was stood up

No root, no Docker daemon, no `sudo` — so `apt install postgresql` and
`docker run postgres` were both unavailable. Instead:

```bash
python3 -m venv /tmp/pgenv
/tmp/pgenv/bin/pip install pgserver          # bundles Postgres binaries, rootless
/tmp/pgenv/bin/python -c "import pgserver; pgserver.get_server('/tmp/nfpgdata', cleanup_mode=None)"
```

Result: **PostgreSQL 16.2** on a unix socket, matching the approved major
version. `pgserver` is installed into a **throwaway venv**, never the project
venv, so `uv.lock` and `pyproject.toml` are untouched — verified clean.

This satisfies the approval's "staging/dev proof first" condition. It is **not**
a production provisioning claim, and the script prints
`note=this_is_a_dev_proof_not_a_production_provisioning_claim`.

## Result — 15 checks, RESULT=PASS

```text
check=postgres_version_supported            PASS version=16.2
check=rls_policies_present                  PASS count=20
check=rls_forced_on_tables                  PASS count=20
check=fixture_rows_seeded                   PASS rows=2
check=owner_visibility_recorded             PASS owner_sees=2
check=app_role_not_superuser                PASS
check=app_role_owns_no_tables               PASS
check=app_role_sees_own_org                 PASS rows=1
check=cross_org_read_returns_zero_rows      PASS rows=0
check=app_role_without_guc_sees_nothing     PASS rows=0
check=app_role_scope_follows_guc            PASS rows=1
check=demo_real_plane_mismatch_denies       PASS rows=0
check=membership_table_scoped_to_own_org    PASS rows=1
check=membership_cross_org_read_denied      PASS rows=0
check=membership_cross_org_write_denied     PASS refused by RLS WITH CHECK
RESULT=PASS
```

## What each check establishes

**The isolation guarantee.** A non-superuser, non-owning app role with
`app.current_org_id` set to org A sees exactly its own row and **zero** rows for
org B. Cross-org access returns an empty result, not an error — the safe failure
mode, because an error reveals that the other org's row exists.

**Fails closed with no context.** With no GUC set at all, the app role sees
nothing. A request that forgets to set the org context gets an empty result
rather than the whole table. That is the property that makes RLS a genuine
backstop for an application-layer bug.

**Scope follows context, it does not widen.** Switching the GUC to org B shows
org B's single row, not both.

**The demo/real plane is enforced in the same predicate.** Setting
`app.current_org_is_demo=true` against a real org denies. Plane isolation is not
a separate mechanism that could drift.

**Membership is protected too, for reads and writes.** The new
`nf_org_memberships` table (migration `0024`, policy `0027`) is scoped like
everything else. Critically, an app role scoped to org A **cannot insert** a
membership row for org B — `WITH CHECK` refuses it. Since membership is the
record that grants a role, a write leak there would be an authority escalation,
not just a data leak.

## The owner bypass — recorded on purpose

`owner_visibility_recorded PASS owner_sees=2` is not a pass in the sense of
"good". It records that the **table owner sees both organizations' rows**.

That is why the approval's requirement that the app DB role be non-owner and
non-superuser is load-bearing rather than hygiene. If the application connects as
the owner or a superuser, every policy proven above is silently bypassed and the
output of this script would look identical for the wrong reason. Two checks guard
it explicitly:

```text
check=app_role_not_superuser    PASS
check=app_role_owns_no_tables   PASS
```

The script prints
`note=owner_and_superuser_roles_bypass_rls_app_role_must_be_neither`.

## How to re-run

```bash
export DATABASE_URL_ADMIN='postgresql://postgres@/nf_pg3?host=/tmp/nfpgdata'
./scripts/verify_nativeforge_rls_isolation.sh
```

Against a real managed instance, point `DATABASE_URL_ADMIN` at it after applying
migrations. The script creates a throwaway `nf_rls_app` role, seeds two probe
organizations, and deletes its own fixture rows afterwards. It never prints a
password.

## What this does NOT establish

- **Not a production claim.** No production instance exists;
  `production_storage_live` stays false.
- **Not a backup/restore proof.** That is a separate approval item and has not
  been done.
- **Not a pen test.** Independent review has not covered this.
- **Not proof the application sets the GUC correctly.** RLS is the backstop;
  `db/rls.py` calls `set_config` per transaction, and wiring that into every
  request path is still ahead. RLS working means an application bug is contained,
  not that there is no bug.
