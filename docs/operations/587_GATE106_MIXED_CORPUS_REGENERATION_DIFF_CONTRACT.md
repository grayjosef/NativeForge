# 587 — Gate 106B: mixed corpus regeneration diff contract

`src/nativeforge/services/mixed_corpus_regeneration_diff_service.py`

Compares the committed manifest against fresh derivation and classifies every
difference. It reads two recorded fixtures and fetches nothing.

## Why a diff needs classification

A fixture regeneration is a bulk overwrite, and the output looks identical in
shape whether or not it is correct. "57 rows written" tells a reviewer nothing.

So every differing field lands in exactly one class:

```text
gate105_tribal_bridge_correction  the canonical Tribal classifier fix landing
preexisting_fixture_drift         a divergence this service can characterise
unexpected                        neither - nobody can say why this changed
unchanged                         identical on both sides
```

## There is no catch-all

`preexisting_fixture_drift` names a divergence the service can actually
characterise — an evidence field going from blank to populated, or an unknown
narrowing to a negative. It is **not** a bucket for "not Gate 105".

An earlier draft of this service ended with `elif row_id not in
GATE105_EXPECTED_ROWS -> preexisting_fixture_drift`. That made `unexpected`
unreachable on every row outside the three, so a genuinely unexplained corpus
change would have been reported as understood drift and waved through. The test
that caught it asserts an arbitrary title change classifies as `unexpected`.

Anything the service cannot name stays `unexpected` and blocks.

## Attribution is per field, not per row

A Gate 105 correction is recognised only on the exact combination:

```text
row      one of the three rows the fix was measured to touch
field    applicant_types_include_tribal
value    False -> True, in that direction
```

Whitelisting the *row* would let any future edit to those three ride in under the
Gate 105 label. Whitelisting the *field* would excuse the reverse transition,
which is a positive removal rather than a correction. Both are tested against
mutations that drop each check.

## fabricated_eligibility_risk is computed, not set

The hazard Gate 106A found: derivation copies a `synopsis` into
`eligibility_text` when the latter is empty. On the one corpus row that records
no NOFO existing, that writes administrative prose into the field the Tribal
classifier and evidence derivation read.

So the risk is derived from what the change would do:

```text
honest_absence_overwritten      an evidence field goes blank -> populated on a
                                row flagged empty_honestly / never_synthesized
unknown_narrowed_to_negative    None -> False, asserting more than the source
```

Either raises the flag. No caller can lower it, and an invariant fails any diff
where fabrication risk coexists with permission to regenerate.

## safe_to_regenerate is derived affirmatively

True only when all the positive conditions hold, never by subtracting known
problems from a permissive default:

```text
every changed field classified as an expected Gate 105 correction
no unexpected changes
no unresolved pre-existing drift
no positives removed
no fabricated eligibility risk
row ids and ordering identical
```

An invariant re-derives it from the measurements and fails a tampered value.
A refusal must name itself in `blocked_reasons`.

The permission path is reachable and tested: a diff containing only the three
expected corrections returns `safe_to_regenerate: True`. Without that test the
refusal would prove nothing, because a function hardcoded to False would pass
every other assertion here.

## Current result

```text
rows_total                        57
rows_changed                       4
fields_changed                     5
gate105_tribal_bridge_correction   3
preexisting_fixture_drift          2
unexpected                         0
positives_added                    3
positives_removed                  0
fabricated_eligibility_risk     True
safe_to_regenerate             False
```
