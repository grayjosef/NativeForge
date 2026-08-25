# 456 — Gate 82C: HTML notice text adapter

`src/nativeforge/services/html_notice_text_adapter_service.py`
Schema `nf_html_notice_text_adapter_v1`.
Extraction method `stdlib_html_parser`.

Turns a local HTML notice page into plain text Gate 81 can section, cite and
parse. Accepts an HTML string or a local file path.

## The no-live-fetch rule

Never opens a URL. A `local_path` that looks like a URL is **refused**, not
resolved:

```text
local_path_is_a_url_not_a_path
```

`source_url` and `notice_url` never reach this module. `url_fetch_performed` is
hardcoded `False` and invariant-checked, and a test asserts the module imports
no network client and none of the five live-fetch services found in the Gate 82A
survey.

## Why the standard library and not the existing approach

`html_card_listing_extractor_service` strips tags with
`re.compile(r"<[^>]+>")`. That removes *tags* and keeps everything between them.
On a notice page it leaves the body of every `<script>` block and the text of
every HTML comment in the output.

That is not a cosmetic problem. Extracted text flows into Gate 81, gets
sectioned, and can be cited as eligibility evidence. A `<script>` variable or a
developer comment could become a quoted sentence attributed to the notice —
a sentence nobody ever wrote into it.

`html.parser.HTMLParser` knows where a script body ends, so the *content* is
dropped rather than merely unwrapped. The synthetic fixture contains both traps
deliberately, and a test asserts neither reaches the output.

## Extraction behaviour

| Category | Tags | Treatment |
| --- | --- | --- |
| Non-content | `script` `style` `noscript` `template` `svg` `canvas` `iframe` | content dropped, counted |
| Chrome | `nav` `header` `footer` `aside` `form` | content dropped, counted |
| Headings | `h1`–`h6` | emitted on their own line, blank-line separated |
| Block | `p` `div` `li` `table` `tr` `td` … | blank line, preserving paragraph boundaries |
| Comments | — | never emitted, characters counted |

**Headings matter more than they look.** Gate 81 only treats a line as a section
heading if it *starts a block* — follows a blank line. Emitting headings inline
would make every section boundary invisible and collapse the whole notice into
one unlabelled block, which in turn would put the purpose paragraph inside the
eligibility section. The adapter emits blank lines around headings for exactly
that reason, and a test runs `detect_sections` over the adapter output to prove
`eligibility` and `deadline` sections are still found.

Whitespace is normalised without destroying structure: spaces and tabs collapse,
newlines are structure, and runs of blank lines reduce to one.

## Hidden text

Content hidden by `display:none`, `visibility:hidden`, `hidden`, or
`aria-hidden="true"` is **excluded from the text and counted**:

```text
hidden_text_excluded_chars:<n>
```

It is never silently used. A page that hides an eligibility sentence produces a
warning and `human_review_required`, rather than a confident answer built on
text no reader would have seen. The synthetic fixture hides a sentence that
contradicts its visible eligibility rule, and a test asserts the visible rule
wins and the hidden one is absent.

## Confidence and uncertainty

```text
high    2+ headings and a reasonable text-to-source ratio
medium  at least one heading
low     no headings at all
```

`extraction_uncertain` is set by low confidence **or** by the presence of hidden
text, and anything uncertain must set `human_review_required` — an invariant
enforces the pairing.

Note these are two different concerns and the pipeline keeps them apart: the
adapter can be confident it read the document correctly and still have found
something worth a human look. That is why the pipeline distinguishes
`adapter_low_confidence:<level>` from `adapter_flagged_uncertainty`.

Adapter confidence is **not** eligibility confidence and never becomes it.

## Blocking

```text
no_html_supplied            neither string nor path
empty_html                  nothing but whitespace
no_text_after_extraction    everything was script/style/chrome
local_path_is_a_url_not_a_path
could_not_read_local_path:<Error>
```

A blocked result carries no text and declares no extraction method; invariants
fail either.

Malformed HTML does not raise. A parser exception is recorded as a warning and
whatever text was collected is kept, because a half-read notice with a warning
is more useful than a crash — and a test covers unclosed tags.

## Evidence span limitations

Spans returned by Gate 81 index the **adapter output**, not the original HTML
file. There is no honest mapping back to a byte offset in the source markup
without a much heavier parser. The pipeline records
`spans_relative_to: "adapter_text"` and returns the adapter text alongside, so a
quote can always be resolved against the exact string it indexes.

## Why no live coverage is claimed

The adapter reads files somebody already has. It identifies no source, fetches
nothing, and monitors nothing. `eligibility_claimed` and `freshness_claimed` are
hardcoded `False`.
