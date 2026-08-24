# 425 — Gate 77C: Federal Native eligibility evidence

`src/nativeforge/services/federal_native_eligibility_service.py`. Whether a
Native organization may apply to a federal opportunity, decided from cited
evidence rather than inference.

## Evidence types

| Type | Strength |
| --- | --- |
| `explicit_tribal_government_eligibility` | Explicit — credits its tier |
| `explicit_native_nonprofit_eligibility` | Explicit — credits its tier |
| `explicit_native_organization_eligibility` | Explicit — credits its tier |
| `cfda_assistance_listing_applicant_type` | Strong, **binding required** |
| `grants_gov_applicant_eligibility_code` | Strong, **binding required** |
| `federal_register_notice_text` | Narrative, **quote required** |
| `agency_nofo_text` | Narrative, **quote required** |
| `program_page_text` | Narrative, **quote required** |
| `unknown` | Rejected |

Every item also needs a non-empty `reference`. A citation with nothing to open
is an assertion.

## Three refused inferences

### Keyword-only matching

The word "tribal" in a title is not eligibility. An opportunity can be entirely
about tribal communities and still restrict applicants to states or
universities. An item flagged `keyword_match_only` is rejected with
`keyword_match_only_is_not_eligibility`.

`title_mentions_tribal` is accepted as an input **specifically so it can be
recorded as not evidence** — the output carries
`title_keyword_is_not_eligibility` in its notes. Taking the signal and visibly
refusing it is stronger than not accepting it, because the refusal shows up in
the record.

### Parent-agency mission

IHS exists to serve Native people. That does not make every IHS opportunity open
to every Native organization, and it says nothing whatsoever about a SAMHSA
opportunity.

Gate 77's triage makes this concrete rather than theoretical: a live search
substituted an IHS opportunity for a SAMHSA seed. Agency-level reasoning about
eligibility is demonstrably unsafe when agency attribution itself can be wrong.

`agency_serves_native_communities` is likewise accepted and visibly refused with
`agency_native_mission_is_not_opportunity_eligibility`.

### Applicant codes floating free

Grants.gov applicant eligibility codes and assistance-listing applicant types are
the best structured evidence available — but only when tied to a specific
opportunity or listing. A code recalled from a program page describes the
program, not this NOFO. Programs change applicant sets between fiscal years.

Unbound codes are rejected with
`applicant_code_not_bound_to_an_opportunity_or_listing`. Supply
`opportunity_id` or `assistance_listing_id` and they count.

## Recognition tiers stay independent

Three separate applicant types:

```text
federally_recognized_tribal_government
state_recognized_tribe
native_nonprofit
```

Each is credited only by evidence mapped to it. Explicit tribal-government
eligibility credits the federally recognized tier and leaves the other two
`unknown` — a federal notice naming federally recognized tribes says nothing
about whether a state-recognized tribe or a Native nonprofit may apply. Those are
different questions with different answers, and in South Carolina the
state-recognized case is the common one.

An invariant fails `eligible_from_unmapped_evidence` if a tier is credited by
evidence not mapped to it.

## Resolution

```text
tier-mapped explicit evidence present  → eligible
bound applicant code, no tier named    → possibly_eligible + human review
otherwise                              → unknown
```

`possibly_eligible` is the honest middle: the structured evidence is real and
bound, but it does not name this tier, so a human decides.

## Never `not_eligible`

This module has no path to assert ineligibility. `not_eligible_asserted` is
`False` and an invariant enforces it.

Absence of evidence is `unknown`. Asserting "not eligible" on no grounds would
discourage a real applicant from a grant they may well be entitled to — a worse
error than leaving the question open, because the customer never finds out what
they missed.

## Invariants

```text
tier_set_incomplete
eligibility_state_invalid:<tier>
eligible_without_supporting_evidence:<tier>
eligible_from_unmapped_evidence:<tier>
credited_rejected_evidence:<type>
forbidden_claim:not_eligible_asserted
```

## Not done here

No fetching, no parsing of real NOFO text. Evidence items are inputs. Extracting
them from documents is the NOFO parser, Gate 81.
