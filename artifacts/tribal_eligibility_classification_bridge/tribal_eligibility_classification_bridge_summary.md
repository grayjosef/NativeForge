# Tribal eligibility classification bridge

Schema: `nf_tribal_eligibility_classification_bridge_guard_v1`

## What was measured

Every phrase is run through the canonical classifier and through mixed-corpus derivation, along both real detection paths. Alignment is observed, not declared.

```text
row_count                                28
aligned_count                            27
misaligned_count                         1
under_detection_count                    1
bridge_owned_under_detection_count       0
upstream_owned_under_detection_count     1
stale_upstream_gap_count                 0
over_claim_count                         0
bridge_intact                            True
```

## No canonical name is shadowed

Each bridged module is parsed with `ast` and checked for a module-level rebinding of a name it imported from the canonical module. This is the defect Gate 105 removed.

```text
nativeforge.services.mixed_corpus_grant_field_derivation_service
    shadowed: none
nativeforge.services.tribal_grant_eligibility_reingest_service
    shadowed: none
```

## Under-detection this bridge does not own

Registered, verified against the upstream service at report time, and failed as stale the moment upstream stops explaining it.

```text
phrase: Native American tribal organization
    path:   eligibility_text
    owner:  grants_gov_eligibility_parser_service.tribal_eligible
    reason: the body-text parser does not treat a tribal organization as tribal_eligible, so derivation never reaches the applicant-type branch this gate owns
```

## Boundaries

```text
fabricated_eligibility         False
eligibility_determined         False
live_source_collection         False
source_monitoring_live         False
source_coverage_claimed        False
```

This guard measures classification. It determines no eligibility, collects from no source, and claims no coverage.
