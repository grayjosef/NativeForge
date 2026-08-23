# 394 — Gate 63B: Failure classification

Every failure classified before any patch. The instruction not to assume all 38
were stale was worth following: **24 of them are a service safety gate working
correctly**, not a stale assertion.

## Summary

| Class | Count | Treatment |
| --- | --- | --- |
| 1. Stale migration-freeze assertion | 13 | marked obsolete, replaced by doctrine test |
| 2. Stale active-source campaign invariant | 0 | — |
| 3. Legitimate current failure | 1 | **fixed properly** (sprint20) |
| 4. Unreachable path of a closed campaign | 24 | marked obsolete with reason |
| 5. Unclear / needs investigation | 0 | — |
| Out of scope (not in `-k` selection) | 2 | left alone, documented |

## Class 1 — stale migration-freeze assertion (13)

`test_no_new_alembic_revision_beyond_0019` in sprint54, 55, 56, 57, 58, 59, 60,
61, 62, 64 (readiness gate), 64 (post-runtime); plus
`test_no_new_alembic_revision_file_added_for_sprint_53_chain` (sprint53) and
`test_28_no_new_alembic_revision_beyond_0019` (sprint65).

**Why obsolete:** they assert a *file* does not exist. Any approved migration
anywhere in the repo breaks them, regardless of whether the active-source
campaign added it. That makes them collateral-damage tests: they fail for work
they were never meant to guard.

**Treatment:** `@pytest.mark.skip` with an explicit reason naming the
replacement. Files kept, all other assertions in them still run.

**Replacement coverage:** `tests/test_gate63_migration_doctrine.py` asserts the
properties the freeze guards were reaching for — one head, a documented head,
unique revision ids — in a form that survives approved schema change.

## Class 3 — legitimate current failure, fixed (1)

`test_sprint20_discovery_engine_closeout::test_alembic_migrations_unique_revisions_and_expected_head`

This one genuinely protects real invariants:

- no duplicate revision ids — **still valuable, kept untouched**
- expected head — **the only stale part**
- discovery-sprint migration files exist — kept

**Treatment:** re-pinned `0019 (head)` → `0027 (head)`, with a comment saying to
update it deliberately when a migration is approved. This is the "preserve the
test, update the expected value" case.

## Class 4 — unreachable path of a closed campaign (24)

`test_sprint47` (3), `test_sprint62` (6 behavioural), `test_sprint64` readiness
gate (7), `test_sprint64` post-runtime (8).

**Why obsolete, and why *not* a product fix:** the services return
`blocked_runtime_revision_mismatch` because `TARGET_REVISION_ID = "0019"` and the
runtime DB is at `0027`. The service is correct. Three options were considered:

1. **Repoint `TARGET_REVISION_ID` to `0027`** — rejected. This gate forbids
   changing product behaviour to satisfy stale tests, and it would silently
   re-authorise a closed campaign against a schema it was never reviewed
   against. The `0019` pin is a safety property, not a bug.
2. **Migrate the test DB to 0019 for these tests** — rejected. It would pin part
   of the suite to a superseded schema and make future migrations progressively
   harder, recreating exactly the problem this gate exists to remove.
3. **Mark obsolete with the reason recorded** — chosen.

**Treatment:** `@pytest.mark.skip` naming the cause
(`blocked_runtime_revision_mismatch`), stating that the service is behaving as
designed, and that re-authorisation is an owner decision.

`test_sprint47`'s three get a distinct reason: their upgrade/downgrade proof
assumes head `0019`, and it is superseded by the real-PostgreSQL proof in
`scripts/verify_nativeforge_rls_isolation.sh` (doc 389), which is a stronger
check than the SQLite up/down proof it replaces.

## Out of scope (2)

`test_recognition_requirement_coverage_expansion::test_unknown_count_drops_ac1`
and
`test_sprint197_eligibility_fit_assessment_dimension_vocabulary::test_five_fit_dimensions`
fail, are unrelated to migrations, and are **not selected** by this gate's `-k`
expression. Left untouched deliberately — fixing unrelated failures under a
migration-cleanup gate would obscure this gate's diff. Worth a separate look.

## What was explicitly not done

- No test file deleted.
- No suite broadly disabled — every skip is on a named function with a reason.
- No product behaviour changed to make a test pass.
- No assertion silently weakened.
