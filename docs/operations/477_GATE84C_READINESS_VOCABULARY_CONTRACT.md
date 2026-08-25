# 477 — Gate 84C-C: Readiness vocabulary contract

`src/nativeforge/services/matching_readiness_readiness_label_vocabulary_service.py`

## The labels

```text
application_ready                  proceed
ready_with_review                  proceed
not_ready_missing_documents        hold
not_ready_deadline_risk            hold
not_ready_eligibility_uncertain    hold
not_ready_capacity_gap             hold
blocked                            hold
```

Two labels let a pursuit proceed. The other five hold it, each naming a
different reason.

## What changed in the test

Old:

```python
assert result["readiness_label"] in {READINESS_BLOCKED,
                                     READINESS_NOT_READY_ELIGIBILITY_UNCERTAIN}
```

The incomplete-profile fixture returns `not_ready_missing_documents`. That is a
*better* answer than either of the two the test allowed: the profile is missing
documents, which is a specific, actionable reason, rather than a generic block
or an eligibility question the evaluator was not actually raising.

New:

```python
label = result["readiness_label"]
assert label == READINESS_NOT_READY_MISSING_DOCUMENTS
assert label in READINESS_LABELS
assert label not in PROCEED_LABELS
assert result["final_eligibility"] is False
```

Plus `test_added_readiness_labels_cannot_bypass_blocking`, asserting that the
proceed set is a subset of the vocabulary and that `blocked`,
`not_ready_eligibility_uncertain` and `not_ready_missing_documents` are all
outside it.

## Why this is tighter, not looser

The instruction was explicitly not to loosen this to "any not_ready". It is not
loosened — it is pinned to one exact label, which is narrower than the
two-element set it replaces.

What was *added* is the property whose absence let this rot: nothing checked
what a newly added label was allowed to mean. A future
`not_ready_something_else` that accidentally landed in the proceed set would now
fail `test_added_readiness_labels_cannot_bypass_blocking`, whereas before it
would have silently allowed a pursuit to proceed.

`not_ready_missing_documents` is not removed, and no label was renamed.

## Product behaviour

**Unchanged.** The evaluator and the vocabulary service were not edited. Only
the test that describes them.

## Why it went unnoticed

No keyword in the recurring gate `-k` reached this file. `readiness` is now in
the expression and guarded by
`scripts/verify_nativeforge_test_selection_coverage.sh`.
