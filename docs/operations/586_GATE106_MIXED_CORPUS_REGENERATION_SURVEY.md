# 586 — Gate 106A: mixed corpus regeneration survey

Every fact below was reproduced by running the tree before anything was mutated.
The fixture is untouched at the time of writing.

## Headline

**Regeneration is blocked.** Not because the Gate 105 correction is unsafe — it
is safe and fully attributable — but because regenerating the manifest would
also write synthesized prose into the `eligibility_text` of the one row in the
corpus that is honestly empty.

The cached fixture is not simply stale. On that row it is *more honest than
current derivation*, and overwriting it would trade a truthful blank for a
plausible-looking sentence.

## Which service builds the fixture

`src/nativeforge/services/mixed_corpus_builder_service.py`

```text
build_mixed_real_corpus(use_cached_manifest=True)   reads the committed manifest
build_mixed_real_corpus(use_cached_manifest=False)  derives from source fixtures
build_mixed_corpus_manifest()                       wraps the fresh derivation
```

Sources are `load_nf13_real_ingested_grants()` (40 tribal-federal rows) and
`PULLS_PATH` (recorded Grants.gov pulls). Both are recorded fixtures. Nothing
fetches.

No script or test in the repository calls `build_mixed_corpus_manifest()`, so
the committed file has no live regeneration path and was produced once,
historically. This gate supplies the attestation that a regeneration would need.

## Verified facts

```text
cached default                  use_cached_manifest = True          confirmed
fresh derivation deterministic  3 runs, identical sha256            confirmed
rows cached / fresh             57 / 57                             confirmed
row ids and ordering            identical, no additions or removals confirmed
differing fields                5, across 4 rows                    confirmed
positives removed               0                                   confirmed
top-level manifest counts       identical                           confirmed
```

Determinism matters here: a non-deterministic build could not be attested at
all, because "what changed" would not be a stable question.

## The five differing fields

### Three are the Gate 105 correction — expected, attributable, safe

```text
nf14-mixed-edge-10           applicant_types_include_tribal  False -> True
nf14-mixed-label_spread-14   applicant_types_include_tribal  False -> True
nf14-mixed-label_spread-15   applicant_types_include_tribal  False -> True
```

Each already carried `tribal_eligible: True` while claiming applicant types
exclude Tribes. Each has eligibility text naming Indian tribes or tribal
governments. The change makes the record agree with its own source text and adds
no claim the text does not carry. This is precisely what Gate 105 fixed and what
this gate exists to absorb.

### Two are pre-existing drift on nf13-real-fed-025 — and they are the blocker

```text
eligibility_text                ''    -> 'Federal grant program: EPA - General
                                          Assistance Program (GAP). No posted
                                          NOFO on Grants.gov at ingest
                                          (no_live_nofo).'
applicant_types_include_tribal  None  -> False
```

## Why nf13-real-fed-025 blocks regeneration

The raw NF-13 record is explicit about itself:

```text
eligibility_text                ''      nothing was posted, so nothing recorded
synopsis                        'Federal grant program: EPA - General Assistance
                                 Program (GAP). No posted NOFO on Grants.gov at
                                 ingest (no_live_nofo).'
empty_honestly                  True
never_synthesized               True
no_live_nofo                    True
real_fetch                      False
applicant_types_include_tribal  None
```

Derivation then does this:

```python
if parsed.get("eligibility_text") and not out.get("eligibility_text"):
    out["eligibility_text"] = parsed["eligibility_text"]
```

`parsed["eligibility_text"]` comes from the **synopsis**, and this row's synopsis
is not eligibility language at all — it is an administrative note recording that
**no NOFO exists**. Regeneration would copy that sentence into the field whose
meaning is "what the source says about who may apply".

Reproduced end to end: derivation writes the sentence into `eligibility_text`
while the row **still carries `empty_honestly: True` and
`never_synthesized: True`**. The row's own honesty flags become false statements
about the row.

That field is not inert. It is what `derive_explicit_source_evidence` and the
canonical Tribal classifier read. Populating it with synthesized prose puts
manufactured text directly into the evidence path — the exact failure the Gate 95
raw-payload boundaries, the Gate 87 deadline-provenance work and the Gate 105
no-fabrication rule all exist to prevent.

The second change compounds it: `applicant_types_include_tribal` goes from `None`
to `False`. Unknown becomes an affirmative negative, on a tribal-federal row
whose source genuinely does not say. `None` is the honest answer.

### Exposure is exactly one row

```text
NF-13 rows total                                     40
rows with empty eligibility_text AND a synopsis       1   nf13-real-fed-025
rows marked no_live_nofo                              1   nf13-real-fed-025
rows marked empty_honestly                            1   nf13-real-fed-025
```

The guard `not out.get("eligibility_text")` means only a row with *nothing*
recorded can be overwritten. There is one such row, and it is the one row that
documents an honest absence. The defect is narrow and it lands on the worst
possible target.

## Answers to the survey questions

```text
which service builds it            mixed_corpus_builder_service
deterministic regeneration path    yes, build_mixed_corpus_manifest()
fresh derivation deterministic     yes, verified over three runs
use_cached_manifest defaults true  yes
exact before/after differences     5 fields, 4 rows, listed above
caused by Gate 105                 3 (the tribal bridge correction)
pre-existed Gate 105               2 (both on nf13-real-fed-025)
nf13-real-fed-025 understood       yes - synopsis copied into eligibility_text,
                                   and None narrowed to False
regeneration changes only
  expected fields                  NO - this is the blocker
eligibility claims fabricated      YES, if regenerated: synthesized prose enters
                                   the evidence path on an honestly-empty row
positives removed                  0
```

## Decision

Regeneration does not proceed. Per the gate's own blocking rules,
`fabricated_eligibility_risk` and changes not classifiable as expected each block
a fixture mutation on their own; both are present.

Gate 106 therefore delivers the diff service, the attestation service, the
artifacts and the tests — the machinery that makes the decision reviewable — and
leaves `nf14_mixed_corpus.json` byte-identical.

The three Gate 105 corrections remain unabsorbed in the cached manifest. That is
a real, stated cost: consumers reading the cache still see the stale values. It
is the smaller cost. Absorbing them today requires also writing manufactured
eligibility text into the evidence path, and no correction is worth that trade.

## Next safe action

Fix the derivation, then regenerate. Two changes, each small and each testable:

```text
1. do not copy a synopsis into eligibility_text - a synopsis is not eligibility
   language, and a row marked empty_honestly must stay empty
2. do not narrow applicant_types_include_tribal from None to False - unknown is
   the honest answer when the source does not say
```

With those in place the diff reduces to the three Gate 105 rows, every change is
classified `gate105_tribal_bridge_correction`, and this gate's attestation
permits the regeneration it currently refuses.
