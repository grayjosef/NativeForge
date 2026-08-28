# 569 — Gate 102D/E/F: production readiness delta

## What changed

Gate 101 reported:

```text
backend_runtime_mode          loopback_backend_contract
lifespan_hook_available       false
persistent_backend_live       false
backend unit installed        no
backend unit enabled          no
```

Gate 102 reports:

```text
backend_runtime_mode          loopback_backend_contract  (repository scope)
lifespan_hook_available       true                        <- changed
in_process_scheduler_possible false
persistent_backend_live       false  (repository scope)
backend unit installed        YES    <- operator-approved
backend unit enabled          no     <- operator declined enable
```

One repository fact changed, and one host fact changed. Nothing that was false
about collectors, monitoring or coverage became true.

## The host was changed, with approval, and only partly

The operator was asked before anything touched the host and chose **install and
start, without enable**.

```text
systemctl --user daemon-reload    run
systemctl --user start            run
systemctl --user enable           NOT RUN
```

The service is running now on `127.0.0.1:8000` and **will not come back after a
reboot**. That is the correct default for a loopback development backend nobody
depends on yet, and it keeps the change trivially reversible:

```bash
systemctl --user stop nativeforge-backend.service
rm ~/.config/systemd/user/nativeforge-backend.service
systemctl --user daemon-reload
```

Loopback was confirmed twice: `ss` reports `127.0.0.1:8000`, and a request to
this host's LAN address is refused. A Cloudflare tunnel is running here, so a
`0.0.0.0` bind would have been publicly reachable — a test parses the unit and
asserts `0.0.0.0` appears nowhere, and another asserts the unit is in no
`WantedBy` target directory.

## Repository scope versus host scope

The distinction that shapes every artifact in this gate:

```text
repository scope   the contract, the plan, what this gate did
host scope         a pid, an observation time, a live healthcheck result
```

`persistent_backend_live` in the committed artifacts is **false**, and it means
exactly one thing: *the committed contract carries no process proof.* A real
proof was captured during the run — unit active, PID 81370, healthcheck ok — and
it is in doc 567 and the gate report.

Both are true. They answer different questions, and
`process_proof_captured_during_run` sits beside the flag so neither reads as the
other. Committed artifacts are compared against a fresh generation by test, so a
pid or a timestamp in one would fail that comparison on any other machine, and on
this one minutes later — the same rule Gate 101 applied to `git_sha` and
`database_ready`.

`installed_by_this_gate: true` and `enabled_by_this_gate: false` **are**
committed, because they are constants recording what this run did, not
detections. They stay true afterwards the way a changelog entry stays true.

## A weakening, stated rather than hidden

Gate 98 asserted that `build_scheduler_readiness` took only `repo_root` — that no
caller-supplied argument could turn a missing component into a present one.

Gate 102B needed `process_proof`, and the reason is worth stating: whether a
process is *running* cannot be detected without I/O that would make readiness
differ per machine and per minute, breaking the determinism the artifacts depend
on. Liveness is now the one component established by evidence passed in.

The guarantee is preserved by **validating** that evidence rather than trusting
it. Gate 98's test was rewritten rather than relaxed, and now asserts that a bare
truthy dict, a partial observation, and one that says it saw nothing all leave the
answer false — while a complete observation flips it, so the check is not vacuous.

## What Gate 102 may not change, and did not

```text
background_worker_available   false
production_worker_live        false
ready_to_start_monitoring     false
source_monitoring_live        false
may_fetch_live_now            false   (all 5 Phase 1 sources)
may_schedule_monitor          false   (all 5 Phase 1 sources)
monitors_active               0
collectors_active             0
collector_status              not_active (all 5)
customer_auth_live            false
production_rollout            false
```

Even with the real proof supplied, `in_process_scheduler_possible` becomes true
and **monitoring stays false** — no worker, no trigger, no production payload
store. That is the whole point of keeping the components separate.

Invariants added this gate:

```text
in_process_scheduler_disagrees_with_its_halves     scheduler readiness
persistent_backend_without_a_process_proof         scheduler readiness
in_process_worker_without_a_lifespan_hook          worker decision
lifespan_hook_read_as_a_scheduler                  phase 1 policy
in_process_attach_disagrees_with_its_halves        runtime contract
```

## Two superseded Gate 101 tests

`test_main_has_no_lifespan_hook` asserted the absence Gate 102C removed. It was
inverted rather than deleted, because the detector is what Gate 101 contributed
and it must keep working — it now has to *find* a hook where it previously had to
correctly report none.

`test_this_gate_did_not_install_or_enable_the_unit` checked host state. Gate 102
owns host state now, so the host check moved here and Gate 101's test was narrowed
to what it can still assert: its contract reports no installed unit by default,
because it never inspects the host.

## What remains

```text
- a background worker            gate 100's open decision, still open
- a periodic trigger             a .timer in the repo is detected by gate 98E
- an object store deployment     gate 97's seam
- enable the unit                only if it should survive reboots
```

`uv.lock` and `pyproject.toml` unchanged.

## Production boundary

```text
controlled customer pilot     NO_GO
production rollout            NO_GO
backend runtime contract      AVAILABLE
backend unit installed        YES (operator-approved, this gate)
backend unit enabled          NO  (operator declined; will not survive reboot)
persistent backend            RUNNING on 127.0.0.1:8000, proof captured
                              (not committed - host scope)
lifespan hook                 AVAILABLE, nothing attached
background worker             NOT AVAILABLE
production worker             NOT LIVE
source monitoring live        0
collectors live               0
crawler live                  0
source coverage live          0
raw payload store production  NOT AVAILABLE
login live                    NO
production storage            NO
customer persistence          NO
pen-test passed               NO
65% improvement claimed       NO
```

No collector ran, no URL was fetched, no raw payload was written, no monitoring
started, and no source coverage is claimed. Backend readiness is not customer
auth, and it is not production rollout.
