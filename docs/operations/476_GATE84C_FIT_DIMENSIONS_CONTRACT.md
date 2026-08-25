# 476 — Gate 84C-B: Fit dimension vocabulary contract

`src/nativeforge/services/eligibility_fit_assessment_dimension_vocabulary_service.py`

## The dimensions

```text
eligibility_fit
recognition_tier_fit
relevance_fit
geography_fit
program_fit
capacity_fit
```

Six, not five. `recognition_tier_fit` was added by commit `526f9ce`, the
recognition-tier eligibility gate, and it is the most load-bearing of the six
for this product: it is where federally recognized and state-recognized applicants
stop being interchangeable.

## What changed in the test

Old:

```python
def test_five_fit_dimensions() -> None:
    assert len(FIT_DIMENSIONS) == 5
    assert DIMENSION_ELIGIBILITY_FIT in FIT_DIMENSIONS
    assert DIMENSION_RELEVANCE_FIT in FIT_DIMENSIONS
```

New:

```python
def test_fit_dimensions_are_the_declared_set() -> None:
    assert FIT_DIMENSIONS == (
        DIMENSION_ELIGIBILITY_FIT,
        DIMENSION_RECOGNITION_TIER_FIT,
        DIMENSION_RELEVANCE_FIT,
        DIMENSION_GEOGRAPHY_FIT,
        DIMENSION_PROGRAM_FIT,
        DIMENSION_CAPACITY_FIT,
    )
    assert len(set(FIT_DIMENSIONS)) == len(FIT_DIMENSIONS)
```

Plus `test_recognition_tier_fit_is_a_dimension`, which states outright why that
member matters.

## Why this is stronger, not weaker

The gate's instruction was not to weaken this to `>= 5` without checking names.
An exact tuple is the strongest available form:

| Change | old `len == 5` | new exact tuple |
| --- | --- | --- |
| a dimension removed | caught | caught |
| a dimension renamed | **missed** | caught |
| a dimension reordered | **missed** | caught |
| an unreviewed dimension added | caught | caught |
| two dimensions swapped for two others | **missed** | caught |
| a duplicate entry | **missed** | caught |

The old assertion would have passed on a rename of `eligibility_fit`, which is
exactly the kind of silent vocabulary drift the campaign has been fighting since
Gate 79B.

## Product behaviour

**Unchanged.** No dimension was added, removed or renamed by this gate. The
vocabulary service was not edited at all — only the test that describes it.

## Why it went unnoticed

The recurring gate `-k` had no keyword reaching this file. It has one now
(`fit_dimension`), enforced by
`scripts/verify_nativeforge_test_selection_coverage.sh`.
