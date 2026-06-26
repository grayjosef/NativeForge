# NativeForge M0 demo runbook

This document is the operator-facing guide for repeating the **M0 backend spine** demo and understanding what is real vs stubbed. It aligns with [`nativeforge-db-context-rules.md`](nativeforge-db-context-rules.md), [`HITP_COMMIT_GATE.md`](HITP_COMMIT_GATE.md), and [`research/execution/04-m0-implementation-plan.md`](../research/execution/04-m0-implementation-plan.md).

## Current M0 status

M0 is the **demo-era** backend: tenant-scoped APIs over `nf_*` tables, review-gated artifacts, deterministic scoring, pursuit pipeline with tasks and calendar events, SF-424 **preview** snapshots (not agency submission), and a trust surface (policy manifest, audit listing, review summary, org-wide JSON export).

There is **no buyer-facing product UI** in this repository beyond a frontend scaffold; demos are **API-first** (OpenAPI `/docs`, curl, HTTP client, or pytest).

## Backend spine (single narrative)

End-to-end order:

1. **Tribal profile** — org identity and contacts used later for previews.
2. **Grant Spark** — opportunity row (`nf_grant_sparks`).
3. **NOFO extraction** — `extract-stub` produces structured payload + checklist (review-gated).
4. **Structured requirements** — checklist rows exposed via requirements endpoint.
5. **Deterministic score** — pure scoring persisted to `nf_spark_scores`.
6. **Pursuit** — pipeline row; seeds **tasks** and **calendar** events.
7. **Form package** — SF-424 **preview** JSON (review-gated package row).
8. **Trust / audit / export** — manifest, audit events, review summary, **org data snapshot** export.

Automated **full-chain proof**: `tests/test_m0_full_chain_demo.py`.

## Required environment variables

| Variable | Purpose |
|----------|---------|
| `DATABASE_URL` | SQLAlchemy URL (file SQLite, Postgres, etc.). Tests use pytest’s file DB via `conftest.py`. |
| `NF_DEV_ORG_HEADERS` | Must be **`true`** for product routes to accept **`X-NF-Org-Id`** (dev/demo simulation). If `false`, org context returns **503**. Default in settings is `true`; production-shaped demos should set explicitly. |
| `NF_DEMO_ORG_IDS` | **Legacy only**: comma-separated UUIDs for **`/v1/isolation/*`** smoke routes. **Not** the source of truth for `/v1/nf/...` product APIs. |
| `NF_APP_NAME`, `NF_APP_ENV` | Optional app metadata. |

Copy `.env.example` to `.env` and adjust `DATABASE_URL` for local servers.

## How org context works (product routes)

1. Client sends header **`X-NF-Org-Id`** with a UUID string.
2. Server requires **`NF_DEV_ORG_HEADERS=true`** (M0 has **no JWT/auth**; this is deliberate).
3. Server loads **`organizations`** by id; **`organizations.org_type`** must be **`real`** or **`demo`** and must match the route plane (see below).
4. Session RLS GUCs are applied for Postgres (`apply_org_rls_gucs`) — see [`nativeforge-db-context-rules.md`](nativeforge-db-context-rules.md).

Path org id must equal header org id (403 otherwise).

## `NF_DEMO_ORG_IDS` smoke routes vs DB-backed `/v1/nf/...`

| Mechanism | Routes | Source of truth |
|-----------|--------|-------------------|
| **Legacy NF-001** | `/v1/isolation/demo-only`, `/v1/isolation/real-only` | **`NF_DEMO_ORG_IDS`** allowlist — **no DB row required** |
| **Product M0 spine** | `/v1/nf/demo/orgs/...`, `/v1/nf/real/orgs/...` | **`organizations`** row + **`org_type`** + **`X-NF-Org-Id`** |

For the M0 demo **always use `/v1/nf/...`** and a seeded **`organizations`** row. Do not confuse the isolation smoke endpoints with the grant spine.

## Seeding an organization for a demo

There is **no org registration API** in M0. Create a row directly (migration, SQL, or test fixture).

**SQLite / generic SQL** (adjust UUID):

```sql
-- Real org (use with /v1/nf/real/orgs/{org_id}/...)
INSERT INTO organizations (id, org_type)
VALUES ('aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee', 'real');

-- Demo org (use with /v1/nf/demo/orgs/{org_id}/...)
INSERT INTO organizations (id, org_type)
VALUES ('bbbbbbbb-cccc-dddd-eeee-ffffffffffff', 'demo');
```

Then:

```bash
export NF_DEV_ORG_HEADERS=true
# Optional: uvicorn nativeforge.main:app --reload
```

Every request must include:

```http
X-NF-Org-Id: <same UUID as organizations.id>
```

## API sequence — **real** org (`org_type=real`)

Replace `BASE` (e.g. `http://127.0.0.1:8000`), `ORG` (path + header UUID), and JSON bodies as needed.

| Step | Method | Path |
|------|--------|------|
| 1 Tribal profile | `POST` | `/v1/nf/real/orgs/{ORG}/tribal-profile` |
| 2 Grant Spark | `POST` | `/v1/nf/real/orgs/{ORG}/grant-sparks` |
| 3 NOFO stub extract | `POST` | `/v1/nf/real/orgs/{ORG}/grant-sparks/{SPARK}/nofo/extract-stub` |
| 4 Requirements | `GET` | `/v1/nf/real/orgs/{ORG}/grant-sparks/{SPARK}/nofo/requirements` |
| 5 Score | `POST` | `/v1/nf/real/orgs/{ORG}/grant-sparks/{SPARK}/score` |
| 6 Pursuit | `POST` | `/v1/nf/real/orgs/{ORG}/grant-sparks/{SPARK}/pursuit` |
| 7 Pursuit detail (tasks/calendar) | `GET` | `/v1/nf/real/orgs/{ORG}/pursuits/{PURSUIT}` |
| 8 Form package / SF-424 preview | `POST` | `/v1/nf/real/orgs/{ORG}/pursuits/{PURSUIT}/form-package` |
| 9 Trust manifest | `GET` | `/v1/nf/real/orgs/{ORG}/trust/manifest` |
| 10 Audit events | `GET` | `/v1/nf/real/orgs/{ORG}/trust/audit-events` |
| 11 Review summary | `GET` | `/v1/nf/real/orgs/{ORG}/trust/review-summary` |
| 12 Export snapshot | `GET` | `/v1/nf/real/orgs/{ORG}/export/org-data-snapshot` |

Query params (examples): `export` supports `audit_sample_limit`, `include_sf424_previews`, optional `actor_id`.

## API sequence — **demo** org (`org_type=demo`)

Same steps with prefix **`/v1/nf/demo/orgs/{ORG}/...`** for every call. The organization row **must** have `org_type='demo'`.

## OpenAPI `/docs`, curl, TestClient

- **Swagger UI**: start the app (`uvicorn nativeforge.main:app --reload`), open **`http://127.0.0.1:8000/docs`**, authorize or add header **`X-NF-Org-Id`** per operation (depending on client).
- **curl**: pass `-H "X-NF-Org-Id: <uuid>"` on each request.
- **pytest TestClient**: pass `headers={"X-NF-Org-Id": str(org_uuid)}` — see `tests/test_m0_full_chain_demo.py`.

## What is deterministic / stubbed

- **NOFO extraction**: **`extract-stub`** — deterministic stub pipeline, **not** live LLM extraction and **not** Grants.gov pull.
- **Scoring**: deterministic rules; same inputs → same outputs.
- **SF-424 preview**: structured JSON preview built from profile + spark + pursuit context — **not** a filed PDF and **not** Grants.gov submit.

## What is intentionally not implemented (M0)

- Grants.gov live ingestion / auto-submit (see trust manifest).
- Authentication / RBAC (header-only org simulation).
- Org self-registration HTTP API.
- Private deployment / SOC 2 claims as enforced guarantees (deferred items appear in trust manifest).

Full validation before merge: `bash scripts/nativeforge_full_validation.sh` ([`HITP_COMMIT_GATE.md`](HITP_COMMIT_GATE.md)).

## Operator Activation console (M8)

Flip live-publish, live-attribution, and auto-publish flags from the **Activation** view in the UI (`?view=activation` in the header toggle), or via API:

```http
GET /v1/nf/demo/orgs/{ORG}/operator/activation
X-NF-Org-Id: {ORG}
```

Governed mutations (operator/admin only; agents denied):

```http
POST /v1/nf/demo/orgs/{ORG}/operator/activation/governed-action?actor_id={ACTOR}
X-NF-Org-Id: {ORG}
X-NF-Actor-Role: operator
Content-Type: application/json

{"governed_action":"activation:toggle","toggle":"kill_switch","value":true}
```

- **Kill switch** — engage is one click (no confirm dialog); release via `activation:toggle` with `value: false`.
- **Live publish / auto-publish enable** — require `reason` in the JSON body (mirrors score override pattern); audited.
- **Auto-publish enable** — use `governed_action: "policy:change"`; appends a versioned `nf_auto_publish_config` row (M7).
- All flags default **OFF**; state is durable per workspace in `nf_activation_state`.

## Buyer-safe language (M0 commitments)

Use these points in live demos:

- **No auto-submit** — M0 does not submit applications to Grants.gov or agency portals; submission stays manual outside NativeForge.
- **Human review required** — draft outputs and review artifacts are gated; workflows expect reviewer action before anything is treated as final.
- **Generated / autofilled content is not final** — SF-424 **previews** are non-final snapshots; not submission-ready agency PDFs.
- **Organization owns its data** — tenant-scoped storage; policy narrative is summarized in **`GET .../trust/manifest`** (`data_ownership`).
- **Export available** — **`GET .../export/org-data-snapshot`** produces an org-wide JSON bundle (and records an audit event).
- **Demo data isolated** — demo orgs use the **demo** API plane and **`is_demo`** semantics; real org rows are separate ([`nativeforge-db-context-rules.md`](nativeforge-db-context-rules.md)).
