# 522 — Gate 92: SC recognition sets and the geography gate

## Three sets, never one

The research pass found three distinct South Carolina lists that are routinely
confused with each other. Conflating any two produces a wrong eligibility
answer.

```text
1  SC state-recognized entities
   Advance SC registry (SC Commission for Community Advancement and
   Engagement). Three categories: Tribes, Indian Groups, Special Interest
   Organizations. 16 entities, of which 10 are Tribes.

2  Federally recognized Tribes resident in SC
   Exactly ONE: the Catawba Nation. Confirmed against the BIA's annual
   Federal Register notice listing 575 entities.

3  Federally recognized Tribes with SC consultation interest
   The SCDAH Section 106 list: 16 Tribes with historic affiliation to South
   Carolina, 15 of them non-resident. A consulting-party list, NOT a
   recognition list.
```

Set 3 is where the damage happens. It is 16 entries long and reads like a
recognition list. An invariant fails any record where a consultation listing is
treated as recognition in SC, and another fails any entity other than the
Catawba Nation claiming set 2.

Two operational notes carried from the research: the Advance SC registry
publishes **no date stamp anywhere**, so change detection must be content
hashing rather than date checking; and the agency was renamed in May 2025, so
every stored `cma.sc.gov` URL is stale and 301s to `advance.sc.gov`.

## Why this is not a cosmetic distinction

Federal recognition is a documented hard gate on GAP, CWA §106/§319, TTP, TTPSF,
SS4A, DOE TELGP and CTAS. A state-recognized-only SC entity cannot win any of
them, and surfacing them is worse than surfacing nothing — it spends a small
grant office's scarcest resource on an application it cannot win.

Two documented exceptions are encoded rather than generalized:

**FTA.** Its own tribal-governments page states that tribal governments which
are not federally recognized *remain eligible to apply to the state as a
subrecipient for funding under the state's apportionment.* This is the clearest
state-recognition pathway found anywhere in the set. It is offered only for
programs where it is documented — an invariant fails any record offering an
undocumented state pathway — and notably SCDOT names Section 5311(c) Tribal
Transit on paper with no detail, which is an open question to put to SCDOT
rather than a route to advertise.

**ED Title VI.** Student eligibility counts members of state-recognized tribes,
terminated tribes, and first- and second-degree descendants. Whether such a
Tribe may itself be the **applicant** is unresolved by the source, so it stays
UNKNOWN rather than being rounded up. Student counts are not applicant
eligibility.

`applicant_eligibility_determined` is False on every access record, enforced by
an invariant. This model says whether a recognition gate excludes an entity. It
does not tell a customer they qualify.

## The geography gate runs before ranking

Four clean out-of-scope test cases for an SC customer, each parametrized into
its own test:

```text
Potlatch Fund                     ID, MT, OR, WA
Bush Foundation                   MN, ND, SD
Cherokee Preservation Foundation  NC (EBCI / western NC)
Bureau of Reclamation             17 Western States
```

None may ever reach an SC customer. A ranker that scores them first has already
failed, so `runs_before_ranking` is True and an invariant fails any result
demoting the gate to a post-filter.

## Deny by default

```text
in_scope           customer state overlaps source geography
out_of_scope       no overlap, or not named in an enumerated eligible set
withheld_unknown   customer states unknown, or source geography unknown
```

Only `in_scope` sets `surfaced_to_customer`. A source whose geography is unknown
is **withheld**, not shown — a filter that passes what it does not understand is
not a filter. Both directions are tested: unknown source geography and unknown
customer states each withhold.

## Enumerated-set eligibility

Class-based eligibility cannot express every restriction. Reclamation's current
Colorado River Basin Tribal Drought Resiliency opportunity is restricted to a
hard-coded list of **30 named Tribes** — no vocabulary of applicant classes
captures that.

So the gate accepts an enumerated eligible set alongside state scoping, and the
enumerated set wins. An AZ customer in an AZ-scoped program is still
`out_of_scope` if not named in the list, and a customer whose own entity name is
unknown is withheld rather than passed. Both cases are tested.

## `distribution_mode`

```text
direct | state_formula | state_competitive | either | unknown
```

Carried so a federal listing is never advertised when the live route is a closed
state allocation. Vocabulary-checked; not yet populated from the registry.
