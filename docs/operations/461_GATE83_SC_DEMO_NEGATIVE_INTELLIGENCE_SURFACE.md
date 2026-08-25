# 461 — Gate 83: SC demo negative intelligence surface

Service `src/nativeforge/services/sc_demo_negative_intelligence_service.py`
(`nf_sc_demo_negative_intelligence_v1`), rendered by
`frontend/src/pages/ScCustomerDemoPage.tsx` under
`data-testid="sc-demo-negative-intelligence"` at `/?view=sc_customer_demo`.

## What is displayed

The customer-facing answer this product exists to give:

> Relevant does not mean eligible. This notice appears to limit eligibility to
> federally recognized tribes.

Per applicant class, the section shows:

```text
Applicant class            State-recognized tribe / Federally recognized tribe
Status                     Likely excluded — review required / Named as eligible
Relevance vs eligibility   an explicit statement that relevance does not decide
Evidence quote             the sentence, quoted, from the notice text
Provenance                 span, spans_relative_to, has_citation, artifact_type,
                           artifact_hash (first 16), extraction method
Parser detail              reason, notice_status, deadline_status,
                           human_review_required, remains_visible,
                           not_eligible_asserted
Why it matters             what the negative answer saves the customer
Class contrast             applicant_class_changes_the_answer, class counts
```

Plus two boundary lines rendered above the rows —
`sc-demo-ni-synthetic-label` and `sc-demo-ni-no-live-coverage` — and a closing
review note.

## Why excluded opportunities remain visible

Stated on the page, not just in code:

> Excluded opportunities remain visible because they are useful negative
> intelligence. Nothing below is hidden from you.

Knowing that a programme has already ruled you out is worth more than never
finding it. It saves the weeks an application would have taken, and it is the
answer a keyword search can never give. Hiding it would leave the customer to
rediscover the exclusion themselves — the same reasoning that shaped Gate 79B's
scoring, now visible to the person it protects.

`remains_visible` is `true` on every row, `excluded_hidden` is `false` on the
surface, and invariants fail either being otherwise.

## How the quote and evidence are generated

**The quote is produced, not written.**

```text
tests/fixtures/nofo_artifacts/synthetic_notice.html
  -> notice_ingestion_pipeline_service.ingest_notice_artifact()   (Gate 82)
     -> html adapter        script/style/comment/hidden/chrome removed
     -> extract_nofo_text   sections + spans                      (Gate 81B)
     -> parse_nofo_eligibility  per-class verdict + citation      (Gate 81C)
     -> detect_notice_status    notice status + evidence          (Gate 81D)
  -> rows shaped for display
```

Hand-writing a quote into a demo payload would produce a screen that looks
identical and proves nothing — a mockup wearing the clothes of a working
system. Because the pipeline runs, the sentence on screen is the one the parser
cited, at the span it found, from the artifact whose hash is displayed beside
it. A parser regression changes this surface or fails its invariants.

Two tests hold that honesty in place: every quoted word of length > 4 must
appear in the fixture, and the committed demo JSON must equal the freshly built
surface.

The excluding sentence reaching the screen is also proof the Gate 82C work
holds: the fixture plants a `<script>` string, an HTML comment and a hidden
`<div>` that all say state-recognized tribes *are* eligible. None of them
reaches the quote.

## The applicant-class contrast

Same notice, two answers:

```text
state_recognized_tribe        excluded_by_evidence   negative intelligence
federally_recognized_tribe    eligible               a real opportunity
```

This is the single most important consequence of the recognition-tier split and
nothing displayed it before. An invariant fails the surface if the two tiers
ever agree, so a future change that collapsed them would break the demo rather
than quietly flattening the answer.

The excluded row is rendered **first**, because the negative answer is the one a
customer cannot get anywhere else.

## Tone and wording

The section never asserts ineligibility. It says the notice text *appears to
limit* eligibility, labels the status "Likely excluded — review required", and
closes with:

> NativeForge reports what a cited sentence appears to say, and asks a human on
> your team to confirm it against the primary notice. This is not a legal
> determination and not a final eligibility decision.

A vitest guard asserts the rendered page never contains "you are not eligible",
"you are ineligible" or "legally ineligible". That guard caught the first draft
of this very paragraph, which used the phrase inside a negation — the copy was
reworded rather than the guard loosened.

`not_eligible_asserted` remains `false` throughout, preserving the Gate 77
boundary.

## Why this is demo / synthetic

The notice is a committed test fixture that declares itself
`SYNTHETIC TEST FIXTURE - NOT A REAL NOTICE` on its first line and states that
no opportunity number is claimed. The exclusion is a true statement *about that
synthetic text*, not about any real programme.

`synthetic_demo` and `demo_only` are hardcoded `true`; a test asserts the page
displays both.

## Why no live coverage is claimed

```text
live_coverage_claimed   false
source_monitored        false
freshness_claimed       false
url_fetch_performed     false
```

All four are hardcoded, invariant-checked, and **rendered on the page**. The
deadline line is equally honest: the fixture carries a date in its deadline
section, but nobody supplied a verified close date and Gate 81 refuses to
promote a parsed one, so the row reads
`deadline_status=date_in_text_not_promoted_to_close_date`.

## What remains blocked before customer pilot

Unchanged by this gate. Nothing here moves the pilot boundary — it displays work
already done. See doc 463.
