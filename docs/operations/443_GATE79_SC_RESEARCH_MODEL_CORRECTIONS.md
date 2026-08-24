# 443 — Gate 79D: SC research model corrections

How the Gate 78R research findings are represented in code, and the boundaries
that keep the representation honest.

## The fixture

`tests/fixtures/sc_research/gate78r_grants_for_state_tribes_model.json`

It models a **research finding about a page**, not a set of live opportunity
records.

```text
provenance:          research-derived model, NOT live coverage
monitoring_allowed:  false
coverage_claimed:    false
freshness_claimed:   false
eligibility_proven:  false
last_checked_at:     null
robots_terms_status: unresolved
```

## What it deliberately does not contain

**No invented opportunity records.** A test greps the file for
`close_date`, `posted_date`, `opportunity_number`, `award_amount`,
`application_url` and `deadline` and fails if any appears.

None of those were captured in Gate 78R, so none may exist here. Inventing a
close date would be the single most damaging fabrication this product could
commit — a missed deadline is unrecoverable for a grant office.

## The eligibility caveat

Every eligibility string carries `eligibility_verified: false`.

They were reported in quotes by the Gate 78R read of
`advance.sc.gov/grants-state-tribes`, but that read was a summarised fetch of an
**index page**, not the primary notice for each programme. So each string is a
research lead requiring primary-source confirmation before any exclusion is shown
to a customer.

This matters because Gate 79C can now produce `excluded_by_evidence` from such a
string. The contract permits it; this fixture withholds the confirmation. Both
are correct: the capability exists, the specific claims are not yet verified.

## Programme currency

Unknown, and stated as unknown. Federal programmes open and close. The fixture is
a snapshot of a page as read on 2026-08-24 — not a claim that any programme is
currently accepting applications. No freshness is asserted anywhere.

## The host/lane mismatch, recorded as data

```text
source_lane:                        sc_state
opportunity_funding_lane_default:   federal_sc_relevant
```

The page is an SC state domain hosting twelve federal programmes. That mismatch
**is** the finding, and it is exactly what Gate 79B corrects: lane per
opportunity, not inherited from the host.

A test asserts every programme in the fixture resolves to a federally-funded lane
or `unknown`, and **never** to `sc_state`.

## Pass-through examples

Three, drawn from the research and used as test inputs for the classifier:

| Source | Federal funder | Expected lane |
| --- | --- | --- |
| SCEMD — HMGP | FEMA | `federal_pass_through` |
| SCOR — CDBG-MIT | HUD | `federal_pass_through` |
| SCDES — §319 | EPA | `federal_pass_through` |

Each is run through `classify_opportunity_funding_lane` with `source_lane`
deliberately set to `sc_state` and an `.sc.gov`/`.org` source URL — the exact
conditions that would previously have produced a state classification. A test
asserts all three come back `federal_pass_through`, `federally_funded: True`,
`state_funded: False`.

## The one state-funded candidate

SC Housing's Housing Trust Fund is the clearest `sc_state` candidate found in the
whole research pass. Even so, the fixture notes it still requires a cited
reference, because Gate 79B forbids inferring `sc_state`.

A test runs it with the citation and asserts `sc_state`; a separate test runs the
same input *without* the citation and asserts `unknown`.

## Recognition context, recorded with its discrepancy

```text
sc_federally_recognized_tribes:     1
sc_state_recognized_tribes:        10
sc_indian_groups:                   3
sc_special_interest_organizations:  3
```

Sourced from `advance.sc.gov/south-carolinas-recognized-native-american-indian-entities`.

A secondary source reported **nine** state-recognized tribes; the agency page
enumerates **ten**. The agency page is treated as authoritative and the
discrepancy is **recorded rather than resolved** — a test asserts the note
mentions it.

Silently picking one number would hide a real uncertainty about how many tribal
communities this product is meant to serve.

## Why this is not live coverage

Nothing was fetched to build this fixture beyond the Gate 78R research read.
Nothing is monitored. No source from the research pack has been seeded into the
registry, because robots/terms review has not happened for any of them.

The fixture exists so the two Gate 79 contracts can be tested against the real
shape of a real finding, rather than against invented inputs that would flatter
them.

## What would make these claims real

1. Robots/terms review for `advance.sc.gov` and the five pass-through sources.
2. Primary-source verification of each eligibility string, replacing
   `eligibility_verified: false` with a cited confirmation.
3. Seeding the sources into the registry with `citation_url` recorded.
4. Only then may an exclusion be surfaced to a customer.

Steps 1 and 2 are owner-blocked. See doc 444.
