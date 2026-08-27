# 558 — Gate 100A: background worker runtime survey

Verified rather than assumed. The survey found one thing the brief does not
mention, and it changes what the worker decision actually depends on.

## Worker, scheduler, queue and broker packages: none, in three places

```text
package        pyproject.toml   uv.lock   importable
celery                      -         -            -
rq                          -         -            -
apscheduler                 -         -            -
dramatiq                    -         -            -
arq                         -         -            -
huey                        -         -            -
taskiq                      -         -            -
procrastinate               -         -            -
schedule                    -         -            -
croniter                    -         -            -
kombu                       -         -            -
redis                       -         -            -
pika                        -         -            -
nats                        -         -            -
confluent_kafka             -         -            -
boto3                       -         -            -
```

Every row empty. `boto3` is included deliberately: Gate 97 built the S3 body
store against an injected-client Protocol precisely so no SDK dependency was
needed, and this confirms that seam held.

## An ASGI server is already a declared dependency

```text
pyproject.toml:12    "fastapi>=0.115"
pyproject.toml:13    "uvicorn[standard]>=0.32"
```

This is the finding that decides Gate 100B. A worker running inside the
application process needs no new dependency at all — the server that would host
it is already declared and installed. `uv.lock` does not need to change, and it
does not.

## But there is no long-running backend process to host one

This is what the brief does not say, and it is the load-bearing fact:

```text
systemd user units:
  nativeforge-demo-preview.service    Vite preview, 127.0.0.1:5175   running
  nativeforge-mayhem-tunnel.service   Cloudflare tunnel              running
  nativeforge-cloudflared.service     (on disk)

pgrep uvicorn|gunicorn|nativeforge.main   ->  nothing running
```

The two running units serve the **frontend** and a tunnel to it. Neither serves
the API. The backend is started only ephemerally, by smoke and staging scripts
that background it and kill it when they finish:

```text
scripts/m0_demo_up.sh:46                uvicorn nativeforge.main:app --reload
scripts/m8_close_gate_staging_smoke.sh  uvicorn ... &   (3 sites)
scripts/la_scale_federal_staging_verify.sh:37   uvicorn ... &
```

And `src/nativeforge/main.py` has **no lifespan hook, no `on_event`, no startup
or shutdown handler** — there is currently nowhere for an in-process background
task to attach even if a process existed to run it.

```text
main.py:54   def create_app() -> FastAPI
main.py:90   app = create_app()
```

So the production worker question has a prerequisite nobody has written down.
It is not first "which broker" — it is:

```text
1  deploy the backend as a persistent process        <- does not exist today
2  decide in-process vs external worker
3  if external: choose a broker and add the dependency
4  add a periodic trigger
```

Step 1 is a deployment decision with no code in this repository behind it.
Choosing a broker before it would be choosing infrastructure for a service that
is not running anywhere.

## Existing CLI scripts

```text
scripts/*.py    11 (6 executable), including Gate 99E's dry-run queue CLI
scripts/*.sh   137
console_scripts declared in pyproject.toml:  none
```

The convention Gate 99E followed — shebang, `parents[1]` root, `sys.path` insert,
`argparse`, mode 755 — is unchanged, and Gate 100E follows it too.

## Is a dependency needed? No

```text
what an external worker library would give    what Gate 100 needs
----------------------------------------------------------------
a broker and transport                        no - nothing is dispatched
worker process management                     no - nothing runs
retry and backoff                             no - Gate 98C's breaker decides
periodic trigger scheduling                   no - no trigger in this gate
task payload serialisation                    no - values stay in process
```

**`uv.lock` does not change in this gate.** An in-process dry-run worker is a
pure function from a queue of jobs to a result record, and Gate 99 already
proved the queue is a pure function from decisions to jobs.

## Is an in-process dry-run worker sufficient for now? Yes

It is sufficient for what this gate is for: establishing the boundary and
proving nothing crosses it. It is *not* sufficient for monitoring, and the
distinction is the whole subject of doc 560.

A dry-run worker consumes a queue and marks jobs. It does not fetch, does not
call a collector, and does not write a payload — and after Gate 100 it still
cannot, because none of those things exists to be called from it.

## What production worker options remain open

All of them, deliberately.

```text
option                        needs                          dependency
in-process (FastAPI lifespan) a deployed backend process     none
external worker + broker      a broker, a host, a deploy     celery/rq/arq + redis
platform scheduler            a platform (cron, k8s, cloud)  none, or vendor SDK
systemd timer + oneshot CLI   a host, a unit, a timer        none
```

The last two are worth noting because they need no dependency either. A systemd
timer firing Gate 99E's CLI would be a real periodic trigger, and Gate 98E's
`periodic_trigger` detection already scans for `.timer` files in the repository —
so that path is detectable the day somebody checks one in.

Gate 100B records the decision state as `external_worker_required`, which means
*a worker is needed and none is chosen*. That is honest about where things
stand: the requirement is established, the implementation is not, and nothing in
this gate pretends otherwise.

## Inputs surveyed

```text
src/nativeforge/            main.py, services/, api/
scripts/                    *.py and *.sh
pyproject.toml, uv.lock
systemd --user units and unit files on disk
tests/
docs/operations/554_GATE99_SCHEDULER_RUNTIME_SURVEY.md
docs/operations/557_GATE99_SCHEDULER_RUNTIME_READINESS_DELTA.md
```

Both Gate 99 documents exist under the names the brief gives. Nothing in the
input list was missing this time.
