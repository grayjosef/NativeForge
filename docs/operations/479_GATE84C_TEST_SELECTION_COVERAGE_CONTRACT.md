# 479 — Gate 84C-E: Test selection coverage contract

`scripts/verify_nativeforge_test_selection_coverage.sh`
`tests/test_gate84c_test_selection_coverage.py`

## The problem it exists for

Every gate since the campaign began reported a "broad scoped pytest" number as
its regression evidence. That number came from a `-k` keyword expression grown
by accretion — one or two keywords added per gate, for that gate's subject.

Nothing ever checked what the expression did **not** reach.

Gate 84B measured the whole suite for the first time and found six deterministic
failures inside the gap. Every gate report had said `0 failed`, and every one
had also said `full suite claimed?: NO`. Both were true. The distance between
them was never measured.

## What the script measures

```text
check=collected                     total tests the suite collects
check=selected_by_gate_expression   how many the gate -k reaches, and the percentage
check=unselected                    the size of the blind spot
check=critical_selected:<name>      one per known-fragile test
check=selection_breadth             fails if the expression has collapsed below 50%
```

Current numbers:

```text
collected  7172
selected   6498  (90%)
unselected  674
```

## The critical list

Six node ids — every test that has already rotted invisibly once:

```text
test_recognition_requirement_coverage_expansion.py::test_unknown_count_drops_ac1
test_sprint348_nf15_closeout.py::test_nf15_gate_and_closeout
test_sprint197_..._dimension_vocabulary.py::test_fit_dimensions_are_the_declared_set
test_sprint222_..._readiness_evaluator.py::test_incomplete_profile_blocked_readiness
test_sprint4202_gate37_...py::test_busy_preview_port_blocks_serve
test_sprint4202_gate37_...py::test_verifier_fail_when_server_down
```

They are **node ids, not keywords**, so a rename fails the guard rather than
silently dropping coverage — which matters here because two of the six were
renamed by this gate (`test_five_fit_dimensions` and
`test_5175_collision_blocks_serve`), and the list names the new identifiers.

Two checks per entry: the test must still exist, and the expression must reach
it.

## What it does not demand

**Not 100% selection.** 674 tests remain outside the expression. Demanding full
coverage would either force the gate `-k` to become "everything" — at which point
it is a 35-minute full run, which is a legitimate choice but a different one — or
invite the expression to be padded with keywords nobody has thought about.

The guard's claim is narrower and honest: *the tests we know can rot silently
are inside the selection*. The remaining 674 are a known, measured blind spot
rather than an unknown one.

## What this gate had to change to make it pass

The expression was missing `fit_dimension`, `readiness` and `gate37`. Four of
the six critical tests were unreachable by it — which is exactly how they failed
unnoticed. Adding those three keywords moved selection from 6436 to 6498.

The guard failed on first run, which is the correct behaviour for a guard whose
subject was genuinely broken.

## Remaining test-health risk

- **674 unselected tests.** Measured, not eliminated. A failure in one of them
  is still invisible to a scoped gate run.
- **The list is retrospective.** It guards tests that have already failed. A
  seventh test can still rot before anyone notices.
- **The expression lives in two places** — this script and the gate prompts. The
  script is the source of truth; a prompt that drifts from it will select
  differently from what the guard checks.

The durable fix is to run the whole suite per gate. It takes ~35 minutes and was
done for Gates 84B and 84C.
