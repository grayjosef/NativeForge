# 592 — Gate 107D/E: mixed corpus regeneration result

## The fixture was regenerated

`fixtures/real_grants_corpus/nf14_mixed_corpus.json`

```text
rows_total                        57
rows changed                       4
positives_removed                  0
eligibility_text synthesized       none
row ordering                       preserved
key ordering                       preserved
formatting                         preserved (indent 2, ASCII-escaped)
```

The complete diff, four lines:

```text
nf14-mixed-edge-10           applicant_types_include_tribal  false -> true
nf14-mixed-label_spread-14   applicant_types_include_tribal  false -> true
nf14-mixed-label_spread-15   applicant_types_include_tribal  false -> true
nf14-mixed-label_spread-16   applicant_types_include_tribal  false -> null
```

Nothing else in the file changed.

## Gate 106 blocked correctly, and was not relaxed

The Gate 106 attestation was re-run **unchanged**. It refused at Gate 106 and
permits now because the derivation was fixed, not because the check was lowered.

A test pins that: feed the attestation the pre-Gate-107 shape — a synopsis
landing in an honestly-empty `eligibility_text` — and it still reports
`fabricated_eligibility_risk: true` and `safe_to_regenerate: false`.

```text
                              Gate 106    Gate 107
rows_changed                         4           4
gate105_tribal_bridge_correction     3           3
gate107_unknown_restored             -           1
preexisting_fixture_drift            2           0
unexpected                           0           0
positives_removed                    0           0
fabricated_eligibility_risk       true       false
safe_to_regenerate               false        true
safe_to_commit_fixture           false        true
```

## The three Gate 105 corrections

Each row already carried `tribal_eligible: true` while claiming applicant types
exclude Tribes, and each has eligibility text naming Indian tribes or tribal
governments. The change makes the record agree with its own source text. Class
`gate105_tribal_bridge_correction`, evidence status `evidence_backed`.

## The fourth change, which the brief did not anticipate

`nf14-mixed-label_spread-16` moves `false -> null`.

The honest-derivation report found it: a row with no structured applicant types,
no eligibility text and no eligibility description was nonetheless asserting that
its applicant types exclude Tribes. The cause was in the builder rather than the
deriver — `_pull_to_grant` seeded `applicant_types_include_tribal` from
`tribal_eligible`, conflating "may Tribes apply" with "do the listed applicant
types include a Tribal class".

The Gate 107 brief specified `rows_changed = 3`. This gate produced 4, and the
deviation is deliberate. The gate's own rule — "False is allowed only when
evidence supports a negative classification" — was violated by that row, and my
own artifact's invariants failed on it. The alternatives were to ship an artifact
that fails its own checks, or to weaken the check until the number matched.
Neither is a real option, so the defect was fixed and the extra row attested.

### A new change class, not an exception

`gate107_unknown_restored` is the mirror of `unknown_narrowed_to_negative`:

```text
unknown_narrowed_to_negative   a regeneration asserts more than the source says
gate107_unknown_restored       a regeneration withdraws an unearned assertion
```

Withdrawing an unearned claim can only move a record from a false certainty to an
honest unknown, never the other way, so it is safe to permit. It is narrowly
scoped to `applicant_types_include_tribal` and to the `False -> None` transition
only; an invariant fails the class if it is used for any other transition, and a
test proves the reverse direction is still classified as drift.

## nf13-real-fed-025 remains honest-empty

The row that blocked Gate 106 is untouched in the regenerated fixture:

```text
eligibility_text                ''
applicant_types_include_tribal  null
empty_honestly                  true
never_synthesized               true
no_live_nofo                    true
```

Its honesty flags are true statements about it again.

## Regenerated values are evidence-backed

Every change is either a correction traceable to applicant-type language already
in the row, or the withdrawal of a claim that had no source at all. No value was
added that the record does not support.

The regeneration script refuses any change not present in the attestation's
expected set, and it did refuse once during this gate — when the fourth change
appeared before the attestation covered it. That refusal is the mechanism
working, not a mishap.

## A hash bug found and fixed in passing

Gate 106's diff hashed the cached *manifest* against the fresh *rows list* — two
different shapes, so `before_hash` and `after_hash` could never match. An
attestation always looked like a change even when nothing changed.

Both sides now hash the row list. Equal content gives equal hashes, and two tests
pin both directions.

## No live fetch occurred

Both sides of every comparison are recorded fixtures. No collector ran, no URL
was fetched, no scraper was activated, and no source coverage is claimed.
