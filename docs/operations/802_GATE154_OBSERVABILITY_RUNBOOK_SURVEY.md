# 802 — Gate 154: what this system can and cannot see about itself

Read-only survey. One reversible experiment, described below and reverted.

## What already exists, and what kind of thing each one is

```text
gate32_observability_service          DECLARATION-DRIVEN demo model
gate33_healthcheck_service            DECLARATION-DRIVEN demo model
gate33_runbook_service                DECLARATION-DRIVEN demo model
backend_health_readiness_service      REAL measurement (Gate 101C)
customer_auth_activation_runbook_svc  REAL, generated from measurements (121D)
beta_onboarding_readiness_summary     REAL per-lane, static next action (144B)
code_health_inventory_service         REAL, repo file counts
```

The split matters, and Gate 65 already drew it once: its module says it
"exists alongside the Block 73/77 demo services and deliberately does not
extend them", because those "will promote restore status on any non-empty
`restore_evidence_ref` string — the string is never opened."

The same is true of the observability trio.

### `resolve_observability` will claim production monitoring if asked

```python
observability_ready = bool(healthcheck_ready and not missing)
production_monitoring = bool(
    observability_ready and default_status == "alert_ready" and not failures
)
```

Every input is a keyword argument with a default. A caller passing
`healthcheck_ready=True, support_owner_assigned=True,
incident_escalation_ready=True, default_status="alert_ready"` gets
`production_monitoring: true` out, having measured nothing.

`gate33_runbook_service.resolve_runbooks_and_checklist` is the same shape: it
returns a hardcoded dict of six `True` values and a checklist whose evidence
refs are `nf://gate33/...` strings that point at nothing.

**Gate 154 must not extend these, must not call them, and must be unable to
produce `production_monitoring: true` by any path.**

## The three code-identity surfaces, and the fact that nothing compares them

```text
repo HEAD                      git rev-parse HEAD
backend  /backend/health       "git_sha": "e75eb4f4..."
preview  /version              "git_sha": "e75eb4f4..."
         dist/index.html       <meta name="nativeforge-build-sha" content="e75eb4f4...">
```

All four agree right now. Nothing in the repository compares them, so when they
disagree nobody is told.

### The surface that claims to detect stale code does not detect it

`detect_git_identity` is documented as "The commit this process is running."
It is not. `build_backend_health` is called by the route with no `git_sha`
injected, so it shells out to `git rev-parse HEAD` **at request time**, in the
working tree. A process that started an hour and three commits ago reports
today's HEAD.

Measured, rather than argued — a tracked file was edited and restored, with no
restart in between:

```text
before        source_dirty=False   tree_dirty=False
after edit    source_dirty=True    tree_dirty=True     <- no restart happened
after revert  source_dirty=False   tree_dirty=False
```

The value tracks the repository, not the process. So:

**Backend stale-code is not observable from the surface built to observe it.**

Nothing else records a process-scoped commit either. `record_startup` captures
a phase, a sequence number and four false capability flags — no identity. This
is why Gate 147 had to add a human carry-forward ("restart the backend onto
current code before the verifier battery"): there was nothing to check.

What *is* derivable without adding a capture: the process start time against
HEAD's commit time. Started before HEAD was committed ⇒ definitely stale.
Started after, with a clean tree ⇒ probably current, and *probably* is the
honest word, because an uncommitted edit postdates any commit.

## Stale stamp: one half detected, the other half not

```text
plain `npm run build`      clobbers dist/index.html, meta tag disappears
                           -> strict-public FAILS identity_meta_present
                           -> DETECTED

stamped build at an        meta tag present, build-manifest.json present,
older commit               sha simply older than HEAD
                           -> strict-public PASSES
                           -> NOT DETECTED
```

`verify_nativeforge_demo_deployment.sh --strict-public` checks that the meta tag
*exists* and that the manifest *exists*. It never compares the stamped sha to
anything. An operator who stamped three commits ago is serving old JavaScript
and every check is green.

## Migration drift: not detected anywhere

Only two scripts read `alembic_version`, and both do it for their own purposes:

```text
scripts/verify_nativeforge_backup_restore.sh            Gate 61/65
scripts/verify_nativeforge_backup_restore_readiness.sh  Gate 153
```

Neither compares the repository's highest migration to the dev database's
current revision as a health question. Right now both are `0042`, so nothing is
wrong — and nothing would have said so if they differed. Gate 151 hit exactly
this: the dev database sat at 0041 while the repo was at 0042, and it was found
by hand.

## The verifiers: 27 of them, and no registry

```text
BLOCKED / PASS      20   readiness lanes (Gates 138-153 pattern)
FAIL / PASS          5   stack, deployment, determinism, fixtures, coverage
FAIL / PASS / SKIP   2   backup_restore (Gate 61/65), postgres_rls
```

Nothing enumerates them. There is no machine-readable statement of which lane a
verifier supports, whether it blocks, what result it is *expected* to return, or
what must pass before it can run. An operator learns the dependency order by
running things and reading failures.

The two vocabularies matter: a `SKIP` from Gate 61/65 is the correct and
expected answer, while a `SKIP` from a readiness verifier would be a finding.
A registry that treated all 27 the same would report the production backup
harness as a problem forever.

## The static next action

`beta_onboarding_readiness_summary_service.NEXT_SAFE_ACTION` is a module
constant:

```python
NEXT_SAFE_ACTION = {"action": "finish_the_controlled_beta_readiness_matrix", ...}
```

That was true at Gate 144. Gates 145 through 153 have happened since; the
matrix was finished at Gate 145. The cockpit still says to go finish it. A
constant cannot go stale loudly, which is the point: nothing failed.

## Service state

```text
nativeforge-backend.service         active
nativeforge-demo-preview.service    active
nativeforge-mayhem-tunnel.service   active
```

Machine-readable, via `systemctl --user is-active` — a shell call, from outside
the application. Nothing inside the app knows whether its sibling units are up,
and Gate 154 must not teach it to shell out to find out.

Worth recording: during Gate 153 a backend was started by hand on :8000 while
systemd already owned the port. The unit won, the manual process died, and
nothing reported the collision. **The supported restart is
`systemctl --user restart nativeforge-backend.service`**, not a manual uvicorn.

## Fixture residue and moving counts

Running the readiness verifiers writes fixture rows into the dev database and
does not always remove them. Measured across two Gate 153 verifier runs an hour
apart:

```text
exported rows   6580  ->  6842
legacy gaps       93  ->    97
```

Neither is a defect in the lane — the two sides of the restore agreed in both
runs — but it means **a live count is not a fixed fact**, and any health surface
that pins one will go stale. Counts belong in a verifier that measures them, not
in a committed artifact.

## Answers to the survey questions

```text
what health is observable today
  process liveness (systemctl, curl), repo HEAD, stamp sha, backend runtime
  mode, per-lane readiness via each lane's own service, and 27 verifiers that
  each answer one question when run by hand

what is NOT observable today
  backend stale-code, stale stamp sha, migration drift, verifier dependency
  order, whether a verifier result is current or hours old, and what to do next

is service state machine-readable?      yes, from outside the app only
is lane state machine-readable?         yes, per lane, via each lane's service
is verifier state machine-readable?     no. there is no registry
stale-code / stale-stamp / drift?       no. none of the three is detected
is next safe action machine-readable?   a stale constant, not derived
what remains manual                     restarting services, running verifiers
                                        in the right order, noticing staleness
```

## What must not be claimed

```text
production monitoring      no. no APM, no alerting, no external monitor, and
                           the one function that can emit the claim takes it
                           as an argument
alerting                   no. nothing sends mail, SMS or a page
external monitoring        no. nothing leaves this host
uptime / SLO / error budget no. nothing is recorded over time
incident response          no. there is a document, not a rota
```

Gate 154 builds a health MODEL, a runbook health reading, and a verifier
REGISTRY, for `controlled_dev_demo`. It adds no monitoring, contacts nothing,
and executes no shell command from a service.
