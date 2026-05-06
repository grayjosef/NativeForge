# Demo isolation and fake data (NF-001)

NativeForge must never mix **demo** (synthetic) data with **real** customer data. NF-001 establishes model-agnostic helpers and HTTP smoke routes **before** tribal profiles, grants, NOFO extraction, or production `nf_*` tables.

Full layered enforcement is described in [`execution/03-demo-isolation-spec.md`](../execution/03-demo-isolation-spec.md). This document summarizes what exists **today** in code.

## Configuration

| Variable | Purpose |
|----------|---------|
| `NF_DEMO_ORG_IDS` | Comma-separated org UUIDs for **NF-001 smoke routes only** (`/v1/isolation/*`). **Not** authoritative for new `nf_*` product APIs — see [`nativeforge-db-context-rules.md`](nativeforge-db-context-rules.md). |
| `NF_DEV_ORG_HEADERS` | When `true` (default in local dev), the backend accepts `X-NF-Org-Id` to build dev org context. When `false`, isolation routes that depend on this return **503** — simulating production without dev headers. |

See `.env.example`.

## Helpers (`nativeforge.lib.demo_isolation`)

- **Parse / classify:** `parse_demo_org_ids`, `is_demo_org`, `org_type_for`
- **Read path:** `row_matches_reader_org_type`, `can_read_record` — demo orgs must only see demo-flagged rows for their org; real orgs only non-demo rows for their org
- **Write path:** `validate_record_write` — `is_demo` on a row must match whether the org is in the demo allowlist
- **HTTP-shaped checks:** `assert_demo_route_org`, `assert_real_route_org` (raise `DemoIsolationError`; map to 403 in routes)
- **Seeds:** `require_explicit_demo_seed_context` — fake/demo seeds must pass `explicit_demo_context=True` when tagging demo content

## Dev HTTP routes (`/v1/isolation/*`)

Smoke endpoints prove Layer 3 separation using **only** `X-NF-Org-Id` and the demo allowlist (no second header to spoof org type). This path is **legacy/smoke-test** isolation.

## Sprint 0+ product routes (`nf_*`)

DB-backed routes (e.g. under `/v1/nf/...`) resolve **`organizations.org_type`** from the database. **`organizations.org_type` is authoritative** for real vs demo on product surfaces; **`NF_DEMO_ORG_IDS` must not** drive new `nf_*` features.

Rules for dependencies, RLS, and repositories: **[`nativeforge-db-context-rules.md`](nativeforge-db-context-rules.md)**.

Production must replace dev headers with authenticated identity; **`org_type` remains DB-backed**.

## Implemented in Sprint 0 (see codebase)

- `organizations`, `nf_review_artifacts`, `nf_audit_events`; SQLite alignment triggers; Postgres RLS + GUC helper (`apply_org_rls_gucs`).
- Repository-scoped queries and `scripts/check_nf_sql_grep.py`.

Remaining gaps vs `03-demo-isolation-spec.md` are tracked in architecture review (e.g. optional Hypothesis fuzz parity).

## Validation

**Preferred full stack + migrations listing (HITP-aligned):**

```bash
bash scripts/nativeforge_full_validation.sh
```

Backend-only quick checks:

```bash
ruff check src tests && ruff format --check src tests
pytest -q
python scripts/check_nf_sql_grep.py
```

NF-001-focused subset:

```bash
bash scripts/validate_demo_isolation.sh
```
