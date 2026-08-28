# 585 — Gate 105: product readiness delta

What Gate 105 changed for the product, and what it did not.

## What improved

Tribal applicant-type detection in mixed-corpus classification now uses the
canonical vocabulary instead of a narrower local shadow. Free-text eligibility
saying "Indian tribe" or "tribal government" — ordinary federal NOFO phrasing —
is recognised where it previously was not.

Three corpus rows are corrected on fresh derivation, each of which previously
claimed `tribal_eligible: True` and `applicant_types_include_tribal: False` at
the same time.

## Tenant matching and digest quality improve only where evidence supports it

This is the whole of the improvement, stated precisely.

Classification input feeds tenant matching, which feeds digest candidate
quality. A tenant sees a better answer **only** for opportunities whose source
text actually names a Tribal applicant type. Nothing improves for an opportunity
whose text is silent, and nothing was added to the canonical vocabulary — the
phrases were already supported and merely unreachable.

No new opportunity is surfaced that the source text does not support. No
eligibility determination is made. `eligibility_determined` remains False at
every surface Gate 104 built, and Gate 103's cap — a NativeForge self-assessment
can rise no higher than `requires_human_review` — is untouched.

## No fabricated eligibility was introduced

The fix could only ever widen detection, never invent it: the shadow's pattern
was a strict subset of the canonical one. Measured across the corpus, the fix
removed zero positives and added three, each backed by text already in the
record.

## What remains false

Unchanged by this gate, and stated so nothing reads a classification fix as
progress toward operation:

```text
live source collection        false
source monitoring live        false
collectors live               false
source coverage               false
operational tenant digest     false
email delivery                false
customer persistence          false
customer beta onboarding      false
production rollout            false
controlled customer pilot     false
```

A better classifier over a recorded corpus is still a recorded corpus. Gate 105
improved how the tree reads evidence it already had; it collected nothing, and
it moved no readiness flag.

## Known gaps carried forward

```text
nf14_mixed_corpus.json is not regenerated
    the committed manifest still holds the stale values for those three rows,
    and already diverged from fresh derivation on nf13-real-fed-025 before this
    gate. Regenerating it needs its own gate under Gate 89 provenance - see 583.

the upstream body-text tribal vocabulary
    grants_gov_eligibility_parser_service decides tribal_eligible with a third
    pattern that does not recognise a tribal organization. Registered,
    attributed and reported by the drift guard; not fixed here.

repo-wide lint baseline
    ~700 pre-existing findings mean a new violation is invisible. Touched files
    are kept clean; the baseline is left for a cleanup gate.
```

## Next

Gate 106 should take the corpus manifest regeneration under proper provenance,
or the upstream tribal vocabulary reconciliation. Both are now measured, named
and owned rather than latent.
