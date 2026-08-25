"""HTML notice text adapter (Gate 82C).

Turns a local HTML notice page into plain text that Gate 81 can section, cite
and parse. Accepts a string or a local file path. **Never opens a URL.**

Why the standard library parser and not the existing regex approach: the
regex used elsewhere in this package is ``re.compile(r"<[^>]+>")``, which
removes *tags* and keeps everything between them. On a notice page that leaves
the body of every ``<script>`` block and the text of every HTML comment in the
output. Either could then land inside a detected eligibility section and be
cited as eligibility evidence - a sentence no human ever wrote into the notice.

``html.parser.HTMLParser`` knows where a script body ends, so the content can be
dropped rather than stripped of its tags.

Three properties Gate 81 depends on:

  * **Headings survive.** ``h1``-``h6`` and ``th`` are emitted on their own
    lines, blank-line separated, because Gate 81 requires a heading to start a
    block before it will treat it as a section boundary.
  * **Paragraph boundaries survive.** Block elements produce blank lines; inline
    elements do not. Section detection depends on the difference.
  * **Hidden text is flagged, never silently used.** ``display:none``,
    ``hidden``, and ``aria-hidden`` content is excluded from the text and
    counted, so a page that hides an eligibility sentence produces a warning
    rather than a confident wrong answer.

Nothing here fetches.
"""

from __future__ import annotations

import json
import re
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "nf_html_notice_text_adapter_v1"
ADAPTER_VERSION = "gate82_v1"
EXTRACTION_METHOD = "stdlib_html_parser"

# Elements whose *content* is not document text at all.
DROPPED_CONTENT_TAGS = frozenset(
    {"script", "style", "noscript", "template", "svg", "canvas", "iframe"}
)

# Elements that are chrome rather than notice prose. Their text is dropped and
# counted, because a nav bar full of programme names would otherwise read like
# notice content.
CHROME_TAGS = frozenset({"nav", "header", "footer", "aside", "form"})

# Elements that end a block, so a paragraph boundary survives into the text.
BLOCK_TAGS = frozenset(
    {
        "p", "div", "section", "article", "main", "ul", "ol", "li", "table",
        "tr", "td", "th", "blockquote", "pre", "br", "hr", "dl", "dt", "dd",
        "figure", "figcaption", "address", "fieldset",
    }
)

HEADING_TAGS = frozenset({"h1", "h2", "h3", "h4", "h5", "h6"})

_HIDDEN_STYLE = re.compile(
    r"(display\s*:\s*none|visibility\s*:\s*hidden)", re.IGNORECASE
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


class _NoticeHTMLTextParser(HTMLParser):
    """Collect readable text, dropping non-content and hidden material."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._drop_depth = 0
        self._chrome_depth = 0
        self._hidden_depth = 0
        self.dropped_tag_counts: dict[str, int] = {}
        self.chrome_tag_counts: dict[str, int] = {}
        self.hidden_text_chars = 0
        self.comment_chars = 0
        self.heading_count = 0
        # Tracks the tag that opened each suppression, so the matching close
        # tag lowers the right counter.
        self._drop_stack: list[str] = []
        self._chrome_stack: list[str] = []
        self._hidden_stack: list[str] = []

    # -- helpers ---------------------------------------------------------

    @staticmethod
    def _is_hidden(attrs: list[tuple[str, str | None]]) -> bool:
        for key, value in attrs:
            k = (key or "").lower()
            v = (value or "").strip().lower()
            if k == "hidden":
                return True
            if k == "aria-hidden" and v == "true":
                return True
            if k == "style" and _HIDDEN_STYLE.search(value or ""):
                return True
        return False

    def _suppressed(self) -> bool:
        return bool(self._drop_depth or self._chrome_depth or self._hidden_depth)

    def _newline(self, blank: bool = False) -> None:
        if self._suppressed():
            return
        self.parts.append("\n\n" if blank else "\n")

    # -- HTMLParser hooks ------------------------------------------------

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        tag = tag.lower()
        if tag in DROPPED_CONTENT_TAGS:
            self._drop_depth += 1
            self._drop_stack.append(tag)
            self.dropped_tag_counts[tag] = self.dropped_tag_counts.get(tag, 0) + 1
            return
        if tag in CHROME_TAGS:
            self._chrome_depth += 1
            self._chrome_stack.append(tag)
            self.chrome_tag_counts[tag] = self.chrome_tag_counts.get(tag, 0) + 1
            return
        if self._is_hidden(attrs):
            self._hidden_depth += 1
            self._hidden_stack.append(tag)
            return
        if tag in HEADING_TAGS:
            self.heading_count += 1
            self._newline(blank=True)
        elif tag in BLOCK_TAGS:
            self._newline(blank=True)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if self._drop_stack and self._drop_stack[-1] == tag:
            self._drop_stack.pop()
            self._drop_depth = max(0, self._drop_depth - 1)
            return
        if self._chrome_stack and self._chrome_stack[-1] == tag:
            self._chrome_stack.pop()
            self._chrome_depth = max(0, self._chrome_depth - 1)
            return
        if self._hidden_stack and self._hidden_stack[-1] == tag:
            self._hidden_stack.pop()
            self._hidden_depth = max(0, self._hidden_depth - 1)
            return
        if tag in HEADING_TAGS or tag in BLOCK_TAGS:
            self._newline(blank=True)

    def handle_data(self, data: str) -> None:
        if self._drop_depth or self._chrome_depth:
            return
        if self._hidden_depth:
            # Counted, never used.
            self.hidden_text_chars += len(data.strip())
            return
        if data.strip():
            self.parts.append(data)

    def handle_comment(self, data: str) -> None:
        # A comment is not document text. Counted so the caller knows the page
        # had some, never emitted.
        self.comment_chars += len(data.strip())


def _collapse(text: str) -> str:
    """Normalise whitespace while preserving blank-line block boundaries."""
    # Spaces and tabs collapse; newlines are structure.
    text = re.sub(r"[ \t\x0b\f\r]+", " ", text)
    # Trim each line.
    text = "\n".join(line.strip() for line in text.split("\n"))
    # At most one blank line between blocks.
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip() + "\n" if text.strip() else ""


def extract_html_notice_text(
    *,
    html: str | None = None,
    local_path: str | Path | None = None,
    artifact_id: str | None = None,
) -> dict[str, Any]:
    """Extract plain text from local HTML. Never fetches.

    Exactly one of ``html`` or ``local_path`` is used; ``local_path`` wins when
    both are supplied, and a URL passed as ``local_path`` is refused rather than
    resolved.
    """
    blocked_reasons: list[str] = []
    warnings: list[str] = []
    source_kind = "string"
    raw: str | None = html

    if local_path is not None:
        source_kind = "file"
        candidate = str(local_path)
        # A URL is not a path. Refuse rather than let anything downstream be
        # tempted to resolve it.
        if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", candidate):
            blocked_reasons.append("local_path_is_a_url_not_a_path")
            raw = None
        else:
            try:
                raw = Path(candidate).read_text(encoding="utf-8", errors="replace")
            except (OSError, ValueError) as exc:
                blocked_reasons.append(f"could_not_read_local_path:{type(exc).__name__}")
                raw = None

    if raw is None and not blocked_reasons:
        blocked_reasons.append("no_html_supplied")

    if raw is not None and not raw.strip():
        blocked_reasons.append("empty_html")

    if blocked_reasons:
        return _blocked(artifact_id, source_kind, blocked_reasons, warnings)

    assert raw is not None
    parser = _NoticeHTMLTextParser()
    try:
        parser.feed(raw)
        parser.close()
    except Exception as exc:  # noqa: BLE001 - malformed HTML must not crash
        warnings.append(f"html_parser_raised:{type(exc).__name__}")

    text = _collapse("".join(parser.parts))

    if not text.strip():
        blocked_reasons.append("no_text_after_extraction")
        return _blocked(artifact_id, source_kind, blocked_reasons, warnings)

    if parser.hidden_text_chars:
        warnings.append(f"hidden_text_excluded_chars:{parser.hidden_text_chars}")
    if parser.comment_chars:
        warnings.append(f"html_comment_text_excluded_chars:{parser.comment_chars}")
    for tag, count in sorted(parser.dropped_tag_counts.items()):
        warnings.append(f"dropped_non_content_element:{tag}x{count}")
    for tag, count in sorted(parser.chrome_tag_counts.items()):
        warnings.append(f"dropped_chrome_element:{tag}x{count}")
    if not parser.heading_count:
        # Gate 81 needs headings to find sections at all.
        warnings.append("no_headings_found_section_detection_will_be_weak")

    # How much of the original survived. A very low ratio usually means the page
    # was mostly chrome or mostly script, which is worth a human looking.
    ratio = round(len(text) / max(1, len(raw)), 4)
    if parser.heading_count >= 2 and ratio >= 0.05:
        confidence = "high"
    elif parser.heading_count >= 1:
        confidence = "medium"
    else:
        confidence = "low"

    uncertain = confidence == "low" or bool(parser.hidden_text_chars)

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "adapter_version": ADAPTER_VERSION,
            "artifact_id": artifact_id,
            "artifact_type": "html",
            "source_kind": source_kind,
            "extraction_status": "extracted",
            "text": text,
            "text_chars": len(text),
            "source_chars": len(raw),
            "text_ratio": ratio,
            "heading_count": parser.heading_count,
            "hidden_text_chars": parser.hidden_text_chars,
            "comment_chars": parser.comment_chars,
            "dropped_tag_counts": dict(sorted(parser.dropped_tag_counts.items())),
            "chrome_tag_counts": dict(sorted(parser.chrome_tag_counts.items())),
            "text_extraction_method": EXTRACTION_METHOD,
            "adapter_confidence": confidence,
            "extraction_uncertain": uncertain,
            "human_review_required": uncertain,
            "blocked_reasons": blocked_reasons,
            "warnings": warnings,
            # Boundaries.
            "url_fetch_performed": False,
            "script_text_included": False,
            "comment_text_included": False,
            "hidden_text_included": False,
            "eligibility_claimed": False,
            "freshness_claimed": False,
        }
    )


def _blocked(
    artifact_id: str | None,
    source_kind: str,
    blocked_reasons: list[str],
    warnings: list[str],
) -> dict[str, Any]:
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "adapter_version": ADAPTER_VERSION,
            "artifact_id": artifact_id,
            "artifact_type": "html",
            "source_kind": source_kind,
            "extraction_status": "blocked",
            "text": "",
            "text_chars": 0,
            "source_chars": 0,
            "text_ratio": 0.0,
            "heading_count": 0,
            "hidden_text_chars": 0,
            "comment_chars": 0,
            "dropped_tag_counts": {},
            "chrome_tag_counts": {},
            "text_extraction_method": None,
            "adapter_confidence": "none",
            "extraction_uncertain": True,
            "human_review_required": True,
            "blocked_reasons": blocked_reasons,
            "warnings": warnings,
            "url_fetch_performed": False,
            "script_text_included": False,
            "comment_text_included": False,
            "hidden_text_included": False,
            "eligibility_claimed": False,
            "freshness_claimed": False,
        }
    )


def html_adapter_invariant_failures(result: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    if result.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")

    status = result.get("extraction_status")
    if status not in {"extracted", "blocked"}:
        fails.append(f"unknown_extraction_status:{status}")

    if status == "blocked":
        if not result.get("blocked_reasons"):
            fails.append("blocked_without_a_reason")
        if result.get("text"):
            fails.append("blocked_result_carried_text")
        if result.get("text_extraction_method"):
            fails.append("blocked_result_claimed_an_extraction_method")

    if status == "extracted":
        if not str(result.get("text") or "").strip():
            fails.append("extracted_result_without_text")
        if result.get("text_extraction_method") != EXTRACTION_METHOD:
            fails.append("extraction_method_not_declared")

    # Hidden and non-content material must be counted, never included.
    for forbidden in (
        "url_fetch_performed",
        "script_text_included",
        "comment_text_included",
        "hidden_text_included",
        "eligibility_claimed",
        "freshness_claimed",
    ):
        if result.get(forbidden) is not False:
            fails.append(f"forbidden_claim:{forbidden}")

    # Anything uncertain must ask for a human.
    if result.get("extraction_uncertain") and not result.get(
        "human_review_required"
    ):
        fails.append("uncertain_extraction_without_human_review")

    return fails
