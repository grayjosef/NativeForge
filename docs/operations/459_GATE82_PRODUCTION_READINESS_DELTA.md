# 459 — Gate 82I: Production readiness delta

Gate 81 built a parser that accepts text. Gate 82 builds the layer that produces
that text from an artifact — hermetically, from local files only.

Nothing was fetched. No source was identified, seeded or monitored. No
dependency was added.

## Notice ingestion: now

| | Before | After |
| --- | --- | --- |
| Notice artifact model | did not exist | 6 types, provenance, hash, honesty flags |
| Live-fetch default | n/a | `False`, and refusable only by the hermetic guard |
| Recorded-fixture status | n/a | **checked** against the committed roots, not asserted |
| Type resolution | n/a | suffix < declaration < magic bytes |
| Artifact → Gate 81 | manual | one pipeline call, provenance carried |

## HTML support: now

| | Before | After |
| --- | --- | --- |
| Approach | regex `<[^>]+>` tag-strip (listing extractor) | `html.parser.HTMLParser` |
| `<script>` bodies | survived into text | **dropped**, counted |
| HTML comments | survived into text | **dropped**, counted |
| Hidden text | indistinguishable | **excluded and flagged** |
| Nav/footer chrome | survived | dropped, counted |
| Headings | flattened | blank-line separated, so Gate 81 still finds sections |

The regex gap was the real find. Stripping tags keeps everything *between* them,
so a `<script>` variable or a developer comment could reach Gate 81, be
sectioned, and be quoted as eligibility evidence — a sentence nobody wrote into
the notice. The synthetic fixture plants both traps plus a hidden `<div>`, all
three contradicting the visible eligibility rule, and tests assert the visible
rule wins.

## PDF support: now

**Structurally present, functionally unavailable.**

No PDF parser is installed (`pypdf`, `PyPDF2`, `fitz`, `pdfminer`, `pdfplumber`
all absent), so every real call returns `parser_unavailable` and blocks.

Adding a dependency was out of scope; hand-rolling an extractor was rejected
because a parser that works on simple files and degrades to garbage elsewhere
does not produce harmless garbage — it produces *cited eligibility evidence*
attributed to a sentence nobody wrote.

What does exist and is tested: local-path-only enforcement, URL refusal,
magic-byte validation, page-span assembly, image-only detection
(`needs_ocr_or_manual_review`, no OCR performed), and graceful failure on a
corrupt file. The extraction path runs under an **injected page reader**, so it
is exercised code rather than dead code waiting on a dependency, and it will run
for real the moment a backend is installed.

## Pipeline: now

| | Before | After |
| --- | --- | --- |
| Artifact → cited exclusion | did not exist | end to end for html/text/markdown/recorded |
| Unreadable vs no-eligibility-section | indistinguishable | **distinct** — blocked never reaches Gate 81 |
| Provenance on an exclusion | none | artifact id, type, hash, path, method |
| Span basis | undeclared | `spans_relative_to: "adapter_text"`, invariant-checked |
| Confidences | — | three, never merged; eligibility confidence stays `none` |

## Source coverage: now

**Unchanged. Zero.**

```text
Live SC source coverage:   NONE
Live federal coverage:     NONE
Sources monitored:         0
Notices fetched:           0
Real notices ingested:     0
SC coverage complete:      NOT CLAIMED
65% improvement:           NOT CLAIMED
```

Every fixture is synthetic and says so. Tests assert no Gate 82 module imports a
network client or any of the five live-fetch services found in the survey, and
that no PDF or HTML dependency appeared in `pyproject.toml`.

## Native customer value

The chain now runs from a **document** to a per-class answer:

1. An HTML notice file is described, hashed, and confirmed to be a local
   recorded fixture rather than a fetch.
2. Script, comment, hidden and chrome text are removed — none of it can become
   evidence.
3. Headings survive, so Gate 81 finds the eligibility section rather than
   reading the purpose paragraph as one.
4. The exclusive list excludes the other recognition tiers **with the sentence
   attached and a citation**.
5. The excluded opportunity stays visible and becomes negative intelligence.

Before this gate that chain started at a string somebody had already produced by
hand. It now starts at a file.

## Owner-blocked

- **Robots/terms review** for the Gate 78R sources. Still the gate on any fetch,
  and therefore on this layer ever seeing a real notice.
- **Primary-source verification.** No real notice has been ingested or parsed.
  The Gate 78R eligibility strings remain `eligibility_verified: false`.
- **A PDF parser decision.** Adding one is a dependency choice with licence and
  supply-chain implications; it is deliberately an owner call, not a silent
  commit.
- Real `OIDC_*` credentials, managed Postgres, migration 0028, backup/restore,
  pen test.

## Engineering-blocked

- The fetch layer itself. Gate 82 ingests artifacts somebody already has;
  nothing in the campaign may obtain one until terms review clears.
- A real notice corpus, to measure HTML-shape and phrase recall. Current
  coverage is measured against fixtures written to be parseable.
- OCR for scanned notices — detected and routed to a human, never attempted.
- Threading `applicant_class` from a customer org profile into the scorer
  (carried from Gate 79B).
- Scheduler (Gate 80) — still correctly blocked; zero sources are terms-cleared.

## Controlled customer pilot delta

**None.**

```text
Controlled customer pilot: NO_GO
Production rollout:        NO_GO
Customer login live:       NO
Production storage live:   NO
Customer persistence:      NO
Pen-test passed:           NO
```

What genuinely changed: the product can now take a notice **file** and produce a
cited, per-class eligibility answer without any of the document's non-content —
scripts, comments, hidden divs, navigation — ever being mistaken for what the
notice says. What has not changed: it has never done so to a real notice, and
PDFs cannot be read at all.
