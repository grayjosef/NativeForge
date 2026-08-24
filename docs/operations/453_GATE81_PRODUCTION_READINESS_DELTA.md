# 453 — Gate 81H: Production readiness delta

Gate 79 built the exclusion contract. Gate 79B wired it into discovery and
scoring. Gate 81 builds the layer that can finally *produce* the evidence those
contracts demand — from notice text, with citations.

Nothing was fetched, no source was identified or seeded, no coverage is claimed.

## NOFO extraction: now

| | Before | After |
| --- | --- | --- |
| Source-agnostic section detection | no — Block 09 was pinned to one opportunity and one fixture path | **yes** |
| Character spans on extracted claims | no | **yes**, invariant-checked |
| Eligibility restricted to eligibility sections | no | **yes** |
| Date precision preserved | no | **yes** (`day` / `month`, plus hedge markers) |
| Missing raw text | silent empty result | **blocked**, with a reason |
| Parser vs eligibility confidence | conflated | separate fields, never merged |

Two parsing defects found and fixed during the build, both of which would have
mattered on real notices:

- **Wrapped prose read as headings.** A short unpunctuated line — the last line
  of a wrapped paragraph — started a new section. In one fixture that split the
  eligibility section in half, which can hand the remaining eligibility rules to
  a different section kind and drop them from the only text allowed to support
  an eligibility conclusion.
- **Wrapped phrases were invisible.** `federally recognized\ntribes` did not
  match while the canonical analyser, which collapses whitespace, found it — so
  the parser and the exclusion service disagreed about the same sentence.

## Eligibility parser: now

| | Before | After |
| --- | --- | --- |
| Keyword outside eligibility context | could support eligibility | **cannot**, structurally |
| Citation for an exclusion | required but unobtainable | **produced**, span + quote |
| Exclusive list of non-Native classes | invisible; tribes came back "not supported" | **excludes**, with evidence |
| Explicit negation of a named class | read as **eligible** | **excluded_by_evidence** |
| Recognition tiers | separate | still separate, both directions tested |
| Trust land | — | preserved as a restriction, never eligibility |

The negation case is the most consequential fix in this gate. *"Federally
recognized tribes are not eligible under this program"* names the class, and
naive matching returned `eligible` — telling a tribe to spend weeks on a
programme that had already ruled them out in writing.

Vocabulary: **superset, not fork.** `APPLICANT_CLASSES` (8) is a strict subset
of `PARSER_APPLICANT_CLASSES` (12), asserted by test. The four non-Native
classes are dropped before anything reaches the exclusion contract.

## Amendment detector: now

| | Before | After |
| --- | --- | --- |
| Notice status axis | did not exist | 9 statuses, projected onto freshness |
| Amended without evidence | possible | **unknown**, never amended |
| Cancelled / withdrawn | no representation | visible, marked, non-current |
| Deadline extension evidence | hand-authored | emitted in the kinds Gate 76D accepts |
| Supersession | Gate 76D only | unchanged — **delegated**, not re-decided |

`FRESHNESS_STATES` and both evidence-kind sets are untouched. The projection is
invariant-guarded so no non-current status can reach a current freshness state.

## Source coverage: now

**Unchanged. Zero.**

```text
Live SC source coverage:   NONE
Live federal coverage:     NONE
Sources monitored:         0
Notices parsed from live:  0
SC coverage complete:      NOT CLAIMED
65% improvement:           NOT CLAIMED
```

Gate 81 built a parser. It identified no source, fetched nothing, and seeded
nothing. All seven fixtures are synthetic and say so on their first line. A test
asserts no Gate 81 module references `requests`, `httpx`, `urllib.request` or
`aiohttp`, and the Gate 77B hermetic guard and Gate 78E write-back guards are
untouched.

## Native customer value

The chain now runs end to end from notice text to a scored, per-class answer:

1. A notice is read; only its eligibility section can support eligibility.
2. "Tribal communities" in the purpose paragraph earns nothing.
3. "Eligible applicants are units of local government" is read as exclusive, and
   every Native class is excluded **with the sentence attached**.
4. The exclusion carries a citation, so it survives Gate 79's contract.
5. The opportunity stays visible and stays in the corpus.
6. It stops counting as eligible coverage for the excluded class, and counts as
   negative intelligence instead.

That is the answer this product exists to give: *this looks relevant, your
applicant class appears excluded, and here is the sentence.* Before Gate 81 the
last clause was not obtainable from text at all.

## Owner-blocked

- **Robots/terms review** for the Gate 78R sources. Still the gate on any fetch.
- **Primary-source verification.** No real notice has been parsed. The Gate 78R
  eligibility strings remain `eligibility_verified: false`, read from index
  pages rather than primary notices. The machinery to publish a cited exclusion
  now exists; the SC claims behind it are still unverified.
- Real `OIDC_*` credentials, managed Postgres, migration 0028, backup/restore,
  pen test.

## Engineering-blocked

- A real notice corpus to exercise phrase and cue coverage. The lists are
  conservative and English-only; unrecognised phrasing yields
  `not_supported_by_evidence` or `human_review_required` rather than a wrong
  answer, but recall is unmeasured and cannot be measured without a corpus.
- PDF and HTML ingestion. This module takes text; something must produce it.
- Threading `applicant_class` from a customer org profile into the scorer
  (carried over from Gate 79B).
- Retiring the two Gate 79B compatibility lane vocabularies.
- Scheduler (Gate 80) — still correctly blocked; zero sources are terms-cleared.

## Controlled customer pilot delta

**None.**

```text
Controlled customer pilot: NO_GO
Production rollout:        NO_GO
Customer login live:       NO
Production storage live:   NO
Customer persistence:      NO
Pen-test passed:           NO
```

What genuinely changed: the product can now derive cited eligibility and
exclusion from a notice instead of accepting them from a caller, and it can tell
an amended notice from a cancelled one without guessing. What has not changed:
it has never done either to a real notice.
