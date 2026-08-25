# 458 — Gate 82F: Notice ingestion pipeline

`src/nativeforge/services/notice_ingestion_pipeline_service.py`
Schema `nf_notice_ingestion_pipeline_v1`.

Runs one artifact end to end:

```text
artifact -> text adapter -> nofo_text_extraction_service (81B)
         -> nofo_eligibility_parser_service (81C)
         -> nofo_amendment_detector_service (81D)
```

## Supported artifact types and their adapters

| Type | Adapter | Method |
| --- | --- | --- |
| `html` | `html_notice_text_adapter_service` | `stdlib_html_parser` |
| `pdf` | `pdf_notice_text_adapter_service` | `backend:<name>` / `injected_page_reader` |
| `plain_text` | `extract_plain_text_notice` | `verbatim_read` |
| `markdown` | `extract_plain_text_notice` | `verbatim_read` |
| `json_recorded_transport` | `extract_recorded_transport_notice` | `recorded_field:<key>` |
| `unknown` | none — blocks | — |

Markdown is read **verbatim**, not converted. Its headings are already
line-initial, which is exactly what Gate 81 section detection wants; rewriting
them could only lose one.

Recorded transport payloads are searched for a text field in a fixed order
(`notice_text`, `raw_text`, `text`, `body`, `content`) and block with
`no_text_field_in_recorded_transport` rather than guessing at an unknown shape.
A payload carrying `real_fetch: true` is warned about, echoing the Gate 77B
honest-labeling rule.

## The no-live-fetch rule

Nothing in this pipeline or any adapter opens a URL. `source_url` and
`notice_url` travel as metadata and are passed to Gate 81 as provenance only.

An artifact that claims `is_live_fetch` **cannot pass**: an invariant fails
`pipeline_ingested_a_live_fetched_artifact`. Combined with the artifact model
refusing to set that flag while the hermetic guard forbids live network, there
is no route by which a fetched document reaches Gate 81 through this path.

## Refusing early

An unknown artifact type, a missing file, or a failed adapter stops the pipeline
before Gate 81 runs.

This matters more than it first appears. A blocked adapter returning `""` would
reach `extract_nofo_text` as *"a notice with no eligibility section"* rather
than *"a notice we could not read"* — two very different statements that would
be indistinguishable downstream. The pipeline keeps them distinct:

```text
artifact_blocked:<reason>
text_extraction_failed:<status>
adapter:<adapter reason>
```

A blocked result carries no eligibility answers at all, and an invariant fails
any blocked result that produced them.

## Adapter-to-parser handoff

The adapter output string is passed to all three Gate 81 services and returned
as `adapter_text`. Provenance travels with it: the full artifact record
(id, type, hash, path, fixture status, fetch mode) and the extraction method.

So an exclusion can be traced to the file it came from, not merely to a string —
`content_hash` identifies the exact bytes parsed.

## Evidence span limitations

Gate 81 spans are offsets into the **adapter output**, not the original
artifact. For plain text and markdown the two coincide. For HTML and PDF they do
not, and there is no honest mapping back without a much heavier parser than this
project has.

Every result therefore declares:

```text
spans_relative_to: "adapter_text"
adapter_text: <the exact string every span indexes>
```

An invariant fails a result that does not declare this basis, and another fails
any span pointing past the end of the returned text. A test resolves a mention's
span back to its phrase to prove the offsets are real.

For PDFs, `page_spans` give page-level attribution — the honest granularity
available.

## Three confidences, never merged

```text
adapter_confidence       did we read the document correctly
parser_confidence        did we find the sections (Gate 81B)
eligibility_confidence   what does the text entitle anyone to  -> always "none"
```

An invariant fails any result where a confident adapter has produced a non-`none`
eligibility confidence (`eligibility_confidence_borrowed_from_the_adapter`), and
`adapter_confidence_used_as_eligibility_confidence` is a hardcoded `False`
claim.

## Manual review

`human_review_required` is set by any of:

```text
adapter_low_confidence:<level>     the adapter is unsure it read the document
adapter_flagged_uncertainty        confident, but something was excluded
adapter_warning:<warning>          e.g. hidden text excluded
parser_requires_review             Gate 81C conflict / uncited / ambiguous
notice_status_requires_review      Gate 81D unknown or non-current status
```

Low confidence and flagged uncertainty are reported separately on purpose: the
adapter can be confident it read the page correctly and still have found
something worth a human look, such as hidden text it deliberately excluded.
Collapsing the two produced the self-contradictory label
`adapter_uncertain:high` in an earlier draft.

## Why no live coverage is claimed

```text
live_coverage_claimed  False
source_monitored       False
freshness_claimed      False
url_fetch_performed    False
```

All four are hardcoded and invariant-checked. The pipeline can read an artifact
somebody already has; it cannot obtain one, and it does not know whether any
source is being watched.
