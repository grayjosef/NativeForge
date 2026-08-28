# 588 — Gate 106C/D: mixed corpus regeneration attestation

`src/nativeforge/services/mixed_corpus_regeneration_attestation_service.py`
`artifacts/mixed_corpus_regeneration_attestation/`

## The fixture was not mutated

```text
corpus_path              fixtures/real_grants_corpus/nf14_mixed_corpus.json
fixture_mutated          false
safe_to_regenerate       false
safe_to_commit_fixture   false
human_review_required    true
positives_removed        0
fabricated_eligibility_risk  true
```

`nf14_mixed_corpus.json` is byte-identical to what git tracks. A test asserts the
attested `before_hash` equals the hash of the committed file, so the attestation
provably describes the file that is actually in the tree rather than some other
state.

## Why Gate 105 did not regenerate it

Gate 105 fixed the canonical Tribal classifier. Regenerating the manifest inside
that gate would have swept unrelated fixture drift into a bridge-fix commit,
making the diff unreviewable. Gate 105 recorded the divergence and deferred.

Gate 106 is that deferred work: build the machinery that makes the decision
reviewable, then let the machinery decide.

## What changed after the canonical Tribal classifier fix

Three rows, one field, one direction — each backed by applicant-type text
already in the record:

```text
nf14-mixed-edge-10           applicant_types_include_tribal  False -> True
nf14-mixed-label_spread-14   applicant_types_include_tribal  False -> True
nf14-mixed-label_spread-15   applicant_types_include_tribal  False -> True
```

Each already carried `tribal_eligible: True` while claiming applicant types
exclude Tribes. These are corrections of self-contradictory records, not new
claims. All three are classified `gate105_tribal_bridge_correction` and marked
`evidence_backed`.

## Why regeneration was refused

`nf13-real-fed-025` drift remains, and it is the blocker:

```text
eligibility_text                ''   -> the row's synopsis
applicant_types_include_tribal  None -> False
```

The synopsis on that row is not eligibility language. It reads "No posted NOFO on
Grants.gov at ingest (no_live_nofo)" — an administrative note recording an
absence. Writing it into `eligibility_text` puts synthesized prose into the field
`derive_explicit_source_evidence` and the canonical Tribal classifier read.

The row would then still carry `empty_honestly: True` and
`never_synthesized: True` while holding manufactured text, making its own honesty
flags false statements about itself. A test asserts exactly that state, so the
reason is pinned rather than described.

The second change narrows an unknown into an affirmative negative on a
tribal-federal row whose source genuinely does not say. `None` is the honest
answer.

## Are the regenerated values evidence-backed?

The three Gate 105 rows: **yes**. Each traces to applicant-type language in the
row's own source text.

The two nf13-real-fed-025 fields: **no**. That is precisely why nothing was
written. Under the gate's own rules, `fabricated_eligibility_risk` blocks a
fixture mutation on its own.

## What this costs

Stated plainly rather than buried: the three Gate 105 corrections remain
**unabsorbed** in the cached manifest. Everything that reads
`build_mixed_real_corpus()` with its default `use_cached_manifest=True` — which is
everything — still sees `applicant_types_include_tribal: False` on those rows.

The classifier is correct; the cache is not. That is a real, ongoing gap.

It is the smaller cost. Absorbing the corrections today requires also writing
manufactured eligibility text into the evidence path, and no correction is worth
that trade.

## safe_to_commit_fixture is derived

True only when the diff independently permits regeneration **and** every changed
field is an expected correction. Deliberately stricter than the diff: the diff
answers "safe to attempt", the attestation answers "safe to commit".

Invariants fail any attestation where fabrication risk, unexpected rows or
removed positives coexist with permission, and fail unresolved drift that did not
route to `human_review_required`. The `attestation_id` is derived from the two
hashes it attests and is re-checked, so a record cannot be edited and still
validate.

The permission path is tested too: a clean diff produces
`safe_to_commit_fixture: True` with `human_review_required: False`, so the
refusal is a measurement rather than a constant.

## Boundaries

```text
live_fetch_performed     false
source_monitoring_live   false
live_source_coverage     false
fabricated               false
```

Both sides of the comparison are recorded fixtures. No collector ran, no URL was
fetched, and no source coverage is claimed.

## Next safe action

Fix the derivation, then regenerate under this same attestation:

```text
1. do not copy a synopsis into eligibility_text - a synopsis is not eligibility
   language, and a row marked empty_honestly must stay empty
2. do not narrow applicant_types_include_tribal from None to False
```

With those in place the diff reduces to the three expected corrections, every
change classifies as `gate105_tribal_bridge_correction`, and this attestation
permits the regeneration it currently refuses. The machinery is already here; the
next gate only has to make the derivation honest enough to pass it.
