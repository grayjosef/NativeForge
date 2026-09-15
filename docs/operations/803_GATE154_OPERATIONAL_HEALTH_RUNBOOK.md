# 803 — Gate 154: the operational health runbook

`operational_health_ready` is true for `controlled_dev_demo`.
**Production monitoring is not active and nothing here makes it active.**

## What this is, and what it is not

```text
IS      a health MODEL composed from measured facts, a verifier REGISTRY, and
        a runbook reading that derives the next action from the model

IS NOT  production monitoring, APM, alerting, an external monitor, an uptime
        record, an error budget, or an incident rota
```

Nothing leaves this host. Nothing sends mail, SMS or a page. No service in this
gate executes a shell.

## Running it

```bash
bash scripts/verify_nativeforge_operational_health_runbook.sh
```

It needs the backend on `127.0.0.1:8000`. It reads `systemctl`, `git`, the
alembic versions directory, the database's `alembic_version` row and the built
SPA's stamp tag, composes them into the model, and prints what it found.

## The six required components

```text
backend_service          systemctl --user is-active nativeforge-backend
preview_service          systemctl --user is-active nativeforge-demo-preview
tunnel_service           systemctl --user is-active nativeforge-mayhem-tunnel
migration_head           repository's highest revision vs the database's current
frontend_stamp           the SPA's stamped sha vs HEAD
backend_code_freshness   process start time vs when the code last changed
```

A component nobody supplied is `unknown`, and `unknown` is not a pass: the lane
stays closed while any required component is unknown. Any blocker, required or
not, also closes it.

## The five statuses

```text
operational   it works now, in controlled_dev_demo
degraded      it works, and something about it is wrong or stale
blocked       something specific stops it, and it is named
skipped       it correctly did not run, or a lane is false by design
unknown       nobody has determined it
```

## Blocked is not the same as waiting on a person

```text
blockers                  something is wrong and somebody can act on it
awaiting_human_decision   a lane is false BY DESIGN until a person decides
```

The first draft of this gate put both in `blockers`, and the model's own
invariant caught it: `operational_health_ready` came back true beside three
blockers. Those three were `customer_auth_live`,
`verified_operational_binding` and `controlled_customer_pilot` — lanes the
campaign's rules require to stay false.

Counting a lane that is waiting on an approver as a health fault would have kept
this lane shut forever while sending an operator to fix something that is not
broken. `EXPECTED_FALSE_LANES` names the lanes that are false on purpose; a lane
false and absent from that set is a real blocker, because nobody declared it was
supposed to be false.

## Backend code freshness, and why the obvious method does not work

`/backend/health` reports a `git_sha` and is documented as "the commit this
process is running". It is not. The route calls `build_backend_health` with no
sha injected, so `detect_git_identity` shells out to `git rev-parse HEAD` **at
request time**, in the working tree. A process started an hour and three commits
ago reports today's HEAD.

Measured rather than argued — a tracked file was edited and restored with no
restart in between:

```text
before        source_dirty=False   tree_dirty=False
after edit    source_dirty=True    tree_dirty=True    <- no restart happened
after revert  source_dirty=False   tree_dirty=False
```

So freshness comes from time, not from a sha:

```text
process started BEFORE the HEAD commit        definitely stale
started after, tree clean                     probably current
tree dirty, edits OLDER than the start        operational, with a caveat:
                                              the running code is HEAD plus
                                              those edits, which is a complete
                                              answer
tree dirty, edits NEWER than the start        definitely stale
tree dirty, edit time not supplied            unknown; nobody looked
```

"Probably" is the honest word in the second row: nothing records which commit
the process actually loaded.

A first draft made *any* dirty tree `unknown`, which closed the lane on every
machine anybody was working on. An edit made before the process started is an
edit the process contains.

## The next safe action is derived

`beta_onboarding_readiness_summary_service.NEXT_SAFE_ACTION` is a module
constant reading `finish_the_controlled_beta_readiness_matrix`. That was true at
Gate 144. The matrix was finished at Gate 145, and Gates 146 through 154 have
happened since. Nothing failed, because a constant cannot go stale loudly.

`runbook_health_service` derives every action from a component status. When a
component moves, the action moves with it.

## Commands, and the ones that are deliberately absent

A command is emitted only when it is non-destructive, already part of the
approved runbook, and passes `command_is_secret_safe` — Gate 121D's rule,
imported rather than reimplemented, because two copies of a secret filter is one
copy that falls behind.

Anything destructive, anything that activates a capability, and anything a human
must decide is emitted as `HUMAN_APPROVAL_REQUIRED` **with no command at all**.
A runbook that prints the command beside the words "needs approval" has already
handed it over. An invariant fails if a gated action ever carries one.

## The routes

```text
GET /v1/nf/demo/orgs/{org}/operational-health/summary
GET /v1/nf/demo/orgs/{org}/operational-health/verifier-registry
GET /v1/nf/demo/orgs/{org}/operational-health/runbook
GET /v1/nf/demo/orgs/{org}/operational-health/next-safe-action
```

Authenticated demo organization only. GET only. **No route shells out**, which
is why a route response reports `operational_health_ready: false`: a request
cannot ask `systemctl` or `git`, so those facts stay `unknown` rather than being
assumed, and the response names exactly which ones and points at the verifier.

A health route that ran `systemctl` would be a command execution surface
reachable with a session cookie.
