# NativeForge M0 — operator checklist

Use this page to run the **M0 demo-era** backend and buyer demo shell **without guessing**. Narrative order matches [`m0-demo-runbook.md`](m0-demo-runbook.md). Deep API tables stay in the runbook; this checklist is copy-paste startup and verification.

---

## 1. Prerequisites

- Python **3.11+** with **`uv`** (same toolchain as `scripts/nativeforge_full_validation.sh`).
- **Node.js** and npm for the frontend shell (`frontend/`).
- A database URL where **`organizations`** exists (apply migrations once per environment).

Create schema if needed:

```bash
cd ~/projects/nativeforge
cp -n .env.example .env    # do not overwrite an existing .env
# Edit .env: set DATABASE_URL (SQLite file or Postgres — match your operator setup).
uv run alembic upgrade head
```

---

## 2. Required environment variables

| Variable | Required | Notes |
|----------|----------|--------|
| `DATABASE_URL` | **Yes** (for any API that touches the DB) | SQLAlchemy URL. Default in code is in-memory SQLite and is **not** what you use for a long-running local server with a file or Postgres. |
| `NF_DEV_ORG_HEADERS` | **Yes for M0 product routes** | Set to **`true`** so the server accepts **`X-NF-Org-Id`** (M0 has no JWT; this is dev/demo simulation). If `false`, org context returns **503**. |
| `NF_DEMO_ORG_IDS` | No for `/v1/nf/...` | Legacy allowlist for **`/v1/isolation/*`** smoke routes only. **Not** the source of truth for the M0 grant spine. |
| `NF_APP_NAME`, `NF_APP_ENV` | No | Optional metadata. |

Copy [`.env.example`](../.env.example) to `.env` and set at least `DATABASE_URL` and `NF_DEV_ORG_HEADERS=true`.

---

## 3. Seed organizations (demo + real)

M0 has **no org registration HTTP API**. You need one row per tenant in **`organizations`** with `org_type` **`demo`** or **`real`**, matching the API plane you call.

### Option A — deterministic helper (recommended)

From the repo root (after `alembic upgrade head`):

```bash
cd ~/projects/nativeforge
export NF_DEV_ORG_HEADERS=true   # not required for the seed script; required when calling the API
uv run python scripts/seed_m0_demo_data.py
```

This inserts **only** the two canonical M0 operator org UUIDs (see script output). It is **idempotent** (safe to re-run). It does **not** create tribal profiles, Grant Sparks, or other tenant data — only tenant roots.

### Option B — SQL

Use the same UUIDs as [`m0-demo-runbook.md`](m0-demo-runbook.md) `INSERT` examples, or the UUIDs printed by the seed script.

- **Demo org** — use with **`/v1/nf/demo/orgs/{org_id}/...`** and `organizations.org_type = 'demo'`.
- **Real org** — use with **`/v1/nf/real/orgs/{org_id}/...`** and `organizations.org_type = 'real'`.

Every product request must include:

```http
X-NF-Org-Id: <same UUID as organizations.id>
```

---

## 4. Start the backend (exact command)

From the repository root, with `.env` loaded (current shell or file present for pydantic-settings):

```bash
cd ~/projects/nativeforge
uv run uvicorn nativeforge.main:app --reload --host 127.0.0.1 --port 8000
```

Leave this terminal running. Default API base: **`http://127.0.0.1:8000`**.

---

## 5. Start the frontend demo shell (exact command)

In a **second** terminal:

```bash
cd ~/projects/nativeforge/frontend
npm ci
npm run dev
```

---

## 6. Verify `/health`

**Browser or curl (through Vite dev server):**

- With only the frontend running, open the shell and click **Ping GET /health**, or visit **`http://127.0.0.1:5173/`** and use the button (Vite proxies `/health` to the API).

**curl (API directly):**

```bash
curl -sS http://127.0.0.1:8000/health
```

Expect HTTP **200** and a JSON body (status fields from the health router).

---

## 7. Verify `/docs` (OpenAPI / Swagger UI)

Open in a browser:

- **Direct to API:** **`http://127.0.0.1:8000/docs`**
- **Through Vite (same origin as the shell):** **`http://127.0.0.1:5173/docs`** (proxied to the API)

Use **Authorize** or per-request **`X-NF-Org-Id`** as required by each operation.

---

## 8. Verify trust manifest

Replace `ORG` and plane with your seeded org (demo example):

```bash
curl -sS -H "X-NF-Org-Id: bbbbbbbb-cccc-dddd-eeee-ffffffffffff" \
  "http://127.0.0.1:8000/v1/nf/demo/orgs/bbbbbbbb-cccc-dddd-eeee-ffffffffffff/trust/manifest"
```

Or use the demo shell: set **API plane** to **demo**, paste the **same org UUID** in **Organization UUID**, then **GET trust/manifest (with header)**.

Expect HTTP **200** and JSON including **`manifest_schema_version`** (e.g. `m0_trust_v1`), **`submission_policy`**, and **`review_gate_policy`** — the **trust surface** for buyer conversations.

---

## 9. Frontend demo URL (exact)

**`http://127.0.0.1:5173/`**

(Vite default port **5173**; see `frontend/vite.config.ts`.)

---

## 10. Buyer demo talk track (use NativeForge language)

Read in order; pause for OpenAPI or curl where noted.

1. **Framing** — NativeForge M0 is a **tenant-scoped grant pursuit spine**: tribal profile, **Grant Spark**, **NOFO** handling, scoring, **pursuit** with tasks and calendar, **SF-424 preview**, then **trust surface** (policy manifest, **audit events**, review summary, org export). This repo ships **API-first** proof; the browser shell is a **guided narrative**, not a full product UI.

2. **Trust first** — Open **`/docs`** or **`GET .../trust/manifest`**. Call out **no automatic submission** to Grants.gov or agency portals in M0, **human review** on gated artifacts, and **SF-424 previews** as non-final snapshots — not agency submission packages.

3. **Tribal profile** — Organization identity and contacts feed later **SF-424 preview** and exports.

4. **Grant Spark** — One tracked opportunity row for the tenant (**Grant Spark**).

5. **NOFO** — **`extract-stub`** returns structured requirements and checklist rows for review; emphasize **deterministic stub**, not live ingestion.

6. **Score** — **Deterministic** pursuit-readiness scoring (same inputs → same outputs).

7. **Pursuit** — Opening a **pursuit** seeds **tasks** and **calendar** anchors (for example application deadline).

8. **Forms** — **Form package** with **SF-424 preview** JSON — preview only; filing stays outside NativeForge in M0.

9. **Trust / audit / export** — Show **`GET .../trust/audit-events`**, **`.../trust/review-summary`**, and **`GET .../export/org-data-snapshot`**: **audit events**, review posture, and tenant-owned data export.

10. **Proof** — Automated full-chain test: `tests/test_m0_full_chain_demo.py`. Full repo gate: `bash scripts/nativeforge_full_validation.sh`.

11. **Demo vs real planes** — **Demo** orgs use **`/v1/nf/demo/orgs/...`**; **real** org rows use **`/v1/nf/real/orgs/...`**. Path org id must match **`X-NF-Org-Id`**.

---

## 11. Stubbed or out of scope (M0)

Be explicit with buyers:

| Area | M0 behavior |
|------|-------------|
| **NOFO extraction** | **`extract-stub`** only — deterministic; **not** live AI/LLM extraction. |
| **Opportunity ingestion** | **Not** live Grants.gov or agency feed pull. |
| **Scoring** | Rule-based / deterministic — **not** a trained ML guarantee. |
| **SF-424** | **Preview** JSON in-product — **not** agency submit; **not** a filed PDF. |
| **Authentication / RBAC** | **None** — org simulation via **`X-NF-Org-Id`** + **`NF_DEV_ORG_HEADERS`**. |
| **Org self-service signup** | **No** registration API — org rows are created by operators (SQL or seed helper). |
| **Private deployment / compliance attestations** | **Not** enforced product guarantees; deferred items may appear narratively in the **trust manifest**. |
| **Buyer product UI** | Beyond this checklist: scaffold shell only; **no** Sprint 8 scope. |

---

## 12. Related docs

- [`m0-demo-runbook.md`](m0-demo-runbook.md) — full API sequence and curl patterns.
- [`nativeforge-db-context-rules.md`](nativeforge-db-context-rules.md) — tenant and RLS context.
- `tests/test_m0_full_chain_demo.py` — automated **full-chain** proof.
