# 593 — Gate 107: product readiness delta

## Mixed corpus freshness: now true

The cached corpus finally agrees with current derivation. Everything reading
`build_mixed_real_corpus()` at its default — which is everything — now sees the
Gate 105 Tribal eligibility corrections.

```text
                          Gate 106    Gate 107
mixed corpus freshness       false        true
cached vs fresh diff       4 rows     0 rows
fabricated eligibility risk   true       false
```

Three rows gained `applicant_types_include_tribal: true`, each already carrying
`tribal_eligible: true` with Tribal applicant-type language in its own text. One
row withdrew an unearned negative back to unknown.

## Derivation is honest about what it does not know

Two rules now hold across the corpus, measured rather than asserted:

```text
honest_empty_preserved   true    a blank stays blank when nothing was posted
unknown_preserved        true    unknown stays unknown when nothing said who
                                 may apply
```

A synopsis is no longer adopted as eligibility text, so manufactured prose cannot
reach the evidence path that `derive_explicit_source_evidence` and the canonical
Tribal classifier read. A negative on `applicant_types_include_tribal` now
requires something that actually described who may apply.

## Tenant matching and digest quality

Improved only where evidence supports it, and the improvement is now *reaching*
consumers rather than sitting behind a stale cache.

Three opportunities are correctly classified as including Tribal applicant types.
One is correctly reported as unknown rather than falsely excluded — which is the
more interesting of the two, because a false negative on applicant types is
exactly how a genuinely eligible opportunity disappears from a tenant's digest.

No eligibility is determined anywhere. `eligibility_determined` remains False at
every surface Gate 104 built, and Gate 103's cap on NativeForge self-assessment
is untouched.

## No fabricated eligibility was introduced

Every regenerated value is either traceable to applicant-type language already in
the row, or the withdrawal of a claim that had no source. The one row recording an
unposted NOFO is byte-identical to before and its honesty flags are true
statements about it again.

## No live fetch occurred

Both sides of every comparison are recorded fixtures. No collector ran, no URL was
fetched, no scraper was activated.

## What remains false

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

A corpus that is now internally consistent is still a recorded corpus of 57 rows.
Gate 107 closed the gap between the classifier and the cache; it collected
nothing and moved no readiness flag beyond corpus freshness.

## Carried forward

```text
the upstream body-text tribal vocabulary
    grants_gov_eligibility_parser_service decides tribal_eligible with a third
    pattern that does not recognise a tribal organization. Registered and
    attributed by the Gate 105 bridge guard; still not fixed.

repo-wide lint baseline
    ~700 pre-existing findings mean a new violation is invisible. Touched files
    are kept clean; the baseline still wants a cleanup gate.

corpus scale
    57 rows. Nothing about this gate changes how few opportunities the product
    has actually seen.
```

## Next

The corpus-integrity thread that ran from Gate 105 through 107 is closed: the
classifier is correct, the derivation is honest, and the cache matches. Gate 108
is free to move to the upstream vocabulary reconciliation, or back to the product
lane — the tenant digest still cannot deliver anything, and that is the largest
remaining gap between what exists and what a Tribe would pay for.
