# 484 — Gate 85: what Discovery Baseline X does not claim

A baseline is dangerous in a way a feature is not. A feature that overreaches
gets caught the first time somebody uses it. A number that overreaches becomes
the thing every later number is measured against, and by then nobody remembers
what it actually counted.

This document is the register of what Baseline X refuses to say, and what
enforces each refusal.

## The four flags

Every baseline result carries these, and they must be `False`:

| Flag | What it would mean | Enforced by |
| --- | --- | --- |
| `improvement_claim_allowed` | this number beats an earlier one | contract + result invariants, artifact writer |
| `live_coverage_claimed` | some source is being covered live | same |
| `source_monitoring_claimed` | some source is being watched | same, plus a derived count of 0 |
| `fixture_mutation_performed` | a committed fixture changed | same, plus a fixture hash before/after |

`False` is required, not merely falsy. An absent key fails: a claim that was
never declared is not a claim that was refused.

## Enforced, not described

### Live coverage

`live` is in the provenance vocabulary so it can be counted and reported as
zero. No committed flag maps to it — `classify_record_provenance` has no branch
that can return `"live"`, and a test asserts that for every input it accepts.
`baseline_result_invariant_failures` fails if `live_records` is ever non-zero.

### Source monitoring

Not asserted as zero — derived. `monitored_sources` counts seeds whose
`promotion_status` is in `MONITORING_STATUSES`. No seed catalog carries a
monitoring, robots or terms-review field at all, so nothing can set it. The
count is zero because there is nothing that could make it otherwise.

### Improvement

Nothing in the baseline reads a prior measurement, so there is no earlier value
to improve on. Beyond the flag, the artifact writer scans the rendered prose for
banned phrases including `65% improvement` and `improvement over`, and the
generator script scans the written JSON, Markdown and CSV again on disk.

That prose check caught its own author. A draft of the summary ended with "It
does not claim improvement over any earlier state" — a denial, but the guard
matches substrings and fired on it, correctly. The copy moved; the guard did
not. Same call as Gate 83, and for the same reason: a guard that gets loosened
to accommodate one careful sentence stops catching the careless ones.

### Fixture mutation

Three layers: `enrich_for_scoring` builds copies and a test diffs the record
before and after; a test hashes every `fixtures/**/*.json` around a full
baseline build; the generator script hashes them around the whole run and exits
3 on any difference.

### Network access

The baseline service imports no HTTP client, and a test greps the source for
`requests`, `httpx`, `urllib.request` and `socket`. The suite's default-deny
would catch an attempt at runtime; this catches the import that would make one
possible.

## Refusal leaves nothing behind

`write_discovery_baseline_x_artifacts` raises `BaselineClaimError` **before**
creating a directory or opening a file. A refused run produces no artifact at
all — not a file with a warning inside it, which is a file somebody eventually
quotes without the warning.

Proved in both directions, end to end. With a forbidden phrase injected into the
renderer:

```text
REFUSED: forbidden claim in Discovery Baseline X
  - banned_phrase:65% improvement
EXIT=2
```

and after reverting the injection:

```text
fixture-hash-stable
RESULT=PASS
EXIT=0
```

A parameterised test flips each of the four flags in turn and asserts both the
raise and the absence of any artifacts directory.

## Distinctions the product cannot afford to lose

### Recognition tier

`federally_recognized_tribe` and `state_recognized_tribe` are reported as
separate rows and are never combined. `test_recognition_tiers_are_not_collapsed_into_one_answer`
asserts the two summaries differ, and that the federal row has strictly more
cited-eligible records — 19 against 0 in this corpus. If those two rows ever
become identical, something has started answering both from one verdict.

### Relevance is not eligibility

Native relevance says an opportunity is worth looking at. Eligibility says a
specific applicant class may apply. 77 records carry relevance labels and no
eligibility text; all 77 stay `unknown` for every class, and a test walks every
text-less record to confirm none reached `eligible`.

### Absence of exclusion is not eligibility

`not_supported_by_evidence` is its own state and is never folded into
`eligible`. The counts across the six result states sum to the corpus total for
every class, so a state cannot quietly disappear into another.

### Exclusions stay visible

An exclusion the system found and cited is negative intelligence — worth telling
a customer about. Hiding those rows would improve every coverage number and make
the product worse. `negative_intelligence_count` is reported per class and the
excluded records remain in `per_record`.

## Honest gaps this baseline reports rather than fills

| Gap | Value | Why it is not filled here |
| --- | --- | --- |
| resolvable freshness | 0 of 185 | normalising the dates would manufacture freshness the pipeline cannot produce |
| unparseable deadlines | 19 | needs a date parser, which is product work, not measurement |
| never-checked records | 79 | needs monitoring, which does not exist |
| amendment evidence | 0 | Gate 81 built the detector; no committed record has been run through it |
| spam / low quality | `null` | no classifier exists; `0` would say one ran |
| recognition tier on opportunities | absent | not in any corpus record |
| authority requirements | absent | not in any corpus record |

Each of these lowers the score. That is the correct direction. A baseline whose
gaps are filled with plausible values is a baseline that cannot be used to tell
whether anything later actually improved.

## What the corpus does support

One thing: the customer demo. It runs entirely on committed, labelled data and
says so on its face. `customer_demo_usable` is the only readiness gate that is
`true`, and `production_usable` and `controlled_pilot_usable` are pinned `False`
by invariant, not by judgement.
