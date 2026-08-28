# 589 — Gate 106: product readiness delta

## What this gate delivered

Machinery, not data. A diff service that classifies every difference between the
cached corpus and fresh derivation, an attestation service that decides whether a
fixture mutation may be committed, four deterministic artifacts, and 44 tests.

## What this gate deliberately did not deliver

The corpus fixture is unchanged. `nf14_mixed_corpus.json` is byte-identical to
what git tracks, and a test proves the attested `before_hash` matches the
committed file.

Regeneration was refused because it would have written synthesized prose into the
`eligibility_text` of the one corpus row that records an honest absence. See 586
and 588 for the full reasoning.

## Mixed corpus freshness: still stale, and now measured

Before this gate the staleness was known but unquantified. Now it is:

```text
rows_total                        57
rows_changed                       4
gate105_tribal_bridge_correction   3  correct, evidence-backed, unabsorbed
preexisting_fixture_drift          2  blocks regeneration
unexpected                         0
positives_removed                  0
```

The three Gate 105 corrections remain unabsorbed in the cached manifest.
Everything reading `build_mixed_real_corpus()` at its default still sees the
pre-fix values on those rows. That gap is real and is not closed by this gate.

What changed is that it is now attested, artifact-backed and reviewable rather
than latent.

## No fabricated eligibility was introduced

Nothing was written to any fixture. The fabrication risk this gate found is a
risk of a regeneration that did not happen, and the services exist to keep it
from happening silently.

## No live fetch occurred

Both sides of the comparison are recorded fixtures — NF-13 ingested grants and
recorded Grants.gov pulls. No collector ran, no URL was fetched, no scraper was
activated.

## What remains false

```text
live source collection        false
source monitoring live        false
collectors live               false
source coverage               false
mixed corpus freshness        false - cached manifest predates the Gate 105 fix
operational tenant digest     false
email delivery                false
customer persistence          false
customer beta onboarding      false
production rollout            false
controlled customer pilot     false
```

A gate that refuses to write is not a gate that advanced readiness. Nothing moved
except the quality of the evidence available for the next decision.

## Next

Gate 107 should make the derivation honest enough to pass this attestation:

```text
1. stop copying a synopsis into eligibility_text
2. stop narrowing applicant_types_include_tribal from None to False
```

Then regenerate under the attestation built here. The diff should reduce to the
three expected corrections, `safe_to_commit_fixture` should become true on its
own, and the cached corpus can finally absorb the Gate 105 fix.

The alternative — relaxing the attestation to let the current derivation through —
would defeat the purpose of having built it.
