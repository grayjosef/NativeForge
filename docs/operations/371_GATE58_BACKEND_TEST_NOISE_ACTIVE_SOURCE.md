# 371 — Gate 58E: Backend test noise (active-source activation suites)

Status: **documented, deliberately not fixed.** The safe correction is not
contained enough to do inside Gate 58.

## Exact known failure count

Broad scoped selection
`-k 'tenant or rbac or role or authority or opportunity or discovery or source or scraping or sc or claim or demo'`:

```text
selected:  5,091 tests
HEAD   9e38706:  38 failed, 5,053 passed, 11 skipped
parent 0868cc8:  38 failed, 5,014 passed, 11 skipped
```

## Parent comparison method

1. `git worktree add /tmp/nf-parent 0868cc8` — parent checked out in isolation.
2. `PYTHONPATH=/tmp/nf-parent/src` and **verified** the import actually resolved
   to the worktree (`/tmp/nf-parent/src/nativeforge/__init__.py`), not to the
   editable install pointing at the main tree. Without that check the comparison
   is meaningless.
3. Identical `-k` expression on both, full output captured to file — **not**
   piped through `tail`, which truncated an earlier attempt to 11 of 38 lines
   and caused a miscount.
4. `comm` diff of the sorted failure-ID sets.
5. Worktree removed and pruned.

Result:

```text
FAILURES ONLY AT HEAD (introduced):  0
FAILURES ONLY AT PARENT (fixed):     0
IDENTICAL SETS?                      YES — byte-identical
passed delta:                        +39 (exactly the new Gate 51-57 tests)
```

All 38 are **pre-existing**, confined to `test_sprint47`–`test_sprint65`
active-source activation files plus `test_sprint20_discovery_engine_closeout`.

## Why this matters

Thirty-eight standing failures is enough noise to hide a real regression — and
it already did. Working from the earlier truncated output, this campaign
initially reported "7 pre-existing failures," a figure that came from a
different, narrower `-k` expression in an earlier sprint. The number was wrong
for two compounding reasons: a truncated capture and an assumption that two
selections were comparable.

A suite with 38 permanently red tests trains everyone to skim the summary line.
The next genuine regression will land inside that noise.

## Root cause of the largest cluster

Migrations have advanced past what these tests assert. Current
`alembic/versions/`:

```text
0019_nf_active_opportunity_sources.py
0020_nf_activation_state.py
0021_nf_opportunity_sources_seed_id.py
0022_nf_evidence_intake_records.py
```

At least six test modules assert **no revision beyond 0019**:
`test_sprint20_discovery_engine_closeout`,
`test_sprint46_active_source_migration_file_generation`,
`test_sprint47_active_source_local_migration_verification`,
`test_sprint48_active_source_runtime_migration_apply_plan`,
`test_sprint49_active_source_runtime_migration_approval_intake`,
`test_sprint50_active_source_runtime_migration_readiness_gate`
(plus `test_sprint64`/`test_sprint65` variants such as
`test_28_no_new_alembic_revision_beyond_0019`).

Those assertions were written as a freeze guard for the active-source
activation campaign — "this gate must not add a migration." Revisions 0020-0022
were then added by *other* work, so the guard now fires on unrelated change.

## Recommendation

Not a one-line fix, which is why it is documented rather than patched here.
Someone needs to decide what the guard was protecting:

1. **If the intent was "this campaign adds no migration"** — rewrite the
   assertion to pin the revision set the campaign owns, or to assert no *new*
   revision relative to a recorded baseline, rather than a hardcoded `0019`
   ceiling that any later work trips.
2. **If the activation campaign is closed** — retire or `xfail` the suites with
   a reason string, so the signal is "known closed" rather than "red."
3. **Either way, isolate them** — a marker (e.g. `-m active_source_freeze`) so
   the default scoped run is green and the freeze suites are opted into
   deliberately.

Option 1 is correct if activation is still live work; option 2 if it is not.
That is a product call about whether the active-source activation campaign is
still being pursued, and it should not be guessed at inside an enforcement gate.

## Not done here

No test was modified. No `xfail` was added. No migration was touched. Gate 58
changed 14 API modules, added two modules and one test file, and introduced
**zero** new failures.
