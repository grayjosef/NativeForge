# 805 — Gate 154: the failure modes, and what to do about each

Ten modes. Each is exercised against the model with synthetic inputs by
`scripts/verify_nativeforge_operational_health_runbook.sh`, so a detector that
stops detecting fails the verifier rather than going quiet.

A healthy synthetic baseline is asserted too: a detector that never passes is
not a detector.

---

## 1. Stale frontend stamp

```text
state      frontend_stamp_is_older_than_head
status     degraded — the preview serves, it serves the wrong commit
caught by  Gate 154 health model
NOT caught by --strict-public
action     ./scripts/build_frontend_stamped.sh
```

`--strict-public` checks that the stamp meta tag **exists** and that
`build-manifest.json` **exists**. It never compares the sha. A build from three
commits ago passes every check.

## 2. Unstamped build

```text
state      frontend_stamp_is_absent_or_unstamped
status     blocked
caught by  --strict-public, as identity_meta_present
action     ./scripts/build_frontend_stamped.sh
```

A plain `npm run build` overwrites `dist/index.html` and removes the stamp.
This half **is** detected today. The stamped build refuses a dirty tree, so
commit first — which is why the post-commit sequence rebuilds.

## 3. Backend stale code

```text
state      backend_started_before_head_was_committed
status     blocked
caught by  Gate 154 health model, from process start time vs HEAD commit time
NOT caught by /backend/health
action     systemctl --user restart nativeforge-backend.service
```

`/backend/health` reports a `git_sha`, and it cannot answer this. The route
detects the git identity **at request time** from the working tree, so it
reports today's HEAD regardless of what the process loaded. Proved by editing a
tracked file and watching `source_dirty` flip with no restart.

Nothing records a process-scoped commit, which is why Gate 147 had to add a
human carry-forward — there was nothing to check.

## 4. Tracked code edited after the process started

```text
state      tracked_code_changed_after_the_process_started
status     blocked
action     systemctl --user restart nativeforge-backend.service
```

The development-time half of mode 3, and the common one: the tree is dirty most
of the time on a machine somebody is working on. What matters is whether the
newest edit predates the process.

An edit **older** than the process start is code the process loaded — that is
`operational` with a `running_uncommitted_code` caveat, not a fault. A first
draft called any dirty tree `unknown` and closed the lane on every working
machine.

## 5. Migration not applied

```text
state      database_is_behind_the_repository_head
status     blocked
caught by  Gate 154 health model
caught by before this gate  nothing
action     alembic upgrade head
```

Gate 151 hit this with the database at 0041 and the repository at 0042, and
found it by hand. Only two scripts read `alembic_version` and both do it for
their own purposes; neither asked it as a health question.

## 6. Migration ahead of the repository

```text
state      database_is_ahead_of_the_repository_head
status     blocked
action     HUMAN_APPROVAL_REQUIRED — no command is emitted
```

The database has a revision this checkout does not contain. Downgrading destroys
data, and which direction is correct depends on why the branches differ. A
person decides, and the runbook prints no command.

## 7. A service unit is down

```text
states     backend_service_not_active
           preview_service_not_active
           tunnel_service_not_active
action     systemctl --user restart <unit>.service
```

Worth recording: during Gate 153 a backend was started by hand on :8000 while
systemd already owned the port. The unit won, the manual process died, and
nothing reported the collision. **The supported restart is `systemctl --user
restart`**, not a manual uvicorn.

## 8. A prior verifier failed

```text
state      verifier_result_unexpected:<name>
action     bash scripts/verify_nativeforge_<name>.sh
```

Read against the registry's `expected_result` for that verifier, not against a
universal `PASS`. A `SKIP` from the Gate 61/65 production backup harness is
correct; a `SKIP` from a readiness verifier would be a finding.

A verifier often fails because one it depends on failed first — the registry
records the order, and doc 804 draws the chain.

## 9. Fixture residue

```text
state      fixture_residue_present
caught by  verify_nativeforge_fixture_cleanliness.sh
```

The readiness verifiers write fixture rows into the dev database and do not
always remove them. Live counts move between runs. Measured across two Gate 153
verifier runs an hour apart:

```text
exported rows   6580  ->  6842
legacy gaps       93  ->    97
```

Neither is drift in a lane — the two sides of the restore agreed in both runs.
It does mean **a live count is not a fixed fact**, and nothing committed should
pin one. Gate 153 pinned a row count in a document and it went stale within the
hour.

## 10. Legacy evidence gaps

```text
state      legacy_evidence_gaps_present
action     none. They are REPORTED, never backfilled.
```

Delivery intents whose digest predates persistence. Gate 152 counts them, Gate
153 preserves them across a restore, and a **fall** in the count fails that
lane: producing a digest for an intent that never had one is fabricating
evidence.

The runbook carries them as a finding with `must_not_be_backfilled: true`, and
an invariant fails if that flag is ever dropped.

---

## Not a failure mode: a lane waiting on a person

```text
customer_auth_live              a real person must sign in as themselves
verified_operational_binding    an approval must be signed
consent_boundary_ready          the customer organization must consent
customer_beta_scope_approved    an approver must approve the scope
source_monitoring_live          activating a collector contacts a live source
email_delivery                  configuring a provider sends mail
object_store_configured         document bytes have nowhere to go, deliberately
controlled_customer_pilot       no activation mechanism exists
production_rollout              not approved
production_backup_ready         procurement must provide a managed instance
```

These are `awaiting_human_decision`, not `blockers`. Each names who decides. An
operator cannot clear any of them by running anything, and the runbook emits no
command for any of them.
