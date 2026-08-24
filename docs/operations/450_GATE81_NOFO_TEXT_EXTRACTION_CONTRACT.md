# 450 — Gate 81B: NOFO text extraction contract

`src/nativeforge/services/nofo_text_extraction_service.py`
Schema `nf_nofo_text_extraction_v1`.

Turns notice prose into structured, **cited** fields. Nothing in this module
fetches; the caller supplies the text.

## What text is extracted

Text is first split into labelled sections carrying character spans:

```text
eligibility      who may apply
deadline         closing / due dates
amendment        amendment, correction, cancellation notices
funding_origin   funding source, pass-through, assistance listing
restriction      allowable use, limitations
other            everything else, including headings we cannot label
```

From those, the result carries:

```text
title agency program_name posted_date close_date amendment_date version
eligibility_sections  deadline_sections  amendment_sections
funding_origin_evidence  restrictions
applicant_class_mentions  recognition_mentions  bare_keyword_mentions
dates_found  close_date_evidence  evidence_quotes
parser_confidence  eligibility_confidence
human_review_required  blocked_reasons
```

Caller-supplied metadata is never overwritten by a guess from the prose. Where
the text also carries a date, it is offered as evidence alongside, so a conflict
is visible rather than silently resolved.

## How evidence is cited

Every extracted claim carries `start` / `end` offsets into the supplied text plus
a quote. `extraction_invariant_failures` rejects any evidence quote with an
invalid span or empty text, so an uncited claim cannot survive the contract.

This is the capability Gate 79 was missing. It made exclusion citation-required
but nothing could supply the citation, because the existing analyser returned
class *names* and never said where it found them.

### Two parsing details that turned out to matter

**Headings must start a block.** An earlier version accepted any short line with
no terminal punctuation, which matched the last line of a wrapped paragraph. In
one fixture that split the eligibility section in half. A split inside an
eligibility section can hand the remaining eligibility rules to a different
section kind, which would quietly drop them from the only text allowed to
support an eligibility conclusion. A heading is now required to follow a blank
line.

**Phrases wrap.** Notice text is hard-wrapped, so `federally recognized\ntribes`
is one phrase split by a newline. Matching the raw string missed it while the
canonical analyser — which collapses whitespace — found it, and the two then
disagreed about the same sentence. `normalise_with_offsets` collapses whitespace
for the match and maps the span back, so the hit and the citation are both
correct.

## How eligibility is evidenced

**Only text inside an eligibility section counts.** `ELIGIBILITY_CONTEXT_KINDS`
is `{"eligibility"}`, and the non-eligibility kinds are derived by difference so
a section kind added later is excluded until someone deliberately includes it.

Keyword mentions are recorded wherever they appear, each with
`in_eligibility_context`. A mention outside an eligibility section is kept —
because knowing the notice mentions tribal communities is useful — but it is
structurally incapable of supporting eligibility, and an invariant fails any
attempt to record an out-of-context mention as an eligibility mention.

"Tribal" in a background paragraph, a programme name, or a list of past awardees
says nothing about who may apply. That was the single most likely way for this
product to tell a tribe it was eligible for something it was not.

## How exclusions are evidenced

This module does not decide exclusion. It produces `eligibility_text` — the
concatenated eligibility sections and nothing else — which Gate 81C parses and
the Gate 79 exclusion service adjudicates.

## How deadlines are handled

Dates are extracted with the precision their source string can honestly claim:
`March 2027` yields `2027-03` at `month` precision and can never be `certain`.
A nearby hedge (`on or about`, `estimated`, `anticipated`) makes a date
uncertain regardless of precision. Both facts are returned rather than resolved.

**A parsed date is never promoted to `close_date`.** Promoting it is how a date
nobody verified becomes a deadline a customer plans around. A missing close date
produces `close_date_certain: false` and a `no_close_date_supplied` blocked
reason, and downstream `opportunity_freshness_service` renders it `unknown` —
never `fresh`.

## Blocking

No raw text means `extraction_status: "blocked"` with `no_raw_text`, not an
empty result. A parser that quietly returns nothing invites the caller to read
the silence as "nothing found". An invariant fails any result that reports
`extracted` without text, and any blocked result without a reason.

## Confidence

`parser_confidence` and `eligibility_confidence` are separate fields and are
never merged. Being confident we read the sentence correctly is a different
question from what the sentence entitles anyone to.
`eligibility_confidence` is `"none"` here — this module does not assess it — and
`parser_confidence_used_as_eligibility_confidence: False` is an enforced claim.

Only *labelled* sections raise parser confidence. An unlabelled heading is a
boundary we found, not a section we understood.

## Why no live coverage is claimed

Nothing here fetches. `live_fetch_performed` and `freshness_claimed` are
hardcoded `False` and invariant-checked, and a test asserts no module in this
gate references `requests`, `httpx`, `urllib.request` or `aiohttp`.

## What still needs primary-source verification

Everything the parser reads is only as good as the text handed to it. All seven
Gate 81 fixtures are synthetic and say so on their first line. No real notice
has been parsed, no source is monitored, and the Gate 78R eligibility strings
remain `eligibility_verified: false`.
