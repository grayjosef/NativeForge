# 510 — Gate 91A: awarded-vs-pursuit and document parser survey

Surveyed before writing any Gate 91 code. The Gate 90 finding was verified
rather than assumed, and it holds.

## Doc number correction

The gate prompt references
`docs/operations/509_AWARDED_VS_PURSUIT_AND_MARK_AS_AWARDED_CONTRACT.md`. The
actual file is
`509_AWARDED_VS_PURSUIT_LANE_AND_MARK_AS_AWARDED_CONTRACT.md` — with `LANE_` in
the name. No file was created at the shortened path.

## Does an awarded-grant portfolio model exist?

**No.** Searched services for `award|portfolio|transition|undo|lane|closeout|lifecycle`.
41 matches, and every one is either a closeout *packet* service (sprint
retrospective artifacts, unrelated to grant closeout), an evidence-lifecycle
service, or a source-lane service. None is an awarded-grant portfolio.

## Does a pursuit model exist?

**Yes, partially.**

```text
pursuit_service.py                     create_pursuit_from_spark, list_pursuits,
                                       update_pursuit, tasks, calendar events
pursuit_workspace_contract_service.py  PURSUIT_STATUSES
pursuit_brief_service.py
pursuit_readiness_next_action_service.py
pursuit_workspace_assembler_service.py
```

`PURSUIT_STATUSES` = `{draft, under_review, needs_information, deferred, blocked,
closed}` — a workspace-review vocabulary, **not** a pipeline lane vocabulary. It
has no `awarded` member and no notion of pursuit-versus-award.

## Where does `GrantPipelineStage` exist, and can `awarded` be assigned directly?

```text
src/nativeforge/domain/enums.py:200-208

class GrantPipelineStage(StrEnum):
    new | evaluating | pursuing | drafting | submitted | awarded | not_pursuing
```

**`awarded` exists at exactly one location in the entire codebase** —
`enums.py:208`. A repo-wide grep for the word across `src/` returns that single
line and nothing else.

**Yes, it can be assigned directly.** It is a plain `StrEnum` member on a
tracked Spark. Nothing guards the assignment, nothing records who made it, and
nothing distinguishes it from any other stage transition.

### This is the bypass risk, confirmed

The product rule in doc 509 is *a pursued grant becomes an awarded-grant
portfolio record only after an explicit user action or verified award evidence*.

Today that rule is unenforceable, because the only thing "awarded" means is a
string in an enum field. Gate 91 does not remove `GrantPipelineStage.awarded` —
other code may depend on it — but it does establish that **a pipeline stage is
not an awarded-grant record**, and that the portfolio is reachable only through
an explicit transition.

## Does any UI show Awarded Grants?

**No.** `grep -rniE "awarded" frontend/src/` returns nothing. There is no
awarded page, no lane toggle, and no Mark-as-Awarded control.

## Does a transition service or undo exist?

**Neither.** No `award_transition_service`. The only `undo` match in `src/` is
`active_source_activation_m1_human_runtime_authorization_board_packet_service.py`,
which is an unrelated authorization board packet.

## Are documents or attachments inventoried?

**Partially, and for a different purpose.**

```text
attachment_form_intake_planner_service.py       application forms planning
forms_attachments_map_contract_service.py       form-to-attachment mapping
forms_attachments_mapper_service.py
grants_gov_attachment_recoverable_reaudit_service.py
```

These concern *application* attachments — what the customer must submit. Gate 91
needs the opposite direction: the agency's own documents (NOFO, amendments,
terms, reporting guidance) as **evidence to read**. No inventory of those exists.

## Deterministic text extraction — what can be reused

This is the strongest finding of the survey. Gates 81 and 82 already built a
complete deterministic, non-AI, hermetic extraction stack:

| Service | What it provides |
| --- | --- |
| `notice_artifact_model_service` | `ARTIFACT_TYPES`, `sniff_artifact_type`, `content_hash_of`, `build_notice_artifact` with hash and live-fetch guards |
| `notice_ingestion_pipeline_service` | `run_text_adapter`, `ingest_notice_artifact`, `PIPELINE_STATUSES` |
| `html_notice_text_adapter_service` | stdlib `HTMLParser`; drops script/style/chrome; flags hidden text |
| `pdf_notice_text_adapter_service` | page-reader injection seam; reports `parser_unavailable` honestly |
| `nofo_text_extraction_service` | `detect_sections` with `SECTION_KINDS` and character spans; `normalise_with_offsets` |

`ARTIFACT_TYPES` = `{html, pdf, plain_text, markdown, json_recorded_transport,
unknown}`, with `EXTRACTABLE_TYPES` derived by difference — a type added later
is unreadable until someone wires an adapter, which is the deny-by-default
pattern this campaign uses throughout.

**Gate 91 reuses all of it.** The document-text-extraction seam is a thin
adapter over `notice_ingestion_pipeline_service`, not a second parser.

## Missing parser support

```text
available_pdf_backends() -> []
```

**No PDF backend is installed.** `pdf_notice_text_adapter_service` returns
`parser_unavailable` and the pipeline reports it as a visible blocker rather
than silently returning empty text. Gate 91 preserves that behaviour and does
not install a backend — that would be a dependency decision, not an extraction
one.

`EXTRACTION_STATUSES` = `{extracted, needs_ocr_or_manual_review, blocked}`.

## Fixtures available

```text
tests/fixtures/nofo_artifacts/   synthetic_notice.{html,md,pdf,txt} + generator
tests/fixtures/nofo_text/        7 synthetic notices, each self-declaring
                                 "SYNTHETIC TEST FIXTURE - NOT A REAL NOTICE"
```

Enough to exercise every extraction path deterministically, including the PDF
blocked path. No real NOFO with post-award reporting sections exists in the
repo — which bounds what Gate 91's reporting extractor can be *tested* against,
and doc 508 already recorded that Gate 93's customer-facing profile needs real
notices.

## What is missing, and what Gate 91 builds

| Missing | Gate 91 |
| --- | --- |
| lane vocabulary separating pursuit from awarded | `grant_lane_separation_service` |
| customer-specific awarded-grant portfolio | `awarded_grant_portfolio_service` |
| projected-vs-active burden separation | `pursuit_reporting_burden_projection_service` |
| explicit transition + undo | `award_transition_service` |
| agency-document inventory | `grant_document_attachment_inventory_service` |
| document text seam | `grant_document_text_extraction_service` (reuses the Gate 81/82 stack) |
| reporting-obligation extraction | `grant_reporting_requirement_extraction_service` |

None of these exist today. All seven are new, and the seventh is the only one
that needed a new parser decision — resolved by reusing `detect_sections`
rather than writing a second one.
