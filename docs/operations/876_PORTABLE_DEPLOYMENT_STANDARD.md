# 876 — Forge Portable Deployment Standard v1, executed

Phases 6–11 of the controlled-live campaign: make NativeForge deployable
anywhere, prove it, and only then choose a host. Railway is the intended first
host; nothing below depends on it, which is the point.

---

## 1. The escape test, run rather than asserted

> Can the complete runtime start on a machine with a container runtime and no
> account anywhere?

```
DOCKER_BUILD   PASS    multi-stage, non-root uid 10001
COMPOSE_BOOT   PASS    postgres:16 healthy, app healthy
FROM_ZERO      PASS    base -> 0067 inside the container
HEALTH         200
TENANT_GATE    18/18   against the containerised PostgreSQL
```

`docker compose up --build` gives PostgreSQL 16 and the application, migrated
from zero, on any machine with a container runtime. No provider API, no
provider CLI, no account. If that stops working, portability has been lost
whatever this document says.

The tenant isolation contract was run against that containerised database, not
only against the local development server: 54 tenant tables with RLS, FORCE, a
policy and a `WITH CHECK`, plus the adversarial matrix as a `NOSUPERUSER`,
`NOBYPASSRLS` role that owns nothing.

---

## 2. Two blockers that only a real deployment reveals

Both were invisible to the test suite because both are properties of a built,
served artifact rather than of the source.

### 2.1 The built frontend probed the viewer's own machine

`apiFetchBase()` ends:

```ts
return fromEnv?.replace(/\/$/, "") ?? "http://127.0.0.1:8000";
```

In development Vite proxies `/health` and `/v1` to the API, so this never
fires. In a production build with `VITE_API_BASE` unset it does: a deployed
page asks **the viewer's browser** to call `http://127.0.0.1:8000`. That can
never succeed, it is mixed content on an HTTPS page, and it fills the console
with errors. `App.tsx` already carried a comment describing exactly this
symptom for the offline demo surfaces — the cause was general.

Fixed without touching the frontend logic. The fallback uses `??`, which is
nullish-coalescing, so building with `VITE_API_BASE=""` yields an empty base
and every request becomes relative:

```js
function Nn(){return(""==null?void 0:"".replace(/\/$/,""))??"http://127.0.0.1:8000"}
```

The literal survives in the bundle as unreachable text, never as a value.
Verified in a browser against the container — every request went to the
serving origin:

```
GET /                     200
GET /assets/index-*.js    200   3,074,274 bytes
GET /brand/nf-mark.svg    200
GET /health               200
GET /v1/nf/demo/orgs/...  401
```

An empty base also keeps the image free of any hostname, so the same image can
be promoted between environments unchanged.

### 2.2 `/health` could not say what was deployed

It returned `{"status": "ok", "service": "nativeforge"}`. That proves
*something* is answering. It does not prove the thing answering is the thing
you shipped, which is the only question worth asking after a cutover.

The repository already had services that know the commit — they run
`git rev-parse HEAD` and `git status --porcelain`. That works in a checkout
and returns nothing useful in a container: no `.git`, no git binary. The
environment where the answer matters most is exactly the one where that
approach fails.

`/health` now reports build-time stamps:

```json
{"status":"ok","service":"nativeforge","git_sha":"...","source_dirty":false}
```

`source_dirty` is tri-state: `true`, `false`, or `null`. **`null` is not a
synonym for clean.** An unstamped image has been told nothing, and reporting
`false` there would assert cleanliness on no evidence — the same failure mode
as a gate that clears a blocker because a variable was never set.

`test_gate101` asserted the health body by exact equality. That contract was
changed deliberately, in the same commit, rather than discovered later.

---

## 3. The frontend is served by the API, on purpose

One container, one hostname, no CORS, and one thing to reproduce on the next
provider. Split into two services the frontend must be told the API's address,
which is what produced §2.1 in the first place.

The mount is registered **last**, after every router. A mount at `/` is a
catch-all; registered earlier it would shadow every API path in the
application. Verified: `/openapi.json` still returns 200 with the mount
active.

`NF_FRONTEND_DIST` empty means no frontend bundled, which is how the test
suite and the SQLite development lane run.

---

## 4. What a secure deployment actually looks like on first boot

Worth stating plainly, because it looks like a bug and is not.

With `NF_DEV_ORG_HEADERS=false` (the new default) and no OIDC configured, the
workspace renders and every data call returns **401**:

```
GET /v1/nf/demo/orgs/bbbbbbbb-cccc-dddd-eeee-ffffffffffff/tribal-profile  401
```

That is the fail-closed default working end to end. `X-NF-Org-Id` names the
tenant every row-level security policy reads and nothing authenticates it, so
a deployment that has not configured real identity has no authenticated way to
name an organisation — and correctly refuses.

**Controlled-live will therefore be a working, secure, empty workspace until
OIDC is configured.** Turning the dev header back on to make the demo populate
would hand any caller an attacker-chosen tenant. It is not an option.

---

## 5. Portability inventory

`RAILWAY_SPECIFIC_APPLICATION_CODE = 0`. The coupling is configuration only:

| Provider feature | Replacement anywhere else |
| --- | --- |
| service environment variables | any env/secret manager |
| managed PostgreSQL | any PostgreSQL 16, same `DATABASE_URL` |
| injected `PORT` | already defaulted to 8000 |
| build from Dockerfile | any container registry or runtime |
| custom domain | Cloudflare DNS, authoritative regardless |

No Redis. No Celery. No queue. None are dependencies of this application, and
none were provisioned to look like architecture.

Object storage is S3-compatible and optional; all six settings default to
empty, which is a supported state.

---

## 6. Migrations

Alembic owns the schema. The entrypoint runs `alembic upgrade head` on boot by
default, which is right for a single instance.

**With more than one replica this must be turned off** (`NF_RUN_MIGRATIONS=false`)
and run as a separate release step via the entrypoint's `migrate` command.
Concurrent `alembic upgrade head` from several containers is a race and
Alembic does not arbitrate it. The default is chosen for the deployment we
have, not the one we might have.

---

## 7. Files

| File | Purpose |
| --- | --- |
| `Dockerfile` | two stages, pinned uv 0.11.7, non-root, build stamps |
| `deploy/docker-entrypoint.sh` | `serve` / `migrate`, deterministic startup |
| `compose.yaml` | the escape test, runnable |
| `.dockerignore` | context would otherwise carry `.venv`, `node_modules` and ~2,000 smoke artifacts |
| `.env.example` | every variable, checked against `settings.py` |
| `docs/DEPLOYMENT.md` | the operator document |

`.gitignore` now excludes `artifacts/*_smoke/`. Roughly 2,000 timestamped
smoke outputs were accumulating untracked, one `git add -A` away from being
committed. Files already tracked are unaffected — historical evidence is
kept, new litter is not collected.

---

## 8. Known unknowns

- **The full suite is a ~7 hour run.** A previous attempt was killed by a
  90-minute timeout at 21%. Any claim that "the suite is green" must name the
  run that proved it.
- **A deployed NativeForge has no working authentication path yet.** §4. OIDC
  is unconfigured, so controlled-live demonstrates the shell and the security
  posture, not the product.
- **`mayhem-nc.dev` is split-delegated.** The registry delegates to Porkbun
  while Cloudflare also answers authoritatively with different data, so
  resolution differs by resolver and `n8n.mayhem-nc.dev` and
  `nf-dev.mayhem-nc.dev` currently return nothing. No hostname-specific record
  can fix that; it is a zone-level decision affecting n8n and the apex.
