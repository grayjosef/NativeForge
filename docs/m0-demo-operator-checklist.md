# NativeForge M0 — operator checklist

Use this page to run the **M0 demo-era** backend and buyer demo shell **without guessing**. Narrative order matches [`m0-demo-runbook.md`](m0-demo-runbook.md). Deep API tables stay in the runbook; this checklist is copy-paste startup and verification.

### Critical: do not use default in-memory SQLite for the local browser demo

Application settings default to **`sqlite+pysqlite:///:memory:`**. That database exists **only inside the running API process**. If you run **`uv run alembic upgrade head`** or **`uv run python scripts/seed_m0_demo_data.py`** in a **separate** shell without the **same** `DATABASE_URL`, migrations and seed data apply to a **different** SQLite database than the one `uvicorn` opens. The API then hits routes that query **`organizations`** and can return **500** with:

`sqlite3.OperationalError: no such table: organizations`

**`GET /health` can still return 200** — health does not prove schema or tenant data. For an interactive local demo (browser shell, trust manifest, product routes), use a **file-backed** `DATABASE_URL` so the CLI and the server share one durable database file.

---

## 1. Prerequisites

- Python **3.11+** with **`uv`** (same toolchain as `scripts/nativeforge_full_validation.sh`).
- **Node.js** and npm for the frontend shell (`frontend/`).

---

## 2. Local demo — proven `.env` (file-backed SQLite)

Put this in **`.env`** at the repo root (create from [`.env.example`](../.env.example) if needed). Use these values for the **browser demo** flow below:

```env
DATABASE_URL=sqlite+pysqlite:///./nativeforge.local.db
NF_DEV_ORG_HEADERS=true
```

Postgres or another SQLite path is fine **if** Alembic, the seed script, and `uvicorn` all see the **same** `DATABASE_URL`.

---

## 3. Local demo — bootstrap sequence (migrations + seed)

Run once per machine (or when you intentionally reset the local file DB). The `rm` step **deletes** the local SQLite file — omit it if you want to keep existing data.

```bash
cd ~/projects/nativeforge
rm -f nativeforge.local.db
export DATABASE_URL=sqlite+pysqlite:///./nativeforge.local.db
export NF_DEV_ORG_HEADERS=true
uv run alembic upgrade head
uv run python scripts/seed_m0_demo_data.py
```

Then **start the backend in a shell that uses the same exports** (see [section 6](#6-start-the-backend-exact-command)), or rely on **`.env`** with identical `DATABASE_URL` / `NF_DEV_ORG_HEADERS` so pydantic-settings loads them into the server process.

---

## 3b. Operator shortcut — full local demo reset (`nf-reset`)

Use **before a walkthrough** when you want the browser **Run M0 sequence** to start from a **known-clean file database** (buyer-safe: resets **local demo state only**, does **not** delete **`.env`** or source trees).

From the repo root:

```bash
cd ~/projects/nativeforge
./nf-reset
# equivalent: bash scripts/m0_demo_reset.sh
```

**What it does:**

1. Stops managed backend/frontend processes if running (same as **`nf-down`** / `scripts/m0_demo_down.sh`).
2. Removes local runtime paths under the repo only: **`.run/`**, **`logs/`**, **`nativeforge.local.db`**, **`uv.lock`**.
3. Recreates the DB with **`DATABASE_URL=sqlite+pysqlite:///./nativeforge.local.db`**, **`NF_DEV_ORG_HEADERS=true`**, then **`uv run alembic upgrade head`** and **`uv run python scripts/seed_m0_demo_data.py`**.
4. Does **not** start servers unless you pass **`--up`** (then runs **`scripts/m0_demo_up.sh`** after reset).

```bash
./nf-reset --up    # reset, then same managed start as nf-up
```

---

## 4. Required environment variables

| Variable | Required | Notes |
|----------|----------|--------|
| `DATABASE_URL` | **Yes** (for any API that touches the DB) | Default in code is **`sqlite+pysqlite:///:memory:`** — **avoid** that for local browser demo (see warning above). Prefer a **file** URL such as **`sqlite+pysqlite:///./nativeforge.local.db`** shared by Alembic, seed, and `uvicorn`. |
| `NF_DEV_ORG_HEADERS` | **Yes for M0 product routes** | Set to **`true`** so the server accepts **`X-NF-Org-Id`** (M0 has no JWT; this is dev/demo simulation). If `false`, org context returns **503**. |
| `NF_DEMO_ORG_IDS` | No for `/v1/nf/...` | Legacy allowlist for **`/v1/isolation/*`** smoke routes only. **Not** the source of truth for the M0 grant spine. |
| `NF_APP_NAME`, `NF_APP_ENV` | No | Optional metadata. |

Copy [`.env.example`](../.env.example) to `.env` and align **`DATABASE_URL`** and **`NF_DEV_ORG_HEADERS`** with the bootstrap block in [section 3](#3-local-demo--bootstrap-sequence-migrations--seed).

---

## 5. Seed organizations (demo + real)

M0 has **no org registration HTTP API**. You need one row per tenant in **`organizations`** with `org_type` **`demo`** or **`real`**, matching the API plane you call.

### Option A — deterministic helper (recommended)

From the repo root (after `alembic upgrade head`), use the **same** `DATABASE_URL` as the running API (file-backed for local demo):

```bash
cd ~/projects/nativeforge
export DATABASE_URL=sqlite+pysqlite:///./nativeforge.local.db
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

## 6. Start the backend (exact command)

From the repository root, the backend must use the **same** `DATABASE_URL` you migrated and seeded (export in the shell **or** `.env` at repo root):

```bash
cd ~/projects/nativeforge
export DATABASE_URL=sqlite+pysqlite:///./nativeforge.local.db
export NF_DEV_ORG_HEADERS=true
uv run uvicorn nativeforge.main:app --reload --host 127.0.0.1 --port 8000
```

Leave this terminal running. Default API base: **`http://127.0.0.1:8000`**.

---

## 7. Start the frontend demo shell (exact command)

In a **second** terminal:

```bash
cd ~/projects/nativeforge/frontend
npm ci
npm run dev
```

On **`http://127.0.0.1:5173/`**, choose **API plane** and **Organization UUID**, then **Run M0 sequence** to execute the full M0 chain live against the backend (step log in-page). Same prerequisites as manual curls: **file-backed** `DATABASE_URL`, migrations, seeded org, **`NF_DEV_ORG_HEADERS=true`**, and backend running.

---

## 8. Verify `/health`

**Browser or curl (through Vite dev server):**

- With only the frontend running, open the shell and click **Ping GET /health**, or visit **`http://127.0.0.1:5173/`** and use the button (Vite proxies `/health` to the API).

**curl (API directly):**

```bash
curl -sS http://127.0.0.1:8000/health
```

Expect HTTP **200** and a JSON body (status fields from the health router). **`/health` alone does not prove** migrations ran or that product routes will succeed — confirm **`GET .../trust/manifest`** ([section 10](#10-verify-trust-manifest)) after seeding.

---

## 9. Verify `/docs` (OpenAPI / Swagger UI)

Open in a browser:

- **Direct to API:** **`http://127.0.0.1:8000/docs`**
- **Through Vite (same origin as the shell):** **`http://127.0.0.1:5173/docs`** (proxied to the API)

Use **Authorize** or per-request **`X-NF-Org-Id`** as required by each operation.

---

## 10. Verify trust manifest

Replace `ORG` and plane with your seeded org (demo example):

```bash
curl -sS -H "X-NF-Org-Id: bbbbbbbb-cccc-dddd-eeee-ffffffffffff" \
  "http://127.0.0.1:8000/v1/nf/demo/orgs/bbbbbbbb-cccc-dddd-eeee-ffffffffffff/trust/manifest"
```

Or use the demo shell: set **API plane** to **demo**, paste the **same org UUID** in **Organization UUID**, then **GET trust/manifest (with header)**.

Expect HTTP **200** and JSON including **`manifest_schema_version`** (e.g. `m0_trust_v1`), **`submission_policy`**, and **`review_gate_policy`** — the **trust surface** for buyer conversations.

---

## 11. Troubleshooting: trust manifest 500 / `no such table: organizations`

If **`GET .../trust/manifest`** returns **500** and server logs show **`sqlite3.OperationalError: no such table: organizations`** (or similar), typical causes are:

1. **In-memory default** — The API is on **`sqlite+pysqlite:///:memory:`** while Alembic/seed used another URL, or nothing was migrated into the process’s database.
2. **Unmigrated file DB** — `DATABASE_URL` points at a file but **`uv run alembic upgrade head`** was never run for that file.

**Fix:** Set a **file-backed** `DATABASE_URL` (e.g. **`sqlite+pysqlite:///./nativeforge.local.db`**) for **every** step: Alembic, seed script, and `uvicorn`. Run **`uv run alembic upgrade head`**, **`uv run python scripts/seed_m0_demo_data.py`**, then **restart** the backend so it picks up the same database.

---

## 12. Frontend demo URL (exact)

**`http://127.0.0.1:5173/`**

(Vite default port **5173**; see `frontend/vite.config.ts`.)

---

## 13. Buyer demo talk track (use NativeForge language)

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

## 14. Stubbed or out of scope (M0)

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

## 15. Related docs

- [`m0-demo-runbook.md`](m0-demo-runbook.md) — full API sequence and curl patterns.
- [`nativeforge-db-context-rules.md`](nativeforge-db-context-rules.md) — tenant and RLS context.
- `tests/test_m0_full_chain_demo.py` — automated **full-chain** proof.
