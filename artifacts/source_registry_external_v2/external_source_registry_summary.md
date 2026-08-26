# External source registry seed

A seed registry of candidate funding sources, imported from a source-discovery dossier. **No URL was requested, no scraper was started, and nothing here is being watched.**

- Sources imported: **381**
- Sources being monitored: **0**
- URLs fetched during import: **0**

## What a registry entry is not

Being listed here answers one question: *is this somewhere we might look?* It does not say a customer qualifies, and it does not say an award could pay for software. Those are tracked as separate statuses and both read `NOT_DETERMINED_BY_REGISTRY` on every row.

## Tiers and jurisdiction

| Priority tier | Sources |
| --- | --- |
| Tier 1 | 144 |
| Tier 2 | 133 |
| Tier 3 | 58 |
| Tier 4 | 42 |
| Tier 5 | 4 |

| Jurisdiction | Sources |
| --- | --- |
| federal | 303 |
| private | 21 |
| state | 57 |

## Terms review

| Terms status | Sources |
| --- | --- |
| `HUMAN_REVIEW_ONLY` | 10 |
| `NO_REVIEW_REQUIRED` | 223 |
| `TERMS_REVIEW_REQUIRED` | 148 |

**158 of 381 sources carry an obligation or a blocker.** None may be automated before that is resolved, and 62 may only ever be checked by a person.

## Capability is not approval

21 sources expose an API. **0 are approved for automated use.** The two are separate fields and an invariant keeps the approved count at zero until somebody clears them.

## State scoping

57 sources are state-scoped, covering SC. They are visible only to customers whose declared **operating state(s)** include that state - not their mailing address. A customer with no declared operating state sees none of them.

## Software allowability

| Class | Sources |
| --- | --- |
| `clearly_allowable` | 13 |
| `likely_allowable` | 45 |
| `sometimes_allowable` | 99 |
| `unclear` | 104 |
| `unknown` | 118 |
| `unlikely_allowable` | 2 |

**58 sources reach the watchlist.** `sometimes_allowable` is deliberately excluded from it: most of the registry reads that way, so a watchlist including it would be the registry with extra steps.

This is a prioritisation aid, not legal advice. No entry says a customer may buy anything; every one requires a live NOFO and an approved budget first.

## Unknowns preserved

570 cells read `UNKNOWN` and are carried through as written. An unknown capability is not an absent one.

