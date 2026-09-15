# 804 — Gate 154: the readiness verifier registry

28 verifiers: the 27 recurring scripts on disk, plus Gate 154's own.

`src/nativeforge/services/readiness_verifier_registry_service.py`

## Why a registry, and why it runs nothing

Before this gate nothing enumerated the verifiers. There was no machine-readable
statement of which lane a verifier serves, whether it blocks, what result it is
*expected* to return, or what must pass before it can run. An operator learned
the dependency order by running things and reading failures.

The registry describes. It never executes. A registry that ran its own contents
would turn a health read into a forty-minute test suite and a route into a
remote code execution surface, and an invariant fails if it ever claims to have
executed anything.

## Two result vocabularies, and why conflating them breaks it forever

```text
PASS / BLOCKED       a readiness lane. BLOCKED names what stops it.       20
PASS / FAIL          a stack or repository check. FAIL is a defect.        5
PASS / FAIL / SKIP   needs infrastructure that does not exist yet.         2
```

Every entry carries `expected_result`, and the health model reads a result
against **that**, not against a universal `PASS`.

This matters most for the two that expect `SKIP`:

```text
backup_restore    Gate 61/65   needs a managed PostgreSQL instance
postgres_rls      Gate 64      needs a managed PostgreSQL instance
```

A `SKIP` from either is the correct answer. A registry that expected `PASS` from
everything would report the production backup harness as broken forever, and an
operator would learn to ignore it — which is how a real failure gets missed.

The verifier proves both directions: an expected `SKIP` does not close the lane,
and an unexpected `PASS` from the production harness does.

## The two backup harnesses stay separate

They sort next to each other and answer opposite questions, which is exactly how
a reader conflates them.

```text
backup_restore              production_backup_ready              SKIP
  Gate 61/65. The INFRASTRUCTURE path: can a provider dump and restore a
  database? pg_dump, PITR, an executed restore. Cannot run without a managed
  instance.

backup_restore_readiness    operational_backup_restore_ready     PASS
  Gate 153. The DATA path: can this system export its own controlled dev/demo
  state, load it into an isolated database, and still pass the Gate 152 replay?
  Runs today, with no provider.
```

`BACKUP_LANE_SEPARATION` records the pair explicitly, and three invariants fail
if they are ever merged, if the production harness stops expecting `SKIP`, or if
the two come to share a lane. Gate 153 built the second and did not move the
first; Gate 154 does not move it either.

## What each entry carries

```text
verifier            the name, without the verify_nativeforge_ prefix
script              the path, which a test asserts exists
lane                the readiness lane it serves
kind                readiness_lane | stack_or_deployment |
                    repository_hygiene | production_infrastructure
gate                the gate that built it
blocking            whether a failure should stop the battery
expected_result     PASS or SKIP
controlled_dev_demo_only / production
depends_on          verifiers that must pass first
note                what a reader needs to know that the name does not say
```

## The dependency chain the registry records

```text
demo_live_stack
  └─ demo_deployment (--strict-public)

customer_persistence_live
  └─ awarded_operational_tracking

tenant_digest_operational
  ├─ tenant_digest_persistence            (151)
  │    └─ audit_replay_readiness          (152)
  │         └─ backup_restore_readiness   (153)
  │              └─ operational_health_runbook (154)
  └─ beta_onboarding_cockpit
       └─ controlled_beta_readiness
            └─ customer_beta_reassessment
```

A verifier often fails because one it depends on failed first. The runbook says
so when it emits the "run that verifier alone" action.

## A note the registry carries that the script name does not

`demo_deployment --strict-public` checks that the build stamp **tag exists**. It
never compares the stamped sha to HEAD, so a build from an older commit passes
every check while serving old JavaScript. That is recorded on the entry, and the
Gate 154 health model is what actually compares the sha.
