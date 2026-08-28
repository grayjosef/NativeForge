# 584 — Gate 105B/C: Tribal eligibility classification bridge contract

`src/nativeforge/services/mixed_corpus_grant_field_derivation_service.py`
`src/nativeforge/services/tribal_eligibility_classification_bridge_guard_service.py`

## A local shadow existed

`mixed_corpus_grant_field_derivation_service` imported the canonical
`_TRIBAL_TYPE_RE` on line 13 and rebound the same name on line 24 to a local
regex with two of the four alternatives removed:

```text
canonical  native american tribal | federally recognized tribe | indian tribe | tribal government
shadow     native american tribal | federally recognized tribe
```

The import was dead from the moment it was written. The module read as bridged
at the top of the file and was not, which is why the defect survived review and
why ruff's F811 was the only thing pointing at it.

## The canonical classifier is now used

The local definition is gone. The module uses the imported canonical pattern at
both detection sites — `applicantTypes[].description` and `eligibility_text` —
and a comment stands where the shadow was, naming what happened so the next
reader does not re-add it.

Not a widened copy: the *same object*. A test asserts
`mixed._TRIBAL_TYPE_RE is CANONICAL_RE`, so the two cannot drift apart again by
being edited independently.

Phrases now detected on both paths:

```text
Eligible: any Indian tribe
Open to tribal governments
Federally recognized tribe only
Indian Tribes
Tribal governments
federally recognized Indian Tribe
Native American tribal governments (Federally recognized)
```

No phrase was added to the canonical vocabulary. Every one of these was already
supported upstream and was simply unreachable through the shadow.

## Under-detection was the failure mode

The shadow's alternation was a strict subset of the canonical one, so it could
only ever match fewer strings. Structurally and empirically it could miss Tribal
eligibility and never invent it.

Measured across the whole corpus, re-derived with each pattern:

```text
rows re-derived                      57
rows corrected by the fix             3
positives removed by the fix          0
```

Under-detection is treated as a defect rather than acceptable caution. A
Native-relevant grant platform that fails to notice Tribal eligibility scores a
genuinely eligible opportunity as if applicant types exclude Tribes — which is
the specific harm the product exists to prevent.

## No fabricated eligibility was introduced

The three corrected rows were already self-contradictory: each carried
`tribal_eligible: True` while its eligibility text named Indian tribes or tribal
governments, and the derived field nevertheless said applicant types do not
include Tribal. The fix makes the record agree with its own source text. It
adds no claim the text does not carry.

Held by tests: non-Tribal text stays non-Tribal on both paths, absent text stays
unknown, and every corpus row asserting Tribal applicant types must have
supporting evidence behind it.

## The drift guard

`tribal_eligibility_classification_bridge_guard_service` measures alignment by
**running both sides on the same phrase**, never by comparing pattern strings or
reading a flag. A module that claims to bridge and does not fails here — which is
exactly the case that shipped.

```text
canonical positive, mixed-corpus positive   aligned
canonical positive, mixed-corpus negative   under-detection - a defect
canonical negative, mixed-corpus positive   over-claim - prohibited outright
canonical negative, mixed-corpus negative   aligned
```

The two failure directions are not symmetric and are not reported as if they
were. Missing an opportunity costs a tenant a deadline; inventing eligibility
costs them a rejected application and their credibility. Over-claim is reported
separately as `fabricated_eligibility` and fails regardless of who owns it.

`find_shadowed_canonical_names` parses each bridged module with `ast` and reports
module-level rebindings of imported canonical names. A text search would trip
over this very document and would miss a rebinding written differently.

Both bridged modules — mixed-corpus derivation and the reingest service — are
checked, and both are clean.

## Under-detection this bridge does not own

One phrase, `Native American tribal organization`, is still missed on the
free-text path. The cause is upstream: `grants_gov_eligibility_parser_service`
does not treat a tribal *organization* as `tribal_eligible`, so derivation never
reaches the applicant-type branch this gate owns. Fixing the bridge cannot fix it.

Rather than dropping the phrase from the list — which would hide a real gap — it
is registered, attributed to its owner, and reported in the artifact. Two things
stop the registry becoming a permanent excuse:

```text
verified   each entry is re-checked against the upstream parser at report time,
           not trusted; an entry upstream no longer explains is marked stale
           and fails the invariants
scoped     the three phrases Gate 104 reported may never be excused - a test
           asserts none of them appears in the registry
```

`bridge_intact` is derived from the measurements, never declared. A mutation
hardcoding it true is caught.

## What this gate did not touch

```text
the cached corpus fixture   nf14_mixed_corpus.json is not regenerated - see 583
the upstream body parser    a third tribal vocabulary, left to its own gate
repo-wide lint              700 pre-existing findings, deliberately untouched
Gate 104 digest semantics   consume corrected input; no rule changed
```
