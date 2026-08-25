# 454 — Gate 82A: Notice ingestion survey

Surveyed before implementing. The decisive finding is a dependency fact, not a
code fact, and it determines what this gate can honestly deliver.

## Dependency reality

```text
PDF parsers:   pypdf MISSING  PyPDF2 MISSING  fitz MISSING
               pdfminer MISSING  pdfplumber MISSING
HTML parsers:  bs4 MISSING  lxml MISSING  html5lib MISSING
               stdlib html.parser AVAILABLE
```

Declared runtime dependencies are `fastapi`, `uvicorn`, `sqlalchemy`,
`alembic`, `psycopg`, `pydantic-settings`, `pyjwt` — nothing that reads a PDF or
a DOM.

Consequences:

- **HTML** can be done properly with the standard library. `html.parser.HTMLParser`
  handles scripts, styles and comments correctly.
- **PDF** cannot be extracted at all today. Gate 82D therefore fails honestly
  with `parser_unavailable`, and no dependency is added — `uv.lock` and
  `pyproject.toml` stay untouched.

Writing a hand-rolled PDF text extractor was considered and rejected. A partial
extractor that works on uncompressed content streams and degrades to garbage
elsewhere is worse than an honest refusal: it produces plausible text that would
flow into Gate 81 and become cited eligibility evidence.

The extraction path is still written and still tested, via an injected parser,
so it is exercised code rather than dead code waiting on a dependency.

## Existing artifact / PDF / HTML ingestion code

| Service | What it does | Reusable? |
| --- | --- | --- |
| `html_card_listing_extractor_service` | regex strip (`<[^>]+>`) over listing pages to find grant links | **No** — regex tag-stripping cannot exclude `<script>` bodies, and it targets listings, not notice prose |
| `foundation_html_listing_adapter_service` | listing adapter, Tier 3 | No — listing, not notice |
| `state_tribal_affairs_html_adapter_service` | listing adapter | No — listing, not notice |
| `html_fetch_honest_labeling_guard_service` | refuses `real_fetch: true` on a fixture payload | **Yes, as precedent** for the honesty flags |
| `source_fetch_adapter_contract_service` | `FETCH_MODE_LIVE` / `FETCH_MODE_FIXTURE` | **Yes** — imported, not re-declared |

**No PDF service exists.** No document/artifact model exists for notices; the
two `*artifact*` services are demo-surface and human-approval packets.

### The gap regex-stripping leaves

`_TAG_RE = re.compile(r"<[^>]+>")` removes tags but leaves everything *between*
them. Applied to a notice page, the body of a `<script>` block and the text of
an HTML comment survive into the output. Either could then land inside a
detected eligibility section and become cited eligibility evidence. That is the
specific hazard Gate 82C is built to close.

## Live-fetch hazards found

Five modules in `src/nativeforge` import a network client:

```text
services/polite_http_fetch_service.py          the general fetcher
services/grants_gov_search_api_adapter_service.py
services/real_url_resolver_service.py
services/oidc_token_verification_service.py
services/feedback_slack_alert_service.py
```

No Gate 82 service imports any of them, and none imports `requests`, `httpx`,
`aiohttp` or `urllib.request` directly. A test asserts this by reading the
source of every Gate 82 module.

`source_url` and `notice_url` are carried as **metadata only**. They are never
opened. This is the single most important boundary in the gate, because an
adapter that quietly fetches would turn every downstream "hermetic" claim in the
campaign into a false one.

## Reusable hermetic guards

From `hermetic_test_guard_service` (Gate 77B):

```text
live_network_allowed()          default False
assert_live_network_allowed()   raises unless explicitly enabled
is_source_controlled(path)      is this a committed fixture path
SOURCE_CONTROLLED_DIRS          the committed fixture roots
guarded_write_text/json         write-back lockdown
```

`is_source_controlled` is what makes `is_recorded_fixture` decidable rather than
caller-asserted: a caller claiming fixture status for a path outside the
committed roots is contradicted by the filesystem.

## Extraction handoff points

Gate 81 is already shaped for this. `extract_nofo_text` takes `raw_text` plus
metadata and returns spans into that exact string, so an adapter only has to
produce the text and say how it produced it.

```text
artifact -> adapter -> raw_text
         -> nofo_text_extraction_service.extract_nofo_text(raw_text=...)
         -> nofo_eligibility_parser_service.parse_nofo_eligibility(raw_text=...)
         -> nofo_amendment_detector_service.detect_notice_status(raw_text=...)
```

**Span caveat.** Gate 81 spans are offsets into the *adapter output*, not into
the original artifact. For plain text they coincide. For HTML and PDF they do
not, and there is no honest mapping back to a byte offset in the source file
without a much heavier parser. The pipeline records
`spans_relative_to: "adapter_text"` so nobody later mistakes an offset for a
position in the original document.

## Gaps Gate 82 fills

- A notice **artifact model** with type, provenance, hash and honesty flags.
- An **HTML adapter** that removes script/style/comment content rather than just
  tags, preserves headings and paragraph boundaries for Gate 81 section
  detection, and flags hidden text instead of silently using it.
- A **PDF adapter** that refuses honestly today and works the moment a parser
  lands, with the extraction path tested by injection.
- A **pipeline** that carries artifact provenance into the parse result and
  keeps adapter confidence separate from eligibility confidence.

## Deliberately not touched

- No new dependency; `uv.lock` and `pyproject.toml` unchanged.
- The five live-fetch modules.
- Gate 81 service internals — the pipeline calls them, it does not modify them.
- The hermetic and corpus write-back guards.
- The existing listing adapters, which answer a different question.
