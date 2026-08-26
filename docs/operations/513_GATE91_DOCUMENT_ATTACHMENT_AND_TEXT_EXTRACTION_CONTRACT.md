# 513 — Gate 91F/91G: document attachment and text extraction contract

A large amount of grant burden lives in attachments. These two services make
them first-class evidence.

## Attachments are evidence, not decoration

`grant_document_attachment_inventory_service` lists the agency documents
attached to an opportunity or awarded grant, before anything tries to read them.

Document types:

```text
NOFO | amendment | application_instructions | budget_instructions |
terms_and_conditions | assurances | reporting_guidance | closeout_guidance |
award_package | portal_instruction | appendix | unknown
```

`POST_AWARD_DOCUMENT_TYPES` and `APPLICATION_DOCUMENT_TYPES` are disjoint, and
an invariant fails if a document claims both. That distinction carries through
to extraction: an application instruction is not a post-award obligation.

## Three facts, three fields

```text
parse_status            has anything tried to parse it?
text_extraction_status  did text come out?
terms_status            are we allowed to retrieve it at all?
```

Collapsing them is how a *listed* document becomes a *read* one. A document can
be inventoried, blocked on terms, and never parsed — a normal state the
inventory reports rather than hiding.

`parse_status` and `text_extraction_status` are both `not_attempted` at
inventory time, always. Inventory never implies a parse succeeded.

## No download in this gate

Nothing is fetched. `downloaded: False` and `network_access_performed: False`
on every entry, `downloads_performed: 0` on the inventory.

A document known upstream but not held locally is inventoried as
`not_retrieved` with the reason `not_retrieved_no_download_in_this_gate` — we
know it exists, we have not got it. That is a different state from "absent" and
is recorded as such.

## Hash everything local

Every local file is hashed SHA-256 via
`notice_artifact_model_service.content_hash_of`. The hash is what makes an
extraction reproducible and proves a fixture has not drifted — the same role
fixture hashing plays in Gates 85–90. An invariant fails on a local document
without one.

## Extraction reuses the Gate 81/82 stack

`grant_document_text_extraction_service` is a **seam**, not a second parser:

```text
notice_artifact_model_service      artifact typing, hashing, live-fetch guard
notice_ingestion_pipeline_service  run_text_adapter dispatch
html_notice_text_adapter_service   stdlib HTMLParser
pdf_notice_text_adapter_service    page-reader seam
nofo_text_extraction_service       detect_sections with character spans
```

Writing a second parser would mean two things that could disagree about the same
file, which is how a quote stops matching its source.

## Deterministic, no AI, no OCR, no network

Same input, same output, byte for byte — a test serialises two runs and compares.

```text
ai_used                      False
ocr_used                     False
network_access_performed     False
deterministic                True
```

The no-AI guard parses this module's **imports** with the `ast` module rather
than grepping its text. The first version grepped, and failed on the module's
own docstring explaining "no model call, no embedding" — the guard is meant to
check the code, not the prose describing it, and rewording accurate
documentation to satisfy a naive matcher would have made the module worse.

## Unsupported is visible, never silent

No PDF backend is installed — `available_pdf_backends()` returns an empty list.
A PDF returns:

```text
extraction_status   parser_unavailable
text                None
blocked_reasons     [parser_unavailable, manual_review_required]
```

It does **not** return empty text with a success status. A silent fallback would
let a document with obligations in it read as a document with none — and an
invariant fails if `parser_unavailable` ever appears without a manual-review
escalation.

Supported here: HTML, plain text, markdown, recorded JSON transport. Recognised
but backend-blocked: PDF. Anything else is a visible `blocked`.

## Evidence spans

Every extraction returns `evidence_spans` from `detect_sections`, with character
offsets into the extracted text. An invariant checks every span is ordered and
inside the text, so a later quote can always point at where it came from.
