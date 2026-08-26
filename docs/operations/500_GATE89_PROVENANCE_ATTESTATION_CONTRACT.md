# 500 — Gate 89B: provenance attestation contract

`corpus_provenance_attestation_service` (`nf_corpus_provenance_attestation_v1`)
validates an operator's account of where the corpus came from, before anything
acts on it.

## Why a human statement gets validated at all

Because the failure this campaign keeps finding is not dishonesty — it is
optimism recorded as fact.

`real_fetch: true`, `never_synthesized: true`, and a commit message reading
"40 real ingested grants" were all written in good faith. Each turned out to
mean less than it appeared to. An attestation is the same category of artefact:
a person's recollection, offered sincerely, about work done weeks earlier.

So it is held to the same standard as a flag. Sincerity is assumed; sufficiency
is checked.

## Statuses

| Status | Meaning | May verify records |
| --- | --- | --- |
| `valid_complete_attestation` | raw transport named, recording method, records named, no gaps | **yes** |
| `valid_limited_attestation` | internally sound but incomplete or without transport | no |
| `insufficient_attestation` | a core field is absent | no |
| `contradictory_attestation` | says something committed evidence refutes | no |
| `unknown_attestation` | absent or unrecognisable | no |

## What it cannot buy, at any completeness

```text
creates_live_coverage        always False
creates_source_monitoring    always False
permits_improvement_claim    always False
```

Constants, not computed values, and an invariant fails if any is flipped. Live
coverage and monitoring are facts about a system running now; an account of how
data was collected in the past cannot produce one, however complete.

## Verification requires transport

`recorded_verified` is Gate 88's bar — an artefact carrying information the
corpus row could not have supplied — and this module does not soften it. An
attestation reaches `valid_complete_attestation` only with all of:

1. `raw_transport_available: true`
2. at least one path in `raw_transport_artifact_paths`
3. a `collection_method` in `RECORDING_METHODS`
4. at least one record in `records_allowed_for_verified_upgrade`
5. no unanswered required field

"Yes, it was fetched" with nothing to point at is `valid_limited_attestation`.
It is still useful — it rules things out and narrows what future work must
assume — but it verifies nothing.

## Deny by default on the method field

`RECORDING_METHODS` is `{live_fetch, recorded_replay}` and verification requires
**membership**, not absence from `NON_RECORDING_METHODS`.

A first cut of this validator asked the negative question. `unknown`, `mixed`
and any value nobody anticipated all passed it, which means a typo in one form
field could have verified a record. That is Gate 79B's lesson — derive the
allowed set, never subtract the denied one — arriving in a place it was not
expected.

`transformed`, `manually_assembled` and `mixed` are deliberately outside the
recording set. Each may well sit on top of a real fetch, but the attestation has
to say which, and a follow-up naming the underlying method costs one line.

## A blank and a "no" are different answers

The packet promises this and the validator honours it:

- an **absent key**, `None`, or an empty string → unanswered, listed in
  `missing_fields`
- a key present with an **empty list** → answered. `known_placeholders: []`
  means "I checked, there are none"

Counting an empty list as a gap would penalise the most careful respondent, who
checked and found nothing, over the one who left the field out.

Core fields — `attestation_id`, `attested_by`, `attested_at`, `corpus_files`,
`collection_method`, `human_statement` — are held to the stricter reading: an
attestation naming no corpus files has no scope, so an empty collection there is
`insufficient_attestation`.

## Contradictions are rejected, not averaged

An attestation that conflicts with committed evidence is refused outright rather
than blended with it:

| Contradiction | Why |
| --- | --- |
| cites the SAMHSA fixture as raw transport | Gate 87 showed it names the corpus row as its own `source_of_values` |
| `raw_transport_available: true` with no path | claims evidence while naming none |
| `live_fetch_performed: true` with a generated method | the two cannot both be true |
| a record both excluded and offered for upgrade | the attestation disagrees with itself |
| offers a suspected-placeholder record for upgrade | overturns a committed finding without evidence |

That last check is deliberately **asymmetric**. An attestation *confirming* a
suspected placeholder is accepted — that is new information and closes a finding
Gate 87 could only mark as suspected. An attestation silently *denying* one is
not enough to overturn it. Confirmation is evidence; denial is a claim.

## Limitations are required

Leaving `provenance_limitations` blank does not produce a stronger attestation.
The validator records `attestation_states_no_limitations` as a limitation in its
own right. Every honest account of weeks-old data collection has gaps, and
naming them is what makes the rest credible.

## Invariants

`attestation_invariant_failures` enforces:

- `fabricated` is `False`; the three runtime constants are `False`
- the status vocabulary is closed
- `permits_verified_upgrade` only under `valid_complete_attestation`
- no `records_eligible_for_upgrade` without permission
- a complete attestation must have named transport
- an excluded record can never appear as upgradable
- a rejection must state its reason

## No I/O

The validator opens no files and makes no requests — a test greps its source for
`open(`, `Path(`, `read_text` and every HTTP client. `committed_evidence` is
passed in by the caller, so what the repository knows and what the attestation
claims stay separable and separately auditable.
