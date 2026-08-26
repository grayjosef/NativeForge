# 506 — Gate 90E: software allowability watchlist

`nativeforge_software_allowability_source_service` ranks registry sources by how
plausibly an award from them could pay for capability-development software.

## This is a prioritisation aid. It is not legal advice.

Nothing here establishes that any customer may buy anything. 2 CFR 200 permits
costs that are necessary, reasonable and allocable — it does not make a product
allowable because it is useful.

The dossier is explicit that allowability belongs at the **opportunity +
budget-category** level, with program-family defaults no stronger than
"sometimes allowable". So the strongest thing this classifier can say about a
*source* is that it is worth looking at.

Every result carries:

```text
customer_may_purchase_software           False   (constant)
requires_live_nofo_and_approved_budget   True    (constant)
is_legal_advice                          False   (constant)
```

## What it reads

Only the committed registry row: `software_cost_allowability`,
`program_examples`, `source_type`, `notes`. No inference from agency reputation,
no lookup, no fetch.

## Results across the 55 sources

| Class | Sources |
| --- | --- |
| `clearly_allowable` | **0** |
| `likely_allowable` | 3 |
| `sometimes_allowable` | 44 |
| `unclear` | 6 |
| `unlikely_allowable` | 2 |
| `unknown` | 0 |

### The empty top bucket is the honest outcome

`clearly_allowable` exists so the vocabulary is complete, and **nothing in this
seed reaches it.** The strongest value across 55 rows is "Likely allowable", on
three. That is not a gap in the classifier — it reflects a dossier that
deliberately refused to assert a stronger position, and a classifier that
refuses to invent one.

## The watchlist — 3 sources

```text
EPA-GAP     Indian Environmental General Assistance Program
            environmental program capacity; "Likely allowable"
EPA-EN      Exchange Network Grant Program
            environmental data exchange systems; "Likely allowable"
CISA-SLCGP  State and Local Cybersecurity Grant Program
            cybersecurity plans, projects, tools; "Likely allowable"
```

All three are Tier 1. Two are EPA capacity/data programmes where a data system
is close to the programme's stated purpose rather than incidental to it; the
third is a cybersecurity programme whose eligible costs include tools.

`CISA-SLCGP` carries a caveat worth repeating: it is a pass-through, usually
state-administered, and the direct-versus-subrecipient route varies. Being on
this watchlist does not tell a tribal customer they can apply directly.

## `sometimes_allowable` is excluded from the watchlist, on purpose

44 of 55 rows read "Sometimes allowable depending on NOFO/budget category" or a
near-variant. A watchlist that included them would be the registry with extra
steps, and would quietly convert the dossier's hedge into a lead list.

An invariant fails if a `sometimes_allowable` entry is ever marked
`on_watchlist`.

## `Varies` and `Unclear` are not promoted

Both map to `unclear`, not `sometimes_allowable`. They are refusals to commit,
and rounding a refusal up to a hedge is how a caveat disappears.

The 6 `unclear` rows: `FED-SAM-AL`, `FED-FR`, `PRIV-NDN` (all "Unclear"), and
`NAT-ATC`, `DOI-BIA-GRANTS`, `DOI-BIE` (all "Varies").

## `unlikely_allowable` — 2 award databases

`FED-USA` (USAspending) and `NIH-REPORTER` both read "Not applicable" and are
typed `award_database`. They report past awards; they are not funding routes and
cannot pay for anything. The classifier says so explicitly in the explanation
rather than leaving the reader to infer it from a low rank.

## How to use this

For sales and discovery prioritisation: these are the sources where the
allowability conversation is most likely to go somewhere, so they are worth
watching first once terms review clears them.

For anything else: don't. A customer's ability to pay for NativeForge from any
award depends on a live NOFO, that NOFO's budget categories, the approved
budget, and the award terms — none of which this registry contains.
