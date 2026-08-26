# 494 — Gate 88B: corpus provenance evidence contract

`corpus_provenance_evidence_service` (`nf_corpus_provenance_evidence_v1`) asks of
a record what Gate 87 asked of a deadline: is there committed evidence behind
it, or only an assertion?

## The rule the module is built on

**No combination of booleans on a record can make that record verified.**

Two flags explain why.

`never_synthesized: true` is set on all 185 records and is a hardcoded literal
in `source_fetch_adapter_contract_service` — assigned unconditionally to every
payload the adapter builds. It cannot distinguish one record from another, and
the classifier names it as such via
`never_synthesized_is_set_unconditionally_by_the_adapter`.

`real_fetch: true` is genuinely guarded.
`real_fetch_honest_labeling_guard_service` (Sprint 313) is fail-closed and
enforces that it implies `fetch_mode == "live"`, `search_live` and
`detail_live`. That guard catches a fixture mislabelled as a live fetch and is
worth having. But every input it reads is a boolean on the same payload, so it
proves internal consistency — not that a request happened. A test pins exactly
that: a payload with all four flags and no artefact passes the guard.

## Statuses

| Status | Meaning | Counts as recorded | Counts as verified |
| --- | --- | --- | --- |
| `recorded_verified` | an independent artefact backs it | yes | **yes** |
| `recorded_circular` | an artefact exists but is derived from the record | yes | no |
| `recorded_asserted` | flags, and often metadata, but no artefact | yes | no |
| `synthetic_declared` | the record declares synthesis | no | no |
| `demo_synthetic` | demo scaffolding | no | no |
| `unknown_provenance` | not enough to place it | no | no |
| `missing_provenance` | nothing at all | no | no |

`live` is deliberately absent from the vocabulary. Nothing in this repository
can produce a live record and this gate creates no runtime proof of one, so
`record_counts_as_live` is a constant `False` rather than a status that could be
reached by mistake.

## Evidence levels

Ordered weakest to strongest:

```text
none                  nothing
flags_only            booleans and nothing else
metadata              a provenance block or source URL, never checked
checked_metadata      an ingestion timestamp plus a block or URL
upstream_identified   a timestamp plus an identifier the repo did not mint
circular_artifact     a transport that names the record as its source
independent_artifact  a transport carrying data the record cannot supply
```

The status says what is *proven*; the level says how close the rest comes. This
matters because `recorded_asserted` spans a very wide range, and collapsing it
would repeat the error the gate exists to correct in the opposite direction.

## What makes an artefact independent

**It carries information the corpus row could not have supplied.** A row cannot
be the source of data it does not contain, so the direction of derivation is
settled by asymmetry rather than by assertion.

`nf14_grants_gov_broad_edge_pulls.json` carries 33 fields absent from its rows —
`revision`, `publisherUid`, `flag2006`, `listed`, and a `modifiedComments`
narrative about a due-date change. A test asserts that gap stays above 20
fields, so if the artefact ever thins out, independence has to be re-established
some other way rather than silently assumed.

The converse is a fixture naming the row as its `source_of_values`. That is
`recorded_circular`: it confirms the repository is internally consistent and
nothing more.

## The classifier does no I/O

Deciding whether an artefact is independent means reading it, and reading is the
caller's job. `classify_corpus_provenance` takes already-resolved artefact
identifiers. A test greps the module source for `open(`, `Path(`, `read_text`
and every HTTP client.

The reading happens in `discovery_baseline_x_service.load_independent_transport_ids`,
which also refuses to treat a file as independent if its `_meta` carries a
`source_of_values` — checked rather than assumed, so a future circular fixture
dropped into that path does not quietly promote records to verified.

## Precedence

1. `declared_demo` / `declared_synthetic` — a record saying what it is outranks
   any inference about it, including an artefact.
2. `independent_artifact` → `recorded_verified`.
3. `circular_artifact` → `recorded_circular`.
4. Otherwise `recorded_asserted` at the highest level the evidence supports, or
   `missing_provenance` when there is nothing.

## Invariants

`corpus_provenance_invariant_failures` enforces:

- `fabricated` is `False` and `record_counts_as_live` is `False`
- both vocabularies are closed
- `recorded_verified` requires `independent_artifact` **and** must name the
  artefact in its evidence reasons
- `record_counts_as_verified_recorded` only ever accompanies `recorded_verified`
- a circular artefact can never be counted as verified, and must state why
- **`flags_only` evidence can never reach a verified status**
- `missing_provenance` is never counted as recorded
- every classification carries a record id

## What a verdict may not do

```text
records_removed   always 0
records_hidden    always 0
fabricated        always False
```

Nothing is deleted, hidden, or rewritten. `recorded_asserted` means a claim has
not been corroborated — not that it has been refuted, and not that any record is
fake.
