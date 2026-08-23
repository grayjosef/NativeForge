# 393 — Gate 63A: Active-source failure cluster baseline

## Measurement method

The reliable "before" figure is the one measured repeatedly across Gates 60–62
and verified **byte-identical** between commits by diffing failure-ID sets:

```text
scoped selection (-k 'storage or postgres or rls or membership or identity or
oidc or auth or token or tenant or rbac or role or authority or opportunity or
discovery or source or scraping or sc or claim or demo')

38 failed, ~5200 passed, 11 skipped
```

Running the implicated files **directly** surfaces 40 failures, because that file
set includes two tests the `-k` expression does not select
(`test_recognition_requirement_coverage_expansion::test_unknown_count_drops_ac1`
and
`test_sprint197_eligibility_fit_assessment_dimension_vocabulary::test_five_fit_dimensions`).
Those two are unrelated to migrations and are **out of scope for this gate** —
noted so the numbers reconcile rather than looking inconsistent.

## Files involved

| File | Failing tests |
| --- | --- |
| `test_sprint20_discovery_engine_closeout` | 1 |
| `test_sprint47_active_source_local_migration_verification` | 3 |
| `test_sprint53_..._post_apply_verification` | 1 |
| `test_sprint54` … `test_sprint61` (8 files) | 1 each |
| `test_sprint62_runtime_active_source_creation_execution_evidence` | 7 |
| `test_sprint64_active_source_activation_readiness_gate` | 8 |
| `test_sprint64_post_runtime_active_source_verification` | 9 |
| `test_sprint65_active_source_activation_review_packet` | 1 |

32 test files in total reference `0019`; only these fail.

## The two failure signatures

### Signature 1 — freeze guard, 13 tests

```python
def test_no_new_alembic_revision_beyond_0019() -> None:
    assert not any(p.name.startswith("0020_") for p in ALEMBIC_VERSIONS.glob("*.py"))
```

Asserts that no `0020_*` migration file exists. Revisions **0020–0022** were
added by unrelated M7/M8 work long before this campaign, and **0023–0027** by the
owner-approved Gate 62 storage path. The assertion is permanently false for
reasons the active-source campaign does not control.

Variants: `test_no_new_alembic_revision_file_added_for_sprint_53_chain`,
`test_28_no_new_alembic_revision_beyond_0019`.

### Signature 2 — revision-gated behaviour, 24 tests

**This is the finding that changed the plan.** These are *not* wrong
expectations. Diagnosed directly:

```text
assert pkt["readiness_decision"] == READINESS_EXECUTED_RUNTIME
AssertionError: assert 'blocked_runtime_revision_mismatch' == 'executed_runtime_source_row_created'
```

The active-source **services** — not the tests — pin the revision:

```python
# src/nativeforge/services/active_source_creation_execution_evidence_service.py
TARGET_REVISION_ID = "0019"
...
"runtime_current_revision_is_0019": rev_norm == TARGET_REVISION_ID,
```

Twelve service modules carry a `0019` pin. With the head at `0027`, they return
`blocked_runtime_revision_mismatch` — **which is correct behaviour**. A service
authorised against one migration state is refusing to operate in a different
one. That is a safety gate doing its job.

The consequence is that the happy path these 24 tests assert is **no longer
reachable**. Repointing `TARGET_REVISION_ID` to `0027` would be changing product
behaviour to satisfy a test — forbidden by this gate's rules, and wrong on the
merits: re-authorising a closed campaign against a new schema is an owner
decision, not a test fix.

`test_sprint47`'s three failures are a third shade of the same cause: an
upgrade/downgrade proof that assumes head `0019`, so downgrading from the real
head now removes more than its target table
(`downgrade_only_removed_target_table` is False).

## Whether anything is new after Gate 62

**No.** Gate 62's regression check diffed the failure-ID set against the Gate 60
baseline and found `0` introduced, `0` fixed — byte-identical.

Gate 62's migrations do make the freeze assertions *further* out of date (head
went 0022 → 0027), but they did not cause the failures. Those tests were already
failing when the head was 0022.

Proceed to classification (`394`).
