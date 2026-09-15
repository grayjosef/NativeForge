# 806 — Gate 154: the readiness delta

## What changed

```text
operational_health_ready        (new lane)  ->  true, controlled_dev_demo
```

Four lanes were added to the beta onboarding cockpit —
`tenant_digest_persistence`, `audit_replay`, `operational_backup_restore` and
`operational_health` — each `readiness_only` until a verifier supplies proof.

## What did not change

```text
production_monitoring           false  ->  false   (no branch computes it)
external_monitoring             false  ->  false
alerting                        false  ->  false
production_backup_ready         false  ->  false   (Gate 61/65, still SKIP)
customer_auth_live              false  ->  false
verified_operational_binding    false  ->  false
consent_boundary_ready          false  ->  false
customer_beta_scope_approved    false  ->  false
source_monitoring_live          false  ->  false
email_delivery                  false  ->  false
object_store_configured         false  ->  false
controlled_customer_pilot       not activated, no mechanism created
production_rollout              NO_GO
tenant_digest_persistence_live  true   ->  true    (Gate 151)
audit_replay_ready              true   ->  true    (Gate 152)
operational_backup_restore_ready true  ->  true    (Gate 153)
```

No migration. Alembic head stays at **0042**. No customer data was written, no
real organization was read, no live source was called, no collector was
activated, no email was sent and no object store was contacted.

## What can now be observed that could not be

```text
backend stale code      by comparing process start time to when the code last
                        changed. The surface that CLAIMED to answer this -
                        /backend/health's git_sha - measures the repository at
                        request time and always agrees with HEAD.

stale build stamp       by comparing the stamped sha to HEAD. --strict-public
                        only checks that the tag exists.

migration drift         by comparing the repository's highest revision to the
                        database's current one. Nothing compared them before.

verifier expectations   28 verifiers, each with the result it is SUPPOSED to
                        return, the lane it serves and what must pass first.

next safe action        derived from the model, replacing a module constant
                        that had been stale since Gate 145.
```

## What still cannot be observed

```text
which commit the process actually loaded   nothing records it. Freshness is
                                           inferred from time, and "probably
                                           current" is the honest answer.
how old a verifier result is               nothing records when one ran
uptime, SLO, error budget                  nothing is recorded over time
anything from outside this host            nothing leaves it
```

## What remains manual

Restarting services, running verifiers, and noticing that a result is hours old.
The registry now records the order; running them is still a person's job.

## This is not production monitoring

No APM, no alerting, no external monitor, no uptime record, no error budget, no
incident rota. Nothing sends mail, SMS or a page, and no service in this gate
executes a shell.

The repository already contains a function that will answer
`production_monitoring: true` on a caller's say-so —
`gate32_observability_service.resolve_observability`, whose every input is a
keyword argument with a default. Gate 154 does not extend it, does not import
it, and does not call it. A test parses the AST of all five Gate 154 modules to
prove it, and the verifier does the same.

## How Gate 61/65 differs from Gate 153, and why Gate 154 keeps them apart

```text
backup_restore              production_backup_ready              expects SKIP
  pg_dump, PITR, an executed provider restore. Needs a managed PostgreSQL
  instance, which does not exist. SKIP is the correct answer.

backup_restore_readiness    operational_backup_restore_ready     expects PASS
  Export controlled dev/demo state, restore it into an isolated database,
  re-run the Gate 152 replay. Runs today.
```

They sort next to each other and answer opposite questions. The registry records
the pair in `BACKUP_LANE_SEPARATION` and three invariants fail if they are
merged, if the production harness stops expecting `SKIP`, or if the two come to
share a lane. Gate 154 ran both: `SKIP` and `PASS`, unchanged.

## Three defects found and fixed during this gate

1. **Lanes false by design were counted as health blockers.** The model's own
   invariant caught it — `operational_health_ready` came back true beside three
   blockers, which is `ready_alongside_blockers`. Those three were lanes the
   campaign's rules require to stay false. Counting them as faults would keep
   this lane shut forever while sending an operator to fix nothing.
   `blockers` and `awaiting_human_decision` are now separate.

2. **The verdict ignored a blocker it had already named.**
   `operational_health_ready` weighed only REQUIRED components, so an
   unexpected result from the Gate 61/65 harness was listed in `blockers` and
   then had no effect. `required` governs how much UNKNOWN is tolerated; it
   never decided which faults count. Any blocker now closes the lane.

3. **The verifier's own shell scan matched a word instead of a meaning.** It
   searched each service file for `subprocess` and flagged three modules whose
   docstrings say they start no subprocess — the substring-versus-meaning
   defect, committed by the tool built to prove those modules clean. It parses
   the AST now, and a control file (`backend_health_readiness_service`, which
   genuinely imports subprocess) proves the scan can still find a real one.

Plus one design correction: **a dirty tree is not automatically unknown**. A
first draft closed the lane on any uncommitted change, which is every machine
anybody is working on. An edit made before the process started is an edit the
process loaded.

## Unchanged campaign blockers

Every customer-beta blocker from Gates 146–150 is still human and still
outstanding: a real customer organization must exist, a named customer must sign
in as themselves, an operational binding approval must be signed, and a
controlled pilot activation must be granted. Gate 154 touched none of them.

## Files

```text
src/nativeforge/services/operational_health_model_service.py
src/nativeforge/services/runbook_health_service.py
src/nativeforge/services/readiness_verifier_registry_service.py
src/nativeforge/services/operational_health_artifact_gate154_service.py
src/nativeforge/services/beta_onboarding_readiness_summary_service.py  (extended)
src/nativeforge/api/operational_health_routes.py
scripts/verify_nativeforge_operational_health_runbook.sh
tests/test_gate154_operational_health_runbook.py
artifacts/operational_health_gate154/  (8 files)
docs/operations/802..806
```

## Next

Gate 155 — durability reassessment, closing the 151–155 block.
