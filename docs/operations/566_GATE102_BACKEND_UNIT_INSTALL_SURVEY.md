# 566 — Gate 102A: backend unit install survey

Completed before any install action, as the gate requires. Every fact verified
against the host.

## The unit template

```text
deploy/systemd/nativeforge-backend.service   present, mode 644

ExecStart=/home/josefgray/projects/nativeforge/.venv/bin/uvicorn \
          nativeforge.main:app --host 127.0.0.1 --port 8000 --no-access-log
WorkingDirectory=/home/josefgray/projects/nativeforge
```

```text
binds loopback only?      yes - --host 127.0.0.1, no 0.0.0.0 anywhere
command uses uvicorn?     yes, the venv binary
uvicorn binary present?   yes, and executable
working directory valid?  yes, the directory exists
```

## Host state before this gate

```text
unit installed (~/.config/systemd/user/)   NO
unit enabled                               not-found
unit active                                inactive
port 8000                                  free, nothing listening
port 5175                                  Vite preview (node), listening
uvicorn nativeforge process                none
/backend/health                            no response
/backend/readiness                         no response
```

Exactly the state Gate 101 left: a template and no process.

## Exact install commands

```bash
mkdir -p ~/.config/systemd/user
cp deploy/systemd/nativeforge-backend.service \
   ~/.config/systemd/user/nativeforge-backend.service
systemctl --user daemon-reload
systemctl --user start nativeforge-backend.service
sleep 5
systemctl --user status nativeforge-backend.service --no-pager
curl -fsS http://127.0.0.1:8000/backend/health
curl -fsS http://127.0.0.1:8000/backend/readiness
```

To stop and remove it again:

```bash
systemctl --user stop nativeforge-backend.service
rm ~/.config/systemd/user/nativeforge-backend.service
systemctl --user daemon-reload
```

## Operator approval

**Given during the run: install and start, but do not enable.**

The operator was asked before anything touched the host, and chose the
lower-commitment option. So:

```text
systemctl --user enable    NOT RUN
systemctl --user start     run
```

The consequence is deliberate and worth stating plainly: the service runs now and
**will not come back after a reboot**. That is the correct default for a
loopback development backend nobody depends on yet, and it keeps the host change
trivially reversible.

`enabled_by_this_gate` is false in every artifact, and a test asserts the unit is
not in any `WantedBy` target directory.

## Ordering: the lifespan hook goes in before the service starts

Gate 102C adds a FastAPI lifespan hook to `main.py`. The install happens *after*
that edit, so the process that ends up running is one that has the hook — rather
than a process started from older code that would then disagree with the
repository about its own capabilities.

## Why the live proof is not committed

The process proof carries a pid, an observation timestamp, and a healthcheck
result. All three are properties of this host at this moment.

Committed artifacts are compared against a fresh generation by test, so anything
host-specific in them would fail that comparison on any other machine — and would
fail on this one the moment the service stops. The artifacts therefore carry the
**contract, the plan, and one fixed worked example**; the real proof is captured
by `backend_process_proof_service` at call time and reported in the gate report.

This is the same rule Gate 101 applied to `git_sha` and `database_ready`, for the
same reason.

## Inputs surveyed

```text
deploy/systemd/nativeforge-backend.service
src/nativeforge/main.py
src/nativeforge/services/backend_runtime_contract_service.py
scripts/
systemd --user state (installed / enabled / active)
ports 8000 and 5175 via ss, endpoints via curl
tests/
docs/operations/562, 563, 565
```

All three Gate 101 documents exist under the names the brief gives.
