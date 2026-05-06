# NativeForge DB-backed org context rules

Rules for **product** APIs that touch `nf_*` data and for Postgres Row-Level Security (RLS). Sprint 0 introduced DB-backed org resolution; Sprint 1 and beyond **must** follow these consistently.

## Authoritative demo vs real separation

- **`organizations.org_type`** (`real` \| `demo`) is the **authoritative** classification for **all new product routes** that serve `nf_*` rows.
- Rows on `nf_*` tables carry **`is_demo`**, aligned with the owning organization via DB triggers (SQLite) or equivalent enforcement on Postgres.

## Legacy allowlist (NF-001 only)

- **`NF_DEMO_ORG_IDS`** powers **`/v1/isolation/*`** smoke endpoints and **`nativeforge.lib.demo_isolation`** helpers that **do not** load `organizations` from the database.
- Treat this as **legacy / smoke-test isolation only**. **Do not** use `NF_DEMO_ORG_IDS` as the source of truth when implementing **new** `nf_*` product features or routes.

## Required dependency path for `nf_*` product APIs

- All future **`nf_*` product APIs** must use **DB-backed organization context**: resolve the current org from the **`organizations`** table (via the established FastAPI dependencies), not from the demo allowlist alone.
- All DB-backed routes that query `nf_*` tables under Postgres must run through the dependency chain that calls **`apply_org_rls_gucs()`** so session GUCs (`app.current_org_id`, `app.current_org_is_demo`) match RLS policies. **Do not** add handlers that open a DB session and query `nf_*` without that path.

## Data access layers

- **Reads and writes** to `nf_*` data must go through **repositories** and **services**, not ad hoc SQL or ORM mutations in route functions. Route handlers orchestrate; they do not bypass the review gate or repository scoping.

## Related docs

- [`demo-isolation.md`](demo-isolation.md) — NF-001 vs Sprint 0 summary  
- [`research/execution/03-demo-isolation-spec.md`](../research/execution/03-demo-isolation-spec.md) — full layered spec  
- [`HITP_COMMIT_GATE.md`](HITP_COMMIT_GATE.md) — validation before commit  

## Full local validation

Before claiming a branch is merge-ready (see HITP), run:

```bash
bash scripts/nativeforge_full_validation.sh
```

That script runs backend checks, **`npm ci`** in `frontend/`, then **typecheck** and **build**, lists migration files, runs **`alembic history`**, and skips optional **lint** / **test** npm scripts when they are absent from `package.json`.
