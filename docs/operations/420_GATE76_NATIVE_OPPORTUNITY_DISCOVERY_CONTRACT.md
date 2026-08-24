# 420 — Gate 76C: Native opportunity discovery contract

## What is implemented

`src/nativeforge/services/native_opportunity_discovery_service.py` — joins three
previously separate things into one routed, evidence-backed opportunity record: a
registry source (76B), an opportunity freshness state (76D), and a Native
relevance classification (Sprint 189).

## What is not reimplemented

The sixteen `native_relevance_classification_*` services. Their evaluator already
separates `_keyword_hit` from `_structured_signal`, which is exactly the
distinction that matters, and it has an overclaim guard and an over-filter guard.
Writing a second classifier would create a competing opinion that drifts.

This module **consumes** a classification and enforces what may be concluded
from it.

## How Native relevance is evidenced

Relevance credit requires all three:

1. At least one evidence entry with a **recognised kind and a non-empty
   reference**. A recognised kind pointing at an empty string is an assertion
   wearing the word evidence.
2. **Not keyword-only.** If the classification reports a keyword hit with no
   structured signal, credit is refused with
   `native_relevance_from_keyword_match_only` — even when the label is strong.
3. A label in the strong or moderate set. Weak, uncertain and irrelevant labels
   earn nothing regardless of evidence.

Accepted evidence kinds:

```text
explicit_tribal_eligibility_text
explicit_native_nonprofit_eligibility_text
tribal_set_aside_provision
native_specific_program_authority
funder_native_program_page
operator_verified_relevance
```

A keyword is deliberately absent from that list.

## How eligibility is handled, and why it is separate

**Eligibility is never inferred from relevance.** Relevance is a property of the
program; eligibility is a property of the applicant. An opportunity can be
unmistakably Native-relevant and still not say whether a given organization may
apply.

```text
explicit eligibility evidence cited      → eligible
eligibility text present, routing known,
  nothing cited                          → possibly_eligible + human review
otherwise                                → unknown
```

`unknown` stays `unknown`. An invariant fails any record marked `eligible`
without eligibility evidence.

This matters because the consequence of a wrong `eligible` is a tribal
organization spending weeks on an application it was never permitted to file.

## Recognition routing: two orthogonal axes

The requested vocabulary mixes two different questions:

| Axis | Values |
| --- | --- |
| **Who the applicant is** | `federally_recognized`, `state_recognized`, `native_nonprofit`, `native_business` |
| **What the money is for** | `native_housing`, `native_health`, `native_education`, `native_culture`, `native_infrastructure` |

A federally recognized tribe can pursue a housing grant. These are not
alternatives, so forcing one value per opportunity discards whichever axis loses
— and discarding the applicant axis would silently narrow eligibility for a real
tribal government.

Resolution: `recognition_routing` is a **set** of tags, and two projections are
derived:

- `recognition_tier` — reuses the existing 4-value `RECOGNITION_TIERS` from the
  Gate 54 scorer. `native_business` has no tier there, so it projects to
  `unknown` rather than inventing a fifth tier.
- `native_sectors` — the sector tags.

A test asserts the two axes partition the vocabulary, and that every applicant
tag projects into the existing tier vocabulary.

**State recognition is not federal recognition.** They are different statuses
with different eligibility consequences, and South Carolina has state-recognized
tribes — which is the concrete reason the applicant axis exists at all. A test
asserts they do not collapse.

Sector-only routing leaves the tier `unknown`: knowing the money is for housing
says nothing about who may apply.

Unrecognised tags are surfaced in `unrecognised_tags` and flagged for review
rather than dropped.

## State / federal separation

Lanes are `federal`, `state`, `local`, `private`, `unknown`, and they stay
distinct:

- A `state` lane record with no state is **blocked**.
- A `state` lane record carrying a `federal_agency` is **blocked**, and an
  invariant catches it independently.
- A `federal` lane record with a state but no federal agency is flagged for
  review.

**SC-specific is not SC-only.** A federal opportunity relevant to a South
Carolina organization stays in the `federal` lane with `state="SC"` and
`funding_geography="federal"`. Collapsing it into the state lane would corrupt
both coverage counts — federal would undercount and state would overcount, and
the customer would be told their funding landscape is smaller and more local
than it is.

## Quality credit chain

`counts_toward_quality` requires all of: no blockers, relevance credited,
freshness state current, not a duplicate. Any one missing and it is `False`.

## Authority to apply

Recognised requirement kinds: `tribal_council_resolution`,
`authorized_representative_signature`, `sam_gov_registration`,
`indirect_cost_agreement`, `board_resolution`, `none_stated`, `unknown`.

An empty list becomes `["unknown"]` with
`authority_requirements_not_determined` flagged for review — not silently
treated as "no requirements". Assuming no authority requirement is how an
application gets filed without a council resolution and rejected.

## Visibility

`visible: True` always, including blocked records. A blocked opportunity is still
a record of something we found, and hiding it would make the discovery gaps
invisible.

## Not done here

No fetching, no parsing, no persistence. The NOFO parser is Gate 81, duplicate
and spam control is Gate 83, and the measured baseline is Gate 85 — which must
use the existing Gate 54 scorer rather than a second one.
