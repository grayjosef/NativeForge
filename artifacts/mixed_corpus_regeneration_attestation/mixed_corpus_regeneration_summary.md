# Mixed corpus regeneration attestation

Corpus: `fixtures/real_grants_corpus/nf14_mixed_corpus.json`

## Outcome

**The committed fixture already agrees with fresh derivation.** There is nothing outstanding to write.

```text
fixture_mutated                  False
fixture_matches_fresh_derivation True
safe_to_regenerate               True
safe_to_commit_fixture           True
human_review_required            False
fabricated_eligibility_risk      False
positives_added                  0
positives_removed                0
```

## Hashes

```text
before (committed)  a9ab264982abddaca1cc526f77ce9ad1258ef2803174bc4157b3246268dbf650
after  (fresh)      a9ab264982abddaca1cc526f77ce9ad1258ef2803174bc4157b3246268dbf650
attestation_id      8a4d32b19080331df0073c8fd5820abbf1c22f0c9246d2a07fb77c1faf3a28ab
```

## Changes by class

```text
rows total                        57
rows changed                      0
fields changed                    0
gate105_tribal_bridge_correction  0
preexisting_fixture_drift         0
unexpected                        0
```

## Every differing field

```text
```

## Notes


## Boundaries

```text
live_fetch_performed         False
source_monitoring_live       False
live_source_coverage         False
fabricated                   False
```

This comparison reads two recorded fixtures. Nothing was fetched, no collector ran, and no source coverage is claimed.
