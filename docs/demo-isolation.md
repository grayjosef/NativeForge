# Demo isolation and fake data (NF-001)

NativeForge must never mix **demo** (synthetic) data with **real** customer data. NF-001 establishes model-agnostic helpers and HTTP smoke routes **before** tribal profiles, grants, NOFO extraction, or production `nf_*` tables.

Full layered enforcement is described in [`execution/03-demo-isolation-spec.md`](../execution/03-demo-isolation-spec.md). This document summarizes what exists **today** in code.

## Configuration

| Variable | Purpose |
|----------|---------|
| `NF_DEMO_ORG_IDS` | Comma-separated org UUIDs classified as **demo** orgs. Any other UUID is treated as **real** for isolation helpers until a persistent `organizations` table exists. |
| `NF_DEV_ORG_HEADERS` | When `true` (default in local dev), the backend accepts `X-NF-Org-Id` to build dev org context. When `false`, isolation routes that depend on this return **503** — simulating production without dev headers. |

See `.env.example`.

## Helpers (`nativeforge.lib.demo_isolation`)

- **Parse / classify:** `parse_demo_org_ids`, `is_demo_org`, `org_type_for`
- **Read path:** `row_matches_reader_org_type`, `can_read_record` — demo orgs must only see demo-flagged rows for their org; real orgs only non-demo rows for their org
- **Write path:** `validate_record_write` — `is_demo` on a row must match whether the org is in the demo allowlist
- **HTTP-shaped checks:** `assert_demo_route_org`, `assert_real_route_org` (raise `DemoIsolationError`; map to 403 in routes)
- **Seeds:** `require_explicit_demo_seed_context` — fake/demo seeds must pass `explicit_demo_context=True` when tagging demo content

## Dev HTTP routes (`/v1/isolation/*`)

Smoke endpoints prove Layer 3 separation using **only** `X-NF-Org-Id` and the demo allowlist (no second header to spoof org type).

Production must replace dev headers with authenticated identity and a DB-backed `org_type`.

## Not implemented yet (later tickets)

- RLS policies, DB triggers, and the full seven CI checks from the spec
- `nf_*` DDL and repository-layer SQL (see `scripts/check_nf_sql_grep.py`)

## Validation

Full repo checks:

```bash
ruff check src tests && ruff format --check src tests
pytest -q
python scripts/check_nf_sql_grep.py
```

NF-001-focused subset:

```bash
bash scripts/validate_demo_isolation.sh
```
