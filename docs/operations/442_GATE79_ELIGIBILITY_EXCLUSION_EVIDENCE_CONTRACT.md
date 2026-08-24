# 442 — Gate 79C: Eligibility exclusion evidence contract

`src/nativeforge/services/eligibility_exclusion_evidence_service.py`

## What this adds

The ability to say **"this programme's cited eligibility text appears to exclude
this applicant class"** — a claim the product could not previously make.

## Why it was needed

Gate 78R found the case. `advance.sc.gov/grants-state-tribes` is South Carolina's
own resource *for state tribes*, and every programme on it is federal. NACTEP's
eligibility, quoted on that page:

> "Federally recognized Indian tribes, tribal organizations, Alaska Native
> entities, and eligible BIE-funded schools"

South Carolina has **one** federally recognized tribe and **ten** state-recognized
ones. That sentence is not silence about state-recognized tribes — it is an
enumerated, exclusive list they are not on.

Before Gate 79 the product could only answer `unknown`. Doc 440 also found that
`not_eligible` existed in the vocabulary but was **unreachable by design**:
`federal_native_eligibility_service` hardcodes `not_eligible_asserted: False`
with an invariant forbidding anything else.

That was the right call for universal ineligibility and the wrong outcome here.
Telling a tribal grant office "we don't know" when the notice plainly excludes
them wastes the scarcest thing they have, which is staff time — an `unknown`
invites a week of investigation that ends the same way.

## The distinction that keeps this honest

| Claim | Scope | Assertable? |
| --- | --- | --- |
| `not_eligible` | universal — this organization is ineligible | **no, still forbidden** |
| `excluded_by_evidence` | this programme's cited text excludes this class | yes, with a citation |

`excluded_by_evidence` is narrower in three ways: one programme, one applicant
class, one citation. It never says an organization is ineligible for anything in
general.

**Gate 77's guard is untouched.** This module also hardcodes
`not_eligible_asserted: False` and re-enforces
`forbidden_claim:not_eligible_asserted`, and a Gate 79 test asserts the Gate 77
service still contains its own guard.

## Applicant classes

Eight, up from the three recognition tiers that existed:

```text
federally_recognized_tribe   state_recognized_tribe
native_nonprofit             native_business
tribal_organization          bie_funded_school
native_individual            unknown
```

Bridged onto `federal_native_eligibility_service.RECOGNITION_TIERS` via
`FEDERAL_TIER_MAP`. Classes with no tier there — `native_business`,
`tribal_organization`, `bie_funded_school`, `native_individual` — map to `None`
rather than borrowing one. A test asserts every projection is either `None` or a
member of the existing set.

Note the naming bridge: `federally_recognized_tribe` here,
`federally_recognized_tribal_government` there.

## Result states

```text
eligible                    the text names this class
possibly_eligible           an exclusive list was widened by cited evidence
excluded_by_evidence        exclusive list, this class absent, citation present
not_supported_by_evidence   text exists, is not exclusive, says nothing here
unknown                     no text, or unrecognised class
human_review_required       exclusion indicated but no citation supplied
```

## Four refused inferences

**Silence is not exclusion.** Exclusion requires an *exclusive list*: an
exclusivity marker (`only`, `limited to`, `restricted to`, `solely`, …) **and** at
least one named class. Text that simply omits a class yields
`not_supported_by_evidence`.

A test asserts a marker alone is not enough and a named class alone is not
enough.

**A narrow grant is not a broad one.** "Eligibility is limited to eligible
BIE-funded schools" makes schools `eligible` and tribal governments
`excluded_by_evidence` — it does not make tribal governments eligible by
association.

**A restriction is not an exclusion.** "On Federal Trust land" narrows how an
award may be used; the class survives. Restrictions are collected separately
(`federal_trust_land`, `reservation_only`, `service_area_only`) and carried into
the result. A test asserts a trust-land notice does not produce an exclusion.

**Exclusion is per class.** `evaluate_all_applicant_classes` returns a verdict
per class rather than one answer, because a notice that excludes state-recognized
tribes may still be open to Native nonprofits, and collapsing that would lose the
useful half. An invariant fails any class appearing in both
`eligible_classes` and `excluded_classes`.

## Citation requirement

An exclusion **must** cite a reference. Without one the result is
`human_review_required`, not exclusion.

An exclusion without a citation is an accusation. It would discourage a real
applicant on our say-so, and the applicant has no way to check us.

Invariants: `exclusion_without_citation`,
`exclusion_without_an_exclusive_eligibility_list`,
`excluded_a_class_the_text_names_as_eligible`.

## Widening evidence

A later notice, amendment or funder confirmation can reopen a closed list:
`additional_expanding_evidence` entries naming the class and carrying their own
reference move the result to `possibly_eligible`.

A bare assertion does not. An entry with an empty reference leaves the exclusion
standing — tested.

## The NACTEP worked example

```text
input:  "Eligibility is limited to Federally recognized Indian tribes, tribal
         organizations, Alaska Native entities, and eligible BIE-funded schools"
cite:   https://advance.sc.gov/grants-state-tribes

federally_recognized_tribe  → eligible
tribal_organization         → eligible
bie_funded_school           → eligible
state_recognized_tribe      → excluded_by_evidence
native_nonprofit            → excluded_by_evidence
native_business             → excluded_by_evidence
native_individual           → excluded_by_evidence
```

## State-recognized vs federally recognized

The two are never interchangeable, and this module is where that becomes
actionable rather than merely respected.

`recognition_routing_contract_service` (Block 27) already said state recognition
is never treated as federal recognition. Gate 78 enforced no inference between
tiers. Gate 79 adds the consequence: when a federal notice says "federally
recognized", a state-recognized tribe gets a cited exclusion rather than a shrug.

For SC that is the difference between a usable answer and an unusable one across
most Native-specific federal programmes.

## `eligibility_proven`

True only when the state is `eligible` **and** a citation exists. An invariant
fails `eligibility_proven_without_eligible_state`.

## Not done here

No eligibility text is fetched or parsed — it is an input. Extraction is the NOFO
parser, Gate 81. Not yet surfaced in the discovery record or the Gate 54 quality
scorer; an excluded opportunity should not count as coverage for the excluded
class, and that wiring is recorded as engineering-blocked in doc 444.

**Nothing here verifies the Gate 78R eligibility strings against primary
sources.** The research fixture marks every one `eligibility_verified: false`,
and no customer-facing exclusion should be published on a summarised read of an
index page.
