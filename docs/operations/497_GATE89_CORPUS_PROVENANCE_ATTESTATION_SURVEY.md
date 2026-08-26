# 497 — Gate 89A: local provenance trail survey

What the repository can establish about where the corpus came from, before
anybody is asked a question. Local evidence only. Nothing was fetched.

## The rule this survey holds itself to

**Git history establishes when a file entered the repository. It does not
establish that the data was fetched.** A commit message saying "40 real ingested
grants" is a claim by its author, not evidence — the same category of thing as
`real_fetch: true`, and Gate 88 already declined to treat that as proof.

What a commit *can* establish is whether raw transport landed alongside the
rows. That is a fact about content, not about narrative, and it is the only
thing this survey draws conclusions from.

## The provenance trail, per file

| Corpus file | Records in Baseline X | Introduced | Transport in that commit | Fetch code in that commit |
| --- | --- | --- | --- | --- |
| `nf14_mixed_corpus.json` | 17 unique | `a742b6a` 2026-06-22 | **yes** | — |
| `nf14_grants_gov_broad_edge_pulls.json` | 0 (it *is* the transport) | `a742b6a` 2026-06-22 | — | — |
| `nf13_real_ingested_grants.json` | 40 | `1a8978a` 2026-06-22 | **no** | **no** |
| `la_scaled_federal_grants.json` | 76 (via the union file) | `cd9499f` 2026-06-29 | no | yes |
| `ta_tier3_foundation_grants.json` | 66 (via the union file) | `ec59481` 2026-06-30 | no | yes |
| `ta_tier2_state_grants.json` | 26 (via the union file) | `12e0ae3` 2026-06-30 | no | no |
| `ta_mixed_tier13_grants.json` | 168 (union of the three above) | `ec59481` 2026-06-30 | no | — |
| `nf15_eligibility_reingest_pulls.json` | 0 (2 evidence pulls) | `ac2e0d8` 2026-06-22 | n/a | — |
| `tests/fixtures/grants_gov/nf_seed_2026_fed_021_samhsa_sm_26_024.json` | 0 (circular transport) | `f15f9a5` 2026-08-24 | — | — |

`ta_mixed_tier13_grants.json` is the deduplicated union of the la, tier-2 and
tier-3 files. Its provenance is inherited from those three and adds nothing of
its own.

## Files that already have independent raw transport

One: **`nf14_mixed_corpus.json`**.

Its transport, `nf14_grants_gov_broad_edge_pulls.json`, landed in the *same
commit* (`a742b6a`) as the rows it produced. Gate 88 established independence by
content — the transport carries 33 fields the rows do not, including `revision`,
`publisherUid`, `flag2006` and a `modifiedComments` narrative — and the shared
commit is consistent with that direction of derivation.

This backs 18 records: the 17 nf14 rows plus `la-real-014`, whose upstream id
361742 appears in the pull with matching opportunity number and title.

## Files with circular evidence

One: **`tests/fixtures/grants_gov/nf_seed_2026_fed_021_samhsa_sm_26_024.json`**,
added by `f15f9a5` (2026-08-24, "Make NativeForge federal corpus tests
hermetic"). Its `_meta` names `nf13_real_ingested_grants.json` as its
`source_of_values`. Covered in Gates 87A and 88A.

Note the dates: the corpus row is from June, the transport from late August. The
transport post-dates the data it appears to corroborate by two months, which is
consistent with its own self-description as a reconstruction.

## Files with asserted flags only

**`nf13_real_ingested_grants.json`** — 40 records, the weakest position in the
corpus. Its introducing commit `1a8978a` touched 19 files and contained no
transport, no pull artifact, and no fetch code. Its message asserts "40 real
ingested grants"; nothing in the commit content supports that.

38 of those 40 records carry `real_fetch: true` with no ingestion timestamp, no
provenance block, no upstream identifier and no source URL.

**`ta_tier2_state_grants.json`** — 26 records. No transport and no fetch code in
`12e0ae3`.

## Files with git history but no source-fetch evidence — a distinction worth keeping

Two files sit in a middle position that Gate 88's classification does not
capture, and that is worth naming because it changes what to *ask*, not what to
conclude:

- **`la_scaled_federal_grants.json`** (`cd9499f`) shipped
  `tier1_batch_live_pull_orchestrator_service.py` and
  `tier1_batch_live_pull_gate_verification_service.py`.
- **`ta_tier3_foundation_grants.json`** (`ec59481`) shipped
  `polite_http_fetch_service.py` and
  `tier3_batch_live_pull_orchestrator_service.py`.

**Fetch machinery was committed. Fetch output was not.**

This does not upgrade either file. Committing a tool that could perform a fetch
is not evidence that a fetch occurred, any more than a boolean is — and Gate 89
upgrades nothing. But it makes a specific, answerable question available: *did
those orchestrators write logs or artifacts that still exist and could be
committed?* If they did, the la and tier-3 batches are recoverable without any
network call. That question is in the packet.

No committed fetch logs exist anywhere in the repository for these batches. The
only `.log` files in history are Playwright, pytest and ruff output.

## Files requiring human or operator attestation

All of them except `nf14_mixed_corpus.json`:

```text
nf13_real_ingested_grants.json        40 records   highest priority
la_scaled_federal_grants.json         76 records   ask about orchestrator output
ta_tier3_foundation_grants.json       66 records   ask about orchestrator output
ta_tier2_state_grants.json            26 records
ta_mixed_tier13_grants.json           derived; inherits from the three above
nf15_eligibility_reingest_pulls.json  2 evidence pulls
```

## What must be answered to upgrade any asserted record

An upgrade to `recorded_verified` requires evidence of the kind Gate 88 defined:
an artefact carrying information the row could not have supplied. An attestation
can supply that in exactly two ways:

1. **Point at raw transport that exists and can be committed** — orchestrator
   output, an HTTP trace, a saved API response. This is the only route that
   produces `recorded_verified`.
2. **State the collection method precisely enough to rule out the alternative** —
   which produces at most a *limited* attestation, and does not verify records.

Everything else narrows the question without settling it. Specifically:

- Was each batch fetched, generated, copied, transformed, or hand-assembled?
- Which tool ran, when, against which source system?
- Do raw responses survive anywhere outside the repository?
- Are any deadline or eligibility values placeholders? (Gate 87 suspects 40
  deadlines are; an attestation can confirm or refute that directly.)
- Are any records test doubles?
- Which records may be treated as verified, and which must stay asserted?
- What robots/terms review was completed?

## A correction to the gate's file list

The Gate 89 prompt lists
`tests/fixtures/grants_gov/nf14_grants_gov_broad_edge_pulls.json`. That path does
not exist. The file is at
`fixtures/real_grants_corpus/nf14_grants_gov_broad_edge_pulls.json`, and the
packet asks about it there. No file was created at the listed path — inventing
one to match a prompt would be exactly the kind of fabrication this gate forbids.

## What this survey does not do

It upgrades nothing. Gate 88's classifications stand unchanged: 18 verified, 166
asserted, 1 circular. This survey establishes only what questions are worth
asking and which answers would move which records.
