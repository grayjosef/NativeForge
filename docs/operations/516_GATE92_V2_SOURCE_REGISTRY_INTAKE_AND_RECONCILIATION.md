# 516 — Gate 92: v2 source registry intake and reconciliation

The v2 registry is a completed research artifact, not a starting point. A full
source-discovery pass fetched and verified roughly 300 official primary pages on
2026-08-26. Gate 92 imports that result. It does not re-derive it, does not
resolve its UNKNOWNs, and does not correct its URLs — several correct URLs look
wrong and several familiar URLs are dead.

## What came in

```text
docs/research/nativeforge-funding-source-dossier-v2.md
docs/research/nativeforge-research-funding-and-cost-allowability.md
docs/research/ext-apis-monitoring.md
docs/research/ext-usda-hud-commerce.md
docs/research/ext-doj-dhs-ed-dol-sba.md
docs/research/ext-doe-epa-dot.md
docs/research/ext-extra-tables.md
docs/research/nativeforge-coding-agent-brief.md
fixtures/external_source_registry/nativeforge-source-registry-v2.csv
```

All nine present. A test asserts the eight required files exist, so a missing
file fails loudly rather than being reasoned around from memory.

The research documents tag every claim `[DOC]` (read in official documentation),
`[TESTED]` (a live request was issued and the response observed), or `[INFER]`
(engineering judgment). Contracts in this gate are built on `[DOC]` and
`[TESTED]` claims. Where an `[INFER]` was worth encoding — the SAM-to-Grants.gov
eligibility crosswalk, the Public Inspection lead time — it carries a field
saying so.

## Import result

```text
rows imported                 381
invariant failures              0
urls fetched                    0
sources monitored               0

priority tier      Tier 1 144 | Tier 2 133 | Tier 3 58 | Tier 4 42 | Tier 5 4
jurisdiction       federal 303 | state 57 | private 21
terms status       NO_REVIEW_REQUIRED 223 | TERMS_REVIEW_REQUIRED 148 | HUMAN_REVIEW_ONLY 10
UNKNOWN cells preserved       570
```

`api_capable` is 21 with a further 21 `api_conditional`; `feed_capable` is 57.

## Preserving UNKNOWN required changing the importer

v1's importer validated `has_api`, `has_rss_or_email` and `requires_login`
against a strict Yes / No / UNKNOWN set. v2 writes free text into all three —
"YES", "yes to apply", "yes - API key and paid contract", "no - not
login-gated". Strict validation would have refused every v2 row; coercing the
text to a bare yes/no would have destroyed the detail that decides whether a
source is buildable at all.

So the raw cell is preserved verbatim and a tri-state reading is derived beside
it in a new `*_resolved` field. The resolver denies by default: an unrecognised
value resolves to `conditional`, never to `no`.

```text
resolve_tristate("Yes")                             -> yes
resolve_tristate("no - not login-gated")            -> no
resolve_tristate("yes - API key and paid contract") -> yes
resolve_tristate("sort of")                         -> conditional
resolve_tristate("")                                -> unknown
```

v1's import is semantically unchanged by this: zero per-row differences against
the committed artifact once the three new derived fields are set aside, and
every v1 count identical (55 rows, 13 terms-review, 10 state-scoped, 5
API-capable, 23 UNKNOWN).

## Two defects the v2 import exposed in Gate 90 code

Both were the same shape — a raw string comparison standing in for a decision —
and both were caught by Gate 90's own invariants rather than by inspection.

**1. `human_review_only` without the review flag (22 rows).** The seed service
read `requires_login == "Yes"` literally, so every v2 row phrasing its login
requirement differently was read as not login-gated. The review flag was then
derived from `terms_status` alone, letting a row read `human_review_only: True`
with `legal_terms_review_required: False`. Fixed: login resolves through the
tri-state, and the review flag derives from `human_review_only` rather than
beside it.

**2. `api_capable_count` read 381 rows as four APIs.** Same raw comparison,
different field. Fixed the same way, with `api_conditional` added so a qualified
answer is neither counted as a capability nor lost.

## Reconciliation: v2 supersedes, nothing is deleted

```text
v1 rows                        55
v2 rows                       381
shared source ids              54
v1-only                         1   (FED-SIMPLER)
v2-only                       327
changed                        54
schema match                 True
supersession status  v2_supersedes_v1
v1 deleted                  False
rows merged                     0
UNKNOWN backfilled              0
UNKNOWN introduced by v2        0
UNKNOWN resolved by v2          2
negative rows                  82
negative rows pruned            0
seed-v1 tagged rows            54
```

`FED-SIMPLER` — Simpler.Grants.gov — appears in v1 and not in v2 by source id.
It is not dropped: v1 remains committed and unmodified, and the reconciliation
names the row rather than reconciling it away.

## Negative rows are load-bearing

82 rows record something that does **not** work, and each is worth more than an
absence:

```text
dead        33      trap         3      404          3
shell        3      absence      3      blacklist    1      prohibited   1
```

A "dead" row stops a future pass from re-fetching a URL already proven dead. A
"trap" row records a page that looks like a funding feed and is not. An
"absence" row records a search that was run and found nothing — the most
expensive kind of finding to lose, because nothing about the repository shows it
is missing. None are pruned, and a test asserts every signal still has rows.

## Research-lane provenance

All 381 rows carry a `research lane:` tag naming the pass that produced them:

```text
122  DOI/HHS + SC + philanthropy      56  USDA/HUD/Commerce
 52  seed-v1                          47  DOJ/DHS/ED/DOL/SBA
 39  DOE/EPA/DOT                      28  Research funding
 27  API/monitoring layer              5  API/monitoring layer; Research funding
```

## Artifacts

v1's artifact set was regenerated in place at
`artifacts/source_registry_external/`. v2's was written alongside it at
`artifacts/source_registry_external_v2/` — 381 sources, a 158-row terms-review
queue, 57 state-scoped rows and a 58-row allowability watchlist. Gate 90's
artifacts are not replaced.
