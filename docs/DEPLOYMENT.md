# Deploying NativeForge

**Forge Portable Deployment Standard v1.**

NativeForge runs as one container plus a PostgreSQL database. That is the
whole architecture. Railway is the current host, and nothing in the
application knows that — the provider is a deployment target, not a
dependency.

The test that keeps it true:

> Can the complete runtime start on a machine with a container runtime and no
> account anywhere?

```bash
docker compose up --build
```

If that stops working, portability has been lost, whatever any document says.

---

## 1. What runs

| Component | What it is | Required for controlled-live |
| --- | --- | --- |
| **app** | FastAPI (uvicorn) + the built frontend, same origin | yes |
| **postgres** | PostgreSQL 16 | yes |
| worker / source collectors | scheduled ingestion | **no — stays off** |
| object store | S3-compatible, optional | no |
| cache / queue | none. No Redis, no Celery | no |

The frontend is **not** a separate service. It is built in the image and
served by the API process from the same origin. One container, one hostname,
no CORS, and nothing extra to reproduce on the next provider.

Source collectors are deliberately not deployed. Worker code existing is not a
reason to run it; live collection requires separate authorization.

---

## 2. Configuration

Everything comes from the environment. `.env.example` lists every variable and
names which are read by `Settings` and which by the container entrypoint.
Nothing is read at build time except the two build stamps below.

The ones that matter:

| Variable | Why it matters |
| --- | --- |
| `DATABASE_URL` | standard SQLAlchemy/libpq URL. PostgreSQL in every deployed environment |
| `NF_SESSION_SIGNING_KEY` | must be supplied out-of-band. The committed local fixture key may never sign a production session |
| `NF_DEV_ORG_HEADERS` | **must stay `false`**. It accepts an unauthenticated header that names the tenant every RLS policy reads |
| `NF_GIT_SHA` | build stamp. A container has no `.git`, so `/health` has to be told what it is running |
| `NF_RUN_MIGRATIONS` | `alembic upgrade head` on boot. See the warning in §4 |

---

## 3. Build

```bash
docker build \
  --build-arg NF_GIT_SHA="$(git rev-parse HEAD)" \
  --build-arg NF_SOURCE_DIRTY="$(test -n "$(git status --porcelain)" && echo true || echo false)" \
  -t nativeforge:local .
```

The frontend is built with `VITE_API_BASE=""` so every request is relative.
This is not cosmetic. `apiFetchBase()` falls back to `http://127.0.0.1:8000`
when that variable is unset, which means a deployed page probes **the
viewer's own machine** — it cannot succeed, it is mixed content on an HTTPS
page, and it fills the console with errors. An empty base also keeps the
image free of any hostname, so the same image can be promoted between
environments unchanged.

---

## 4. Migrations

Alembic owns the schema. Nothing else may alter it.

By default the entrypoint runs `alembic upgrade head` on boot, which is right
for a single instance: a database that silently lags the code is worse than a
slow start.

> **With more than one replica, set `NF_RUN_MIGRATIONS=false`** and run the
> entrypoint's `migrate` command as its own release step. Concurrent
> `alembic upgrade head` from several containers is a race, and Alembic does
> not arbitrate it.

```bash
docker run --rm -e DATABASE_URL=... nativeforge:local migrate
```

---

## 5. Database roles

The runtime role must be **`NOSUPERUSER`** and **`NOBYPASSRLS`**.

This is not hygiene, it is the tenant boundary. A superuser bypasses row-level
security unconditionally, regardless of `FORCE ROW LEVEL SECURITY`, so a
runtime connecting as the database owner silently disables every isolation
policy in the schema.

Managed providers hand out a root credential. Do not use it as the runtime
credential merely because it is the one that was given to you:

```sql
CREATE ROLE nf_app LOGIN PASSWORD '...' NOSUPERUSER NOBYPASSRLS
  NOCREATEDB NOCREATEROLE;
GRANT USAGE ON SCHEMA public TO nf_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO nf_app;
GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO nf_app;
```

Migrations run as the owner. The application runs as `nf_app`.

Verify, never assume:

```bash
DATABASE_URL=... python scripts/check_postgres_tenant_isolation.py
```

That gate checks coverage (every `organization_id` table has RLS, FORCE, a
policy and a `WITH CHECK`) and refusal (an adversarial matrix as a
non-superuser role). It is falsifiable: removing FORCE, dropping a
`WITH CHECK`, or replacing a policy with `USING (true)` each turn it red.

---

## 6. Health

`GET /health` returns `200` with the deployed `git_sha` and `source_dirty`.
Those come from the build stamps, because the container has no git.

A health endpoint that cannot say which commit it is running cannot be used to
verify a deployment — it proves only that *something* is answering.

---

## 7. Leaving Railway

Railway-specific **application** code: none. The coupling is configuration
only:

| Railway thing | Replacement anywhere else |
| --- | --- |
| service env vars | any env/secret manager |
| managed PostgreSQL | any PostgreSQL 16, same `DATABASE_URL` |
| `PORT` injection | already defaulted to 8000 |
| build from Dockerfile | any container registry/runtime |
| custom domain | Cloudflare DNS, which is authoritative regardless |

To move: build the image, run it against a PostgreSQL instance with the same
environment, repoint the Cloudflare record. The application does not change.

---

## 8. Local development

The container lane is **not** the day-to-day lane. Local development uses
SQLite:

```bash
scripts/m0_demo_up.sh
```

SQLite has no row-level security at all, so the tenant boundary is invisible
to the default test suite. Anything that claims tenant isolation must be
verified against PostgreSQL — `compose.yaml` or the CI `postgres-contract`
job, not the SQLite lane.
