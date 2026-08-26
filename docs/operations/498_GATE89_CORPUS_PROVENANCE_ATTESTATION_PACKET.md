# 498 — Gate 89C: corpus provenance attestation packet

**This is a blank form. Nothing in it is filled in, and nothing in it is a
claim.**

Baseline X reports 185 records. An artefact backs 18 of them. The other 167 rest
on assertion, and four gates of analysis have established that committed data
cannot settle them — the question has to go to whoever produced the corpus.

## How to use this

Answer what you know. **"I don't remember" and "no" are both useful answers, and
neither is a failure.** A blank is worse than either, because a blank cannot be
told apart from an oversight.

The one thing that would be actively harmful is an optimistic answer. Every
figure this campaign has had to walk back — `real_fetch: true`,
`never_synthesized: true`, "40 real ingested grants" — was written in good faith
and turned out to mean less than it appeared to. An honest "generated" upgrades
nothing and costs nothing; an unsupported "fetched" costs a later gate.

## What an answer can and cannot change

**Can:** move specific records from `recorded_asserted` to `recorded_verified` —
but only by pointing at raw transport that still exists. Confirm or refute the
40 suspected placeholder deadlines. Rule out possibilities, which narrows what
future work has to assume.

**Cannot:** create live coverage, monitored sources, or an improvement claim.
Those are facts about a running system, not about history. They are hardcoded
`False` in the validator.

## The single highest-value question

**Do the batch orchestrators' outputs still exist anywhere?**

`la_scaled_federal_grants.json` shipped alongside
`tier1_batch_live_pull_orchestrator_service.py`;
`ta_tier3_foundation_grants.json` shipped alongside `polite_http_fetch_service.py`
and `tier3_batch_live_pull_orchestrator_service.py`. The machinery was committed;
its output was not.

If those runs wrote logs or saved responses that survive on disk, in a scratch
directory, or in a backup, **142 records become recoverable without a single
network call.** That is the largest single lever available and it needs no terms
clearance.

- Did those orchestrators write output to disk? ☐ yes ☐ no ☐ don't remember
- If yes, where, and does it still exist? `________________`

---

# Group 1 — `fixtures/real_grants_corpus/nf13_real_ingested_grants.json`

**40 records. Highest priority.** 38 of them carry `real_fetch: true` with no
ingestion timestamp, no provenance block, no upstream id and no source URL. The
introducing commit contained no transport and no fetch code. All 40 carry the
identical deadline `2026-12-31`, which Gate 87 classified as
`suspected_placeholder`.

- How was this data produced? ☐ fetched live ☐ recorded replay ☐ copied from
  another corpus row ☐ generated ☐ synthesized ☐ transformed ☐ manually
  assembled ☐ mixed ☐ don't remember
- What tool or script collected or produced it? `________________`
- When? `________________`
- From what source system? `________________`
- Do raw API responses survive anywhere? ☐ yes ☐ no ☐ don't remember
  → paths: `________________`
- Are any values copied from another committed corpus row? ☐ yes ☐ no ☐ unsure
- **Are the 40 identical `2026-12-31` deadlines placeholders?** ☐ yes ☐ no
  ☐ don't remember — *a plain "yes" here closes a finding Gate 87 could only
  mark as suspected*
- Is the `eligibility_text` field fetched, or written from the title/agency?
  `________________`
- Are the `FED-001`…`FED-041` opportunity numbers real federal numbers, or
  sequence numbers assigned locally? `________________`
- Are any of these records test doubles? ☐ yes ☐ no → which: `____________`
- Which records, if any, may be treated as verified recorded? `____________`
- Which must remain asserted only? `____________`
- What robots/terms review was completed? ☐ cleared ☐ blocked ☐ unclear
  ☐ not reviewed

---

# Group 2 — `fixtures/real_grants_corpus/la_scaled_federal_grants.json`

**76 records** (reaching Baseline X through the union file). 19 of them carry a
full evidence set — ingestion timestamp, provenance block, upstream id, source
URL — and are the corpus's best-documented asserted records. Committed alongside
`tier1_batch_live_pull_orchestrator_service.py`.

- How was this data produced? ☐ fetched live ☐ recorded replay ☐ copied
  ☐ generated ☐ synthesized ☐ transformed ☐ manually assembled ☐ mixed
  ☐ don't remember
- **Did `tier1_batch_live_pull_orchestrator_service` write logs or saved
  responses? Do they survive?** ☐ yes ☐ no ☐ don't remember
  → paths: `________________`
- When did the batch run? `________________`
- Against what source system? `________________`
- Are the `MM/DD/YYYY` deadlines on 19 of these records as fetched, or
  reformatted locally? `________________`
- Are any values copied from another committed corpus row? ☐ yes ☐ no ☐ unsure
- Any placeholder deadlines? ☐ yes ☐ no → which: `____________`
- Any placeholder eligibility fields? ☐ yes ☐ no → which: `____________`
- Any test doubles? ☐ yes ☐ no → which: `____________`
- Which records may be treated as verified recorded? `____________`
- Which must remain asserted only? `____________`
- Robots/terms review? ☐ cleared ☐ blocked ☐ unclear ☐ not reviewed

---

# Group 3 — `fixtures/real_grants_corpus/ta_mixed_tier13_grants.json` and the tier batches

**168 records in the union file**, which is the deduplicated combination of
`la_scaled_federal_grants.json` (76), `ta_tier3_foundation_grants.json` (66) and
`ta_tier2_state_grants.json` (26). Group 2 covers the first. This group covers
the other two and the union itself.

### `ta_tier3_foundation_grants.json` — 66 records
Committed alongside `polite_http_fetch_service.py` and
`tier3_batch_live_pull_orchestrator_service.py`.

- How was this data produced? `________________`
- **Did the tier-3 orchestrator or the polite fetch service write output that
  survives?** ☐ yes ☐ no ☐ don't remember → paths: `________________`
- Was the "live polite crawl" in the commit message an actual crawl, or the
  capability being added? `________________`
- Robots/terms review for the foundation sources? ☐ cleared ☐ blocked
  ☐ unclear ☐ not reviewed

### `ta_tier2_state_grants.json` — 26 records
No transport and no fetch code in its introducing commit.

- How was this data produced? `________________`
- What tool, when, against what source? `________________`
- Do raw responses survive? ☐ yes ☐ no ☐ don't remember
- Robots/terms review? ☐ cleared ☐ blocked ☐ unclear ☐ not reviewed

### `ta_mixed_tier13_grants.json` — the union
- Is this purely a deduplicated union of the three files above, with no records
  added or values altered? ☐ yes ☐ no ☐ unsure
- If values were altered in the merge, which fields? `________________`

---

# Group 4 — `fixtures/real_grants_corpus/nf14_mixed_corpus.json`

**17 unique records — the only group already backed by an independent
artefact.** That artefact is
`fixtures/real_grants_corpus/nf14_grants_gov_broad_edge_pulls.json`, which landed
in the same commit and carries 33 fields the rows do not. These records are
`recorded_verified`, and this group is asking for confirmation, not rescue.

*(Note: the Gate 89 prompt listed this transport under
`tests/fixtures/grants_gov/`. No such file exists; the path above is the real
one.)*

- Is that transport genuine captured API output, or was it hand-written to match
  the rows? ☐ captured ☐ hand-written ☐ unsure —
  *a "hand-written" answer would* remove *18 records from verified, and is worth
  more than a comfortable "captured"*
- What tool captured it, and when? `________________` (the file records
  `pulled_at: 2026-05-19`)
- Are the 17 rows derived from that pull, or assembled separately and matched up
  afterwards? `________________`
- These rows carry `real_fetch: false` and `fixture: true`. Is that labelling
  accurate? ☐ yes ☐ no
- Robots/terms review for that pull? ☐ cleared ☐ blocked ☐ unclear
  ☐ not reviewed

---

# Group 5 — `tests/fixtures/grants_gov/nf_seed_2026_fed_021_samhsa_sm_26_024.json`

**The circular transport.** Its `_meta` names
`nf13_real_ingested_grants.json` as its `source_of_values` and describes itself
as "a record of what the repo already asserts". Added 2026-08-24, two months
after the row it appears to corroborate. Classified `recorded_circular`.

- Is that self-description accurate — were its values transcribed from the
  corpus row? ☐ yes ☐ no ☐ unsure
- Does any *genuine* captured response for SAMHSA `SM-26-024` survive anywhere?
  ☐ yes ☐ no ☐ don't remember → paths: `________________`
- Is `12/31/2026` the real close date for SM-26-024, or inherited from the
  placeholder? ☐ real ☐ inherited ☐ don't know

---

# Group 6 — `fixtures/real_grants_corpus/nf15_eligibility_reingest_pulls.json`

**2 evidence pull records.** Carries no deadline field.

- How was this produced? `________________`
- Does raw transport for the re-ingest survive? ☐ yes ☐ no ☐ don't remember
- Are these genuine captured responses or reconstructions? `________________`

---

# Signature block

```text
attestation_id        ____________________
attested_at           ____________________  (ISO-8601)
attested_by           ____________________
attestation_scope     ____________________  (which groups above this covers)

collection_method     ____________________  (live_fetch | recorded_replay |
                                             copied_from_another_corpus_row |
                                             generated | synthesized |
                                             transformed | manually_assembled |
                                             mixed | unknown)
collection_window     ____________________
source_systems        ____________________
fetch_tool_or_script  ____________________

raw_transport_available        ☐ yes ☐ no
raw_transport_artifact_paths   ____________________
source_terms_reviewed          ☐ yes ☐ no
source_terms_status            ☐ reviewed_cleared ☐ reviewed_blocked
                               ☐ reviewed_unclear ☐ not_reviewed ☐ unknown
live_fetch_performed           ☐ yes ☐ no

field_mapping_summary          ____________________
deadline_source                ____________________
eligibility_source             ____________________

provenance_limitations         ____________________  (required — see below)
known_placeholders             ____________________
known_circular_sources         ____________________

records_to_exclude_from_verified      ____________________
records_allowed_for_verified_upgrade  ____________________

human_statement
____________________________________________________________
____________________________________________________________
```

## Notes on three fields that decide the outcome

**`provenance_limitations`** — leaving this blank does not produce a stronger
attestation, it produces a weaker one. The validator records
`attestation_states_no_limitations` as a limitation in its own right. Every
honest account of six-week-old data collection has gaps; naming them is what
makes the rest credible.

**`raw_transport_artifact_paths`** — this is the only field that can move a
record to `recorded_verified`. Setting `raw_transport_available: yes` without a
path is rejected as `contradictory_attestation`, not accepted as a partial win.
Naming the known-circular SAMHSA fixture here is also rejected: Gate 87
established it cannot corroborate its own source.

**`records_allowed_for_verified_upgrade`** — records named here but also listed
in `records_to_exclude_from_verified` are rejected as contradictory. Records
named here that Gate 87 flagged as suspected placeholders are rejected unless
you also list them under `known_placeholders` — an attestation confirming a
suspicion is accepted; one silently overriding it is not.

## Where to put the completed form

A new doc, `docs/operations/NNN_CORPUS_PROVENANCE_ATTESTATION_SIGNED.md`, and
say so in the gate prompt that acts on it. Do not edit this file — it stays
blank as the template. Do not edit `499`, which records that no attestation has
been supplied.
