# Mixed corpus regeneration attestation

Corpus: `fixtures/real_grants_corpus/nf14_mixed_corpus.json`

## Outcome

**The fixture was not regenerated.** It is byte-identical to what git tracks. The changes below are what a regeneration *would* have written.

```text
fixture_mutated                  False
safe_to_regenerate               False
safe_to_commit_fixture           False
human_review_required            True
fabricated_eligibility_risk      True
positives_added                  3
positives_removed                0
```

## Hashes

```text
before (committed)  3296b2a94eb2a1fe5610bd651cce9b3d18a62dafefa199dd88b17af4530a2493
after  (fresh)      b204dc39fe8a09e739033db3556341989b38f3d4d7bf7bbfbffc47e5d46d0e43
attestation_id      89c837602ac6fe7ba66aeccd15caf313a0b9735ba3d756d2345539a3984d10de
```

## Changes by class

```text
rows total                        57
rows changed                      4
fields changed                    5
gate105_tribal_bridge_correction  3
preexisting_fixture_drift         2
unexpected                        0
```

## Every differing field

```text
nf13-real-fed-025.applicant_types_include_tribal
    class:    preexisting_fixture_drift
    evidence: unknown_narrowed_to_negative
    reason:   unknown narrowed to an affirmative negative, which asserts more than the source says
nf13-real-fed-025.eligibility_text
    class:    preexisting_fixture_drift
    evidence: honest_absence_overwritten
    reason:   derivation would populate an evidence field on a row that marked its own emptiness deliberate
nf14-mixed-edge-10.applicant_types_include_tribal
    class:    gate105_tribal_bridge_correction
    evidence: evidence_backed
    reason:   canonical Tribal classifier now recognises the applicant type this row already carried in its source text
nf14-mixed-label_spread-14.applicant_types_include_tribal
    class:    gate105_tribal_bridge_correction
    evidence: evidence_backed
    reason:   canonical Tribal classifier now recognises the applicant type this row already carried in its source text
nf14-mixed-label_spread-15.applicant_types_include_tribal
    class:    gate105_tribal_bridge_correction
    evidence: evidence_backed
    reason:   canonical Tribal classifier now recognises the applicant type this row already carried in its source text
```

## Notes

- 3 row(s) carry the Gate 105 canonical Tribal classifier correction, each backed by applicant-type text already in the record
- 1 row(s) carry drift that predates Gate 105 and is not attributable to it
- nf13-real-fed-025.applicant_types_include_tribal: unknown_narrowed_to_negative - unknown narrowed to an affirmative negative, which asserts more than the source says
- nf13-real-fed-025.eligibility_text: honest_absence_overwritten - derivation would populate an evidence field on a row that marked its own emptiness deliberate
- regeneration refused: the fixture is left byte-identical and the Gate 105 corrections remain unabsorbed in the cached manifest

```text
blocked: fabricated_eligibility_risk:2
blocked: unresolved_preexisting_drift:2
```

## Boundaries

```text
live_fetch_performed         False
source_monitoring_live       False
live_source_coverage         False
fabricated                   False
```

This comparison reads two recorded fixtures. Nothing was fetched, no collector ran, and no source coverage is claimed.
