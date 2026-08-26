# 493 — Gate 88A: corpus provenance flag survey

Audit of whether `recorded_records: 162` is supported by committed evidence.
Committed and local data only. Nothing was fetched.

## Verdict

**18 of 185 records have independent committed evidence of a recording. The
other 167 rest on assertion.**

`recorded_records: 162` is not wrong — those records are not synthetic, and
nothing here says any of them is fake. But it was answering a weaker question
than it appeared to. It counts records whose *flags* say they were fetched, and
this gate found that 38 of them carry no fetch artefact of any kind.

## What the flags are actually worth

### `never_synthesized: true` carries no weight at all

It is set on all 185 records, and it is a hardcoded literal:

```python
# source_fetch_adapter_contract_service.py
"never_synthesized": True,
```

Assigned unconditionally on every payload the adapter builds. It is not derived
from anything, so it cannot distinguish one record from another. This directly
answers the survey question: **yes, code assigns a provenance flag by default.**

### `real_fetch: true` is guarded, but the guard checks flags against flags

`real_fetch_honest_labeling_guard_service` (Sprint 313) is fail-closed and real:

```text
fixture payload            => real_fetch must not be true
real_fetch: true           => fetch_mode must be "live"
real_fetch: true           => search_live AND detail_live must be true
```

That is a genuine guard against one specific mislabeling, and it is worth
having. But every input it inspects is a boolean on the same payload. It cannot
distinguish a payload where a fetch happened from one where four booleans were
set together. It proves internal consistency, not that an HTTP request occurred.

**38 records carry `real_fetch: true` and no `ingested_at`, no `provenance`
block, no upstream id, and no `source_url`.** All 38 are `nf13-real-fed` — the
same batch Gate 87 found carrying 40 identical deadlines.

## Evidence actually present, by batch

Tuple is `(ingested_at, provenance block, upstream id, source_url)`:

| batch | n | evidence |
| --- | --- | --- |
| `la-real` | 36 | 32 × all four; 4 × source_url only |
| `nf13-real-fed` | 40 | **38 × none**; 1 × upstream id; 1 × source_url |
| `nf14-mixed-*` | 17 | 17 × upstream id, **plus an independent transport** |
| `ta2-real` | 26 | 23 × checked+provenance+url; 3 × provenance+url |
| `ta3-real` | 66 | 51 × checked+provenance+url; 15 × provenance+url |

Corpus-wide: 106 have `ingested_at`, 124 a provenance block, 50 an upstream id,
129 a `source_url`, and **38 have none of the four**.

## The one independent artifact

`fixtures/real_grants_corpus/nf14_grants_gov_broad_edge_pulls.json` — 466 KB of
raw Grants.gov transport:

```text
schema_version       nf14_grants_gov_broad_edge_pulls_v1
pull_count           17
pulled_at            2026-05-19
fetch_mode_recorded  live
```

It is independent of the corpus rows, and this is checkable rather than assumed.
The test is **does the artifact carry information the corpus row could not have
supplied**:

- 33 fields in the transport are absent from the corresponding row
- among them `revision: 7`, `publisherUid: 1643657692`, `flag2006: N`,
  `listed: L`, and a `modifiedComments` narrative about a due-date change

A row cannot be the source of data it does not contain, so derivation runs
transport → row. The file also carries no `source_of_values`, no
`expected_grant_id`, and no "transcribed" or "repo-recorded" marker.

It covers 16 distinct upstream ids, matching all 16 that the 17 nf14 rows carry.

**It also corroborates one record outside its own batch.** `la-real-014`
(upstream id 361742) appears in the pull as `HHS-2026-ACF-ANA-NB-0116`,
"Native American Language Preservation and Maintenance-Esther…", matching the
corpus row's number and title. The same opportunity was recorded twice, and the
independent copy backs the asserted one.

That gives 18 records with independent evidence: 17 nf14 plus `la-real-014`.

## The one circular artifact

`tests/fixtures/grants_gov/nf_seed_2026_fed_021_samhsa_sm_26_024.json`, covered
in Gate 87A. Its `_meta` names `nf13_real_ingested_grants.json` as its
`source_of_values` and states it is "a record of what the repo already asserts".
Its values were copied from the row it appears to corroborate.

It is the only artifact in the corpus that declares such derivation, and Gate 77B
deserves credit for labelling it — the label is the only reason the circle is
visible. It classifies as `recorded_circular`.

## Answers to the survey questions

- **Independent committed evidence of fetch/recording?** 18 records — 17 nf14
  and `la-real-014`, all via the one independent transport.
- **Only assert fetch through boolean flags?** 38, all `nf13-real-fed`.
- **Synthetic by self-declaration?** None. No record declares itself synthetic;
  `fixture: true` on the 17 nf14 rows means *derived from a recorded pull*, which
  is honest labelling of a recording, not of a synthesis.
- **Circular recorded fixtures?** One, and it says so itself.
- **Corpus files trustworthy as recorded data?** `nf14_mixed_corpus.json`, and
  only because its transport is committed alongside it.
- **Asserted-but-unverified?** `nf13_real_ingested_grants.json` most acutely
  (38 records with nothing), and `la_scaled_federal_grants.json`,
  `ta_tier2_state_grants.json`, `ta_tier3_foundation_grants.json` more mildly —
  those carry timestamps, provenance blocks and URLs, but no transport artifact.
- **Does code assign provenance flags by default?** Yes.
  `never_synthesized: True` is a hardcoded literal on every adapter payload.
- **How should Baseline X classify?** `recorded_verified` (18),
  `recorded_circular` (1), `recorded_asserted` (166), with `evidence_level`
  carrying the gradation inside the asserted group.

## A distinction this survey insists on

`recorded_asserted` is not an accusation. It spans a very wide range:

```text
upstream_identified   a check timestamp plus an id the repo did not mint   31
checked_metadata      a timestamp plus a provenance block or URL           74
metadata              a provenance block or URL, never checked             23
flags_only            booleans and nothing else                            38
```

A record at `upstream_identified` is in far better shape than one at
`flags_only`, and collapsing them would repeat the mistake this gate exists to
correct. The status says what is *proven*; the evidence level says how close the
rest comes.

## Two axes will disagree, on purpose

Gate 85's `corpus_summary` classifies by *fetch mode* — 162 recorded, 23
unknown, 0 synthetic, 0 live. Gate 88 classifies by *evidence strength*. The 23
`no_live_nofo` records are `unknown` on the first axis and `recorded_asserted`
on the second, because they do record a check that happened; what they lack is
opportunity content, which Gate 85 already counts separately as
`honest_empty_records`.

Both axes stay, both stay labelled, and neither is edited to match the other.
Gate 85's composition figures are unchanged by this gate.

## What is missing

No amount of further analysis of committed data will move the 166. Resolving
them needs a transport artifact per record — a recording that carries data the
row cannot supply — and producing one requires a fetch, which is blocked behind
terms clearance.
