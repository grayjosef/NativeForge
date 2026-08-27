# 562 — Gate 101A: persistent backend process survey

Verified rather than assumed. The survey corrects the brief in one place and
finds a collision the brief did not anticipate.

## Where the FastAPI app is created

```text
src/nativeforge/main.py:54    def create_app() -> FastAPI
src/nativeforge/main.py:56    app = FastAPI(title=settings.app_name)
src/nativeforge/main.py:90    app = create_app()
```

Twenty-eight routers are registered. There is **no lifespan hook, no
`on_event`, no startup or shutdown handler** — confirmed by reading all 90 lines.
So there is still nowhere for an in-process background task to attach, which is
what Gate 100 concluded and what makes this gate the prerequisite it is.

## A health endpoint already exists — the brief implies otherwise

```python
# src/nativeforge/api/health.py
@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "nativeforge"}
```

Two fields, no database, no git sha, no runtime mode, no timestamp. It answers
"is this process up" and nothing else. Gate 101C extends the surface rather than
inventing one, because a second `/health` would be a second answer to the same
question.

## The collision: two different `/health` surfaces already disagree

This is the finding that shapes 101C.

```text
http://127.0.0.1:5175/health   ->  ok
                                   (plain text, stamped static file)
http://127.0.0.1:5175/version  ->  {"app": "nativeforge",
                                    "artifact_kind": "dev-domain-demo",
                                    "git_sha": "755d422...",
                                    "build_time": "2026-08-27T22:20:07Z",
                                    "source_dirty": false}

backend /health                ->  {"status": "ok", "service": "nativeforge"}
                                   (JSON, no sha, requires a running process)
```

The Vite preview serves a **static** `/health` and `/version`, written by
`scripts/build_frontend_stamped.sh` from `git rev-parse HEAD` and
`NF_STAMP_SOURCE_DIRTY`. It is a build stamp. It is up right now, and it will
answer `ok` whether or not any backend exists.

That matters: a monitor pointed at `:5175/health` would report the system healthy
with no backend running at all. Gate 101C therefore puts the backend health
contract at **`/backend/health`** rather than extending `/health`, so the two
answers cannot be mistaken for one another, and the backend contract carries the
runtime mode that says which kind of alive it means.

## How the API is started today

Only ephemerally, by scripts that background it and kill it:

```text
scripts/m8_close_gate_staging_smoke.sh:37
  .venv/bin/uvicorn nativeforge.main:app --host 127.0.0.1 --port "$PORT" &
  SERVER_PID=$!
  trap 'kill $SERVER_PID 2>/dev/null || true' EXIT

scripts/m0_demo_up.sh:46                uvicorn ... --reload --port 8000
scripts/la_scale_federal_staging_verify.sh:37   uvicorn ... &
```

Every one binds `127.0.0.1` already, so loopback-only is the established
convention rather than something this gate introduces.

## uvicorn

```text
pyproject.toml:12   "fastapi>=0.115"
pyproject.toml:13   "uvicorn[standard]>=0.32"
```

Declared and installed. No dependency is needed to run a persistent backend, and
`uv.lock` does not change in this gate.

## Backend systemd unit: none

```text
~/.config/systemd/user/
  nativeforge-cloudflared.service
  nativeforge-demo-preview.service     Vite preview, 127.0.0.1:5175   running
  nativeforge-mayhem-tunnel.service    Cloudflare tunnel              running
```

No unit runs the API. `deploy/` does not exist, so Gate 101D creates
`deploy/systemd/nativeforge-backend.service` as a **template that is not
installed and not enabled**.

## Does /trust require the backend runtime? Yes

```text
demo_trust_router  prefix="/v1/nf/demo/orgs"   /{org_id}/trust/manifest
real_trust_router  prefix="/v1/nf/real/orgs"   /{org_id}/trust/manifest
                                               /{org_id}/trust/audit-events
                                               /{org_id}/trust/review-summary
                                               /{org_id}/export/org-data-snapshot
```

These are API routes. Without a backend process they do not answer at all.

## What the frontend preview serves without a backend

The SPA and its stamped static files. Its API clients default to a backend that
is not running:

```text
frontend/src/m0ApiClient.ts:12   VITE_API_BASE ?? "http://127.0.0.1:8000"
frontend/src/m0ApiClient.ts:92   fetch(`${baseUrl}/health`)
frontend/src/discoveryApiClient.ts, activationApiClient.ts, workbenchApiClient.ts
```

`VITE_API_BASE` is not set anywhere in `frontend/.env*` or `vite.config`, so the
default applies. The Playwright suite runs against `http://127.0.0.1:4173` with
its own `webServer` and passes with no backend — which means the surfaces it
exercises are static or demo-fixture backed, not API backed.

**What must remain static/demo-only:** everything the preview currently shows.
Nothing in this gate changes what the demo serves, and no API-backed surface
becomes live because no backend is started.

## Which port is safe

```text
127.0.0.1:5175   Vite preview        in use
127.0.0.1:20242  cloudflared         in use
127.0.0.1:4173   Playwright web      transient
127.0.0.1:8000   backend             FREE
```

`8000` is free, is what `m0_demo_up.sh` uses, and is what the frontend already
defaults to. The contract uses `127.0.0.1:8000`, loopback only.

## Can the API run loopback-only? Yes, and it already does

Every existing invocation binds `127.0.0.1`. The systemd template does the same
and a test parses it to prove no public interface is bound — a unit binding
`0.0.0.0` would put the API on the tunnel, which is the one mistake in this gate
that would matter.

## Inputs surveyed

```text
src/nativeforge/main.py       read in full (90 lines)
src/nativeforge/api/health.py, trust_routes.py
scripts/*.sh                  uvicorn invocation sites
systemd --user units and unit files on disk
live ports via ss, live responses via curl on 127.0.0.1:5175
pyproject.toml, uv.lock
frontend/src/*ApiClient.ts, playwright.config
docs/operations/558_GATE100_BACKGROUND_WORKER_RUNTIME_SURVEY.md
docs/operations/561_GATE100_PRODUCTION_READINESS_DELTA.md
```

Both Gate 100 documents exist under the names the brief gives.
