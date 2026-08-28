# Honest mixed corpus derivation

Measured across every derived row. Nothing here is a declaration; each value is what derivation actually produced.

```text
row_count                            57
honest_empty_preserved               True
unknown_preserved                    True
fabricated_eligibility_risk          False
rows_with_synthesized_eligibility_text 0
rows_narrowed_without_evidence       0
```

## Rows declaring honest emptiness

These rows state that their blank fields are the truth rather than a gap. Derivation must leave them blank.

```text
nf13-real-fed-025
```

## Rows whose unknown was preserved

`applicant_types_include_tribal` left as unknown because nothing described who may apply. Unknown is not False.

```text
nf13-real-fed-025
nf14-mixed-label_spread-16
```

## Boundaries

```text
live_fetch_performed         False
source_monitoring_live       False
live_source_coverage         False
fabricated                   False
```

Derivation reads recorded fixtures. Nothing was fetched, no collector ran, and no source coverage is claimed.
