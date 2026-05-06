# NativeForge HITP Commit Gate

No automatic commits. Every commit requires explicit human approval.

Valid approval phrases:
- approve commit
- commit it
- go commit

Required block before every commit:

```text
================ HITP COMMIT APPROVAL REQUIRED ================
Proposed commit message:
Branch:
Files changed:
Diff stat:
Backend validation run:
Backend validation result:
Frontend validation run:
Frontend validation result:
Migration status:
Test coverage touched:
Known risks:
What was intentionally not tested:
Why this is safe to commit:

Awaiting explicit human approval before running git commit.
Valid approvals: "approve commit", "commit it", or "go commit".
==============================================================
```

Frontend validation is mandatory when `frontend/package.json` exists. No commit may be made based only on backend tests.

Before `npm run typecheck` or `npm run build`, run **`npm ci`** in `frontend/` (or equivalent install) so local binaries such as `vite` and `tsc` exist under `node_modules/.bin`. CI does this automatically; local manual runs often fail with `vite: not found` / `tsc: not found` if `npm ci` was skipped.

## Required full validation command

The canonical local validation path before requesting commit approval is:

```bash
bash scripts/nativeforge_full_validation.sh
```

That script runs backend checks (ruff, `check_nf_sql_grep`, pytest), **`npm ci`** and frontend **typecheck** + **build**, lists Alembic migration files, runs **`alembic history`**, and **skips** `npm run lint` / `npm test` when those scripts are missing from `frontend/package.json`.

## `nf_*` product routes and org context

All future **`nf_*` product APIs** must use **DB-backed** organization context (`organizations.org_type` authoritative). **`NF_DEMO_ORG_IDS`** is **legacy/smoke-test only** for `/v1/isolation/*`. DB-backed routes must use the dependency path that applies **`apply_org_rls_gucs()`** on Postgres. Reads/writes go through **repositories/services** — see **[`nativeforge-db-context-rules.md`](nativeforge-db-context-rules.md)**.
