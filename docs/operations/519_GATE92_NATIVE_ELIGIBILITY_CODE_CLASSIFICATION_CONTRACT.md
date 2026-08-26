# 519 — Gate 92: Native eligibility code classification contract

This is the contract closest to the reason NativeForge exists.

## The recall set is five codes, not two

Grants.gov "Eligible Applicants" is a 2-character coded value. Three codes name
tribal applicants directly:

```text
07   Native American tribal governments (Federally recognized)
11   Native American tribal organizations (other than Federally recognized
     tribal governments)
08   Public housing authorities/Indian housing authorities
```

Two more are mandatory in the **recall** set:

```text
99   Unrestricted (i.e., open to any type of entity below)
25   Others (see text field entitled "Additional Information on Eligibility")
```

`99` is silently tribe-eligible. `25` hides tribal eligibility inside a
4,000-character free-text field. **A system that filters on `07|11` looks clean
and silently misses a large share of tribally-eligible money** — the exact
failure this product exists to prevent. So the recall set is a frozenset with a
test pinning it at exactly `{07, 11, 08, 99, 25}`, not a query someone can
tighten later.

## Graded, never boolean

```text
direct            the code names tribal applicants        (07, 11, 08 / ET230x0)
requires_reading  eligible in principle; the answer is in
                  text we have not read                   (99, 25, ET12010)
negative          no tribal-eligible code present
unknown           no code present at all
```

`requires_reading` never collapses into either neighbour, and two invariants
enforce it in both directions: treating it as a positive fabricates eligibility,
treating it as a negative hides money.

`unknown` is separate from `negative` for the same reason Gate 89 separated an
absent answer from an empty one — a record with no code has not been assessed,
and saying otherwise turns a gap in the data into a finding.

## The service does not read the free text

It marks the text as requiring a read, records whether text is even present, and
stops. `free_text_screened` and `free_text_read_by_this_service` are both False
and invariants keep them there. No NLP, no keyword guessing, no inference from a
title. The screening backlog is counted and reported so the unread text is
visible as work outstanding rather than as an answer.

## The SAM crosswalk is a mapping, not an equivalence

```text
ET23010  Federally Recognized ... Tribal Government                 -> 07
ET23020  ... Tribal Government (Other than Federally Recognized)    -> 11
ET23030  Tribally Designated Housing Authority                      -> 08
```

The research pass tagged this mapping as its own `[INFER]`, not as
documentation. It is therefore recorded with `crosswalk_is_inferred: True`, an
invariant fails any record claiming otherwise, and the crosswalk is only ever
used to report what a SAM code *would* map to — never to manufacture a
Grants.gov code onto a record.

`ET12010` ("Specific Restrictions Determined at NOFO Level") means the
Assistance Listing **under-determines** eligibility. It sets
`nofo_text_is_authoritative`, checked by an invariant.

## Twelve eligibility classes

```text
federally-recognized-tribe        state-recognized-tribe
tribal-government                 tribal-organization
native-nonprofit                  native-owned-business
native-serving-nonprofit          tribal-college-or-BIE-school
native-individual                 consortium-with-tribal-partner
state-or-local-govt-serving-natives                     UNKNOWN
```

A class is implied only where a code's own label says so. Everything else is
`UNKNOWN`.

## What classification is not

`customer_eligibility_determined` is False on every result, and an invariant
enforces it. Classifying an opportunity's codes says what the opportunity
allows. It does not say a particular customer qualifies — that requires the
recognition model (doc 522's SC contract), the geography gate, and in the
`requires_reading` cases, a human reading the NOFO.
