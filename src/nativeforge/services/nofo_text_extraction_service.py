"""NOFO / primary-notice text extraction (Gate 81B).

Turns the text of a funding notice into structured, **cited** fields.

The rule that shapes every function here: *a claim without a span is not a
claim.* Every extracted value carries the character offsets it came from, so a
customer-facing statement can always be traced back to the sentence that
produced it. Gate 79 made exclusion citation-required; this is the module that
can actually supply the citation.

Three boundaries are enforced rather than documented:

  * **No raw text means blocked.** Not "empty result", not "unknown" - blocked,
    with a reason. A parser that quietly returns nothing for missing input
    invites a caller to read the silence as "nothing found".
  * **A keyword is not eligibility.** "Tribal" in a background paragraph, a
    programme name, or a list of past awardees says nothing about who may apply.
    Mentions are recorded with their spans and a flag for whether they fell
    inside an eligibility section; only the latter can support eligibility.
  * **Parser confidence is not eligibility confidence.** Being sure we read the
    sentence correctly is a different question from what the sentence entitles
    anyone to. They are returned as separate fields and never merged.

Nothing here fetches. Input text is supplied by the caller.
"""

from __future__ import annotations

import json
import re
from typing import Any

SCHEMA_VERSION = "nf_nofo_text_extraction_v1"
EXTRACTOR_VERSION = "gate81_v1"

# Section kinds this module can label. "other" is the honest default for prose
# that matches no heading we recognise.
SECTION_KINDS = frozenset(
    {
        "eligibility",
        "deadline",
        "amendment",
        "funding_origin",
        "restriction",
        "other",
    }
)

# Only these can support an eligibility conclusion. Derived by name so a section
# kind added later is excluded until someone deliberately includes it.
ELIGIBILITY_CONTEXT_KINDS = frozenset({"eligibility"})
NON_ELIGIBILITY_CONTEXT_KINDS = SECTION_KINDS - ELIGIBILITY_CONTEXT_KINDS

# Heading patterns, matched against a whole line. Ordered most specific first;
# the first match wins so "eligibility information" does not fall into "other".
_HEADING_PATTERNS: tuple[tuple[str, str], ...] = (
    (
        "eligibility",
        r"(eligib\w*|who\s+may\s+apply|applicant\s+eligibility|"
        r"qualified\s+entities|eligible\s+applicants?)",
    ),
    (
        "deadline",
        r"(deadline|closing\s+date|close\s+date|application\s+due|"
        r"submission\s+date|due\s+date|key\s+dates)",
    ),
    (
        "amendment",
        r"(amendment|amended|correction|corrected|modification|"
        r"addendum|supplement|notice\s+of\s+change|revision|cancell?ation|"
        r"withdrawal)",
    ),
    (
        "funding_origin",
        r"(funding\s+source|source\s+of\s+funds|federal\s+award|"
        r"pass[-\s]?through|cfda|assistance\s+listing|authoriz\w+\s+statute)",
    ),
    (
        "restriction",
        r"(restrictions?|limitations?|allowable\s+use|use\s+of\s+funds|"
        r"ineligible\s+activities)",
    ),
)

# A line is treated as a heading if it is short, and looks like one.
#
# Wrapped prose is the trap here. An earlier version accepted any short line
# with no terminal punctuation, which matched the last line of a wrapped
# paragraph and split a section in the middle - and a split inside an
# eligibility section can hand the rest of the eligibility rules to a different
# section kind. So a heading must also start a block.
_MAX_HEADING_LEN = 120
_NUMBERED_HEADING = re.compile(
    r"^(?:section\s+)?(?:[IVXLC]+|[A-Z]|\d+(?:\.\d+)*)[.)]\s+\S",
    re.IGNORECASE,
)
_MAX_HEADING_WORDS = 10

# Date forms, most specific first. Each carries the precision it can honestly
# claim - a month-and-year string cannot yield a day.
_DATE_PATTERNS: tuple[tuple[str, str], ...] = (
    (
        "day",
        r"\b(?P<month>January|February|March|April|May|June|July|August|"
        r"September|October|November|December)\s+(?P<day>\d{1,2}),?\s+"
        r"(?P<year>\d{4})\b",
    ),
    ("day", r"\b(?P<year>\d{4})-(?P<mon>\d{2})-(?P<dom>\d{2})\b"),
    ("day", r"\b(?P<m>\d{1,2})/(?P<d>\d{1,2})/(?P<y>\d{4})\b"),
    (
        "month",
        r"\b(?P<month2>January|February|March|April|May|June|July|August|"
        r"September|October|November|December)\s+(?P<year2>\d{4})\b",
    ),
)

_MONTHS = {
    "january": "01",
    "february": "02",
    "march": "03",
    "april": "04",
    "may": "05",
    "june": "06",
    "july": "07",
    "august": "08",
    "september": "09",
    "october": "10",
    "november": "11",
    "december": "12",
}

# Phrases that make a date approximate. A notice that says "on or about" has not
# given us a deadline we may show a customer as firm.
_UNCERTAINTY_MARKERS = (
    "on or about",
    "approximately",
    "estimated",
    "anticipated",
    "expected",
    "subject to change",
    "tentative",
)

# Recognition language worth recording wherever it appears. Recording is not
# concluding: a mention outside an eligibility section proves nothing.
_RECOGNITION_PHRASES: tuple[str, ...] = (
    "federally recognized",
    "federally-recognized",
    "state recognized",
    "state-recognized",
    "federal recognition",
    "bureau of indian education",
    "bureau of indian affairs",
    "indian tribal government",
    "trust land",
    "restricted fee land",
)

# Bare Native-relevance keywords. Present so they can be found and explicitly
# denied eligibility credit - never so they can grant it.
_BARE_NATIVE_KEYWORDS: tuple[str, ...] = (
    "tribal",
    "tribe",
    "native",
    "american indian",
    "alaska native",
    "indigenous",
    "native hawaiian",
)

_MAX_QUOTE_CHARS = 400


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _clip(text: str, limit: int = _MAX_QUOTE_CHARS) -> str:
    t = re.sub(r"\s+", " ", text).strip()
    return t if len(t) <= limit else t[: limit - 3].rstrip() + "..."


def _looks_like_heading(line: str, *, starts_block: bool) -> bool:
    """A heading is short, block-initial, and shaped like a heading.

    ``starts_block`` means the line is the first line or follows a blank one.
    Requiring it is what keeps the last line of a wrapped paragraph from being
    read as the start of a new section.
    """
    stripped = line.strip()
    if not stripped or len(stripped) > _MAX_HEADING_LEN:
        return False
    if not starts_block:
        return False
    if stripped.isupper():
        return True
    if stripped.endswith(":"):
        return True
    return (
        bool(_NUMBERED_HEADING.match(stripped))
        and len(stripped.split()) <= _MAX_HEADING_WORDS
    )


def _classify_heading(line: str) -> str | None:
    low = line.strip().lower()
    for kind, pattern in _HEADING_PATTERNS:
        if re.search(pattern, low):
            return kind
    return None


def detect_sections(raw_text: str) -> list[dict[str, Any]]:
    """Split notice text into labelled sections carrying character spans.

    Source-agnostic by design. The Block 09 extractor answers a similar question
    but is pinned to one opportunity and one fixture path, so it cannot be
    reused for arbitrary notices.
    """
    if not str(raw_text or "").strip():
        return []

    lines = raw_text.splitlines(keepends=True)
    marks: list[tuple[int, str, str]] = []
    offset = 0
    prev_blank = True  # the first line starts a block
    for line in lines:
        if _looks_like_heading(line, starts_block=prev_blank):
            # Every heading is a boundary, even one we cannot label. Otherwise a
            # "PROGRAM PURPOSE" block following the eligibility section would be
            # absorbed into it, and its keywords would read as eligibility rules
            # - exactly the confusion this module exists to prevent.
            kind = _classify_heading(line) or "other"
            marks.append((offset, kind, line.strip().rstrip(":")))
        offset += len(line)
        prev_blank = not line.strip()

    if not marks:
        return [
            {
                "kind": "other",
                "heading": None,
                "start": 0,
                "end": len(raw_text),
                "text": raw_text,
                "heading_matched": False,
            }
        ]

    sections: list[dict[str, Any]] = []
    if marks[0][0] > 0:
        sections.append(
            {
                "kind": "other",
                "heading": None,
                "start": 0,
                "end": marks[0][0],
                "text": raw_text[: marks[0][0]],
                "heading_matched": False,
            }
        )

    for i, (start, kind, heading) in enumerate(marks):
        end = marks[i + 1][0] if i + 1 < len(marks) else len(raw_text)
        sections.append(
            {
                "kind": kind,
                "heading": heading,
                "start": start,
                "end": end,
                "text": raw_text[start:end],
                "heading_matched": True,
            }
        )
    return sections


def _sections_of(sections: list[dict[str, Any]], kind: str) -> list[dict[str, Any]]:
    return [
        {
            "kind": s["kind"],
            "heading": s["heading"],
            "start": s["start"],
            "end": s["end"],
            "quote": _clip(s["text"]),
        }
        for s in sections
        if s["kind"] == kind
    ]


def _normalise_date(m: re.Match[str]) -> tuple[str, str] | None:
    """Return (value, precision) or None. Precision never exceeds the source."""
    g = m.groupdict()
    try:
        if g.get("month") and g.get("day"):
            month = _MONTHS[g["month"].lower()]
            return f"{g['year']}-{month}-{int(g['day']):02d}", "day"
        if g.get("mon"):
            return f"{g['year']}-{g['mon']}-{g['dom']}", "day"
        if g.get("m"):
            return f"{g['y']}-{int(g['m']):02d}-{int(g['d']):02d}", "day"
        if g.get("month2"):
            month = _MONTHS[g["month2"].lower()]
            return f"{g['year2']}-{month}", "month"
    except (KeyError, ValueError):
        return None
    return None


def extract_dates(text: str, *, window: int = 90) -> list[dict[str, Any]]:
    """Find dates and keep their uncertainty.

    A date is only as precise as the string that produced it, and a nearby
    hedge ("on or about") makes it approximate. Both are returned rather than
    resolved, because resolving them is how a customer ends up trusting a
    deadline the notice never committed to.
    """
    if not str(text or "").strip():
        return []
    found: list[dict[str, Any]] = []
    claimed: list[tuple[int, int]] = []
    for _precision, pattern in _DATE_PATTERNS:
        for m in re.finditer(pattern, text, re.IGNORECASE):
            # A "March 2026" match inside an already-claimed "March 15, 2026"
            # is the same date at lower precision, not a second date.
            if any(s <= m.start() and m.end() <= e for s, e in claimed):
                continue
            parsed = _normalise_date(m)
            if not parsed:
                continue
            value, precision = parsed
            claimed.append((m.start(), m.end()))
            lo = max(0, m.start() - window)
            context = text[lo : m.end() + window].lower()
            hedges = sorted({h for h in _UNCERTAINTY_MARKERS if h in context})
            found.append(
                {
                    "value": value,
                    "precision": precision,
                    "raw": m.group(0),
                    "start": m.start(),
                    "end": m.end(),
                    "uncertainty_markers": hedges,
                    "certain": not hedges and precision == "day",
                }
            )
    return sorted(found, key=lambda d: d["start"])


def normalise_with_offsets(text: str) -> tuple[str, list[int]]:
    """Lowercase and collapse whitespace, keeping a map back to real offsets.

    Notice text is hard-wrapped, so "federally recognized\\ntribes" is one
    phrase split by a newline. Matching against the raw string misses it while
    the canonical analyser - which collapses whitespace - finds it, and the two
    then disagree about what the same sentence says. Normalising for the match
    and mapping the span back keeps both the hit and an honest citation.
    """
    chars: list[str] = []
    idx: list[int] = []
    prev_space = False
    for i, ch in enumerate(text):
        if ch.isspace():
            if prev_space or not chars:
                continue
            chars.append(" ")
            idx.append(i)
            prev_space = True
        else:
            chars.append(ch.lower())
            idx.append(i)
            prev_space = False
    return "".join(chars), idx


def find_phrase_spans(
    text: str, phrases: tuple[str, ...]
) -> list[tuple[str, int, int]]:
    """Return (phrase, start, end) for each hit, in original-text offsets."""
    norm, idx = normalise_with_offsets(text)
    hits: list[tuple[str, int, int]] = []
    for phrase in phrases:
        needle = re.sub(r"\s+", " ", phrase.strip().lower())
        if not needle:
            continue
        for m in re.finditer(re.escape(needle), norm):
            if m.end() - 1 >= len(idx):
                continue
            hits.append((phrase, idx[m.start()], idx[m.end() - 1] + 1))
    return hits


def _find_phrases(
    text: str, phrases: tuple[str, ...], sections: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for phrase, start, end in find_phrase_spans(text, phrases):
        ctx = [s for s in sections if s["start"] <= start < s["end"]]
        kind = ctx[0]["kind"] if ctx else "other"
        out.append(
            {
                "phrase": phrase,
                "start": start,
                "end": end,
                "section_kind": kind,
                "in_eligibility_context": kind in ELIGIBILITY_CONTEXT_KINDS,
                "quote": _clip(text[max(0, start - 80) : end + 80]),
            }
        )
    return sorted(out, key=lambda d: d["start"])


def _blocked_result(
    *,
    notice_id: str,
    source_id: str | None,
    source_url: str | None,
    notice_url: str | None,
    title: str | None,
    agency: str | None,
    program_name: str | None,
    posted_date: str | None,
    close_date: str | None,
    amendment_date: str | None,
    version: str | int | None,
    retrieved_at: str | None,
    blocked_reasons: list[str],
) -> dict[str, Any]:
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "extractor_version": EXTRACTOR_VERSION,
            "notice_id": notice_id,
            "source_id": source_id,
            "source_url": source_url,
            "notice_url": notice_url,
            "title": title,
            "agency": agency,
            "program_name": program_name,
            "posted_date": posted_date,
            "close_date": close_date,
            "close_date_certain": False,
            "amendment_date": amendment_date,
            "version": str(version) if version is not None else None,
            "retrieved_at": retrieved_at,
            "extraction_status": "blocked",
            "raw_text_present": False,
            "raw_text_chars": 0,
            "sections": [],
            "eligibility_sections": [],
            "deadline_sections": [],
            "amendment_sections": [],
            "funding_origin_evidence": [],
            "restrictions": [],
            "applicant_class_mentions": [],
            "recognition_mentions": [],
            "bare_keyword_mentions": [],
            "dates_found": [],
            "close_date_evidence": [],
            "evidence_quotes": [],
            "parser_confidence": "none",
            "eligibility_confidence": "none",
            "eligibility_text": None,
            "eligibility_text_present": False,
            "human_review_required": True,
            "blocked_reasons": blocked_reasons,
            # Boundaries this module never crosses.
            "keyword_counted_as_eligibility": False,
            "parser_confidence_used_as_eligibility_confidence": False,
            "live_fetch_performed": False,
            "freshness_claimed": False,
        }
    )


def extract_nofo_text(
    *,
    notice_id: str,
    source_id: str | None = None,
    source_url: str | None = None,
    notice_url: str | None = None,
    title: str | None = None,
    agency: str | None = None,
    program_name: str | None = None,
    posted_date: str | None = None,
    close_date: str | None = None,
    amendment_date: str | None = None,
    version: str | int | None = None,
    raw_text: str | None = None,
    retrieved_at: str | None = None,
) -> dict[str, Any]:
    """Extract cited structure from one notice's text.

    Caller-supplied metadata (``title``, ``close_date``, ...) is kept as
    supplied and never overwritten by a guess from the prose. Where the text
    also carries a date, it is offered as *evidence* alongside, so a conflict is
    visible instead of silently resolved.
    """
    blocked_reasons: list[str] = []
    text = str(raw_text or "")

    if not text.strip():
        return _blocked_result(
            notice_id=notice_id,
            source_id=source_id,
            source_url=source_url,
            notice_url=notice_url,
            title=title,
            agency=agency,
            program_name=program_name,
            posted_date=posted_date,
            close_date=close_date,
            amendment_date=amendment_date,
            version=version,
            retrieved_at=retrieved_at,
            blocked_reasons=["no_raw_text"],
        )

    sections = detect_sections(text)
    elig_sections = _sections_of(sections, "eligibility")
    deadline_sections = _sections_of(sections, "deadline")
    amendment_sections = _sections_of(sections, "amendment")
    origin_sections = _sections_of(sections, "funding_origin")
    restriction_sections = _sections_of(sections, "restriction")

    # The only text that may support an eligibility conclusion.
    eligibility_text = (
        "\n".join(
            s["text"] for s in sections if s["kind"] in ELIGIBILITY_CONTEXT_KINDS
        )
        or None
    )

    recognition_mentions = _find_phrases(text, _RECOGNITION_PHRASES, sections)
    bare_mentions = _find_phrases(text, _BARE_NATIVE_KEYWORDS, sections)

    # Every mention is recorded; only in-context ones are even candidates.
    applicant_class_mentions = sorted(
        (
            m
            for m in recognition_mentions + bare_mentions
            if m["in_eligibility_context"]
        ),
        key=lambda d: d["start"],
    )

    dates = extract_dates(text)
    deadline_spans = [(s["start"], s["end"]) for s in deadline_sections]
    close_evidence = [
        d for d in dates if any(s <= d["start"] < e for s, e in deadline_spans)
    ]

    # A parsed date is never promoted to the close date. Promoting it is how a
    # date nobody verified becomes a deadline a customer plans around.
    close_certain = bool(close_date)
    if not close_date:
        blocked_reasons.append("no_close_date_supplied")

    evidence_quotes = [
        {
            "field": kind,
            "start": s["start"],
            "end": s["end"],
            "quote": s["quote"],
        }
        for kind, group in (
            ("eligibility", elig_sections),
            ("deadline", deadline_sections),
            ("amendment", amendment_sections),
            ("funding_origin", origin_sections),
            ("restriction", restriction_sections),
        )
        for s in group
    ]

    # Only *labelled* sections count. An unlabelled heading is a boundary we
    # found, not a section we understood.
    matched = sum(
        1 for s in sections if s.get("heading_matched") and s["kind"] != "other"
    )
    if matched >= 3:
        parser_confidence = "high"
    elif matched >= 1:
        parser_confidence = "medium"
    else:
        parser_confidence = "low"

    if not elig_sections:
        blocked_reasons.append("no_eligibility_section_found")
    human_review = not elig_sections or not close_date

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "extractor_version": EXTRACTOR_VERSION,
            "notice_id": notice_id,
            "source_id": source_id,
            "source_url": source_url,
            "notice_url": notice_url,
            "title": title,
            "agency": agency,
            "program_name": program_name,
            "posted_date": posted_date,
            "close_date": close_date,
            "close_date_certain": close_certain,
            "amendment_date": amendment_date,
            "version": str(version) if version is not None else None,
            "retrieved_at": retrieved_at,
            "extraction_status": "extracted",
            "raw_text_present": True,
            "raw_text_chars": len(text),
            "sections": [
                {
                    "kind": s["kind"],
                    "heading": s["heading"],
                    "start": s["start"],
                    "end": s["end"],
                }
                for s in sections
            ],
            "eligibility_sections": elig_sections,
            "deadline_sections": deadline_sections,
            "amendment_sections": amendment_sections,
            "funding_origin_evidence": origin_sections,
            "restrictions": restriction_sections,
            "applicant_class_mentions": applicant_class_mentions,
            "recognition_mentions": recognition_mentions,
            "bare_keyword_mentions": bare_mentions,
            "dates_found": dates,
            "close_date_evidence": close_evidence,
            "evidence_quotes": evidence_quotes,
            # Two different questions, kept apart on purpose.
            "parser_confidence": parser_confidence,
            "eligibility_confidence": "none",
            "eligibility_text": eligibility_text,
            "eligibility_text_present": bool(eligibility_text),
            "human_review_required": human_review,
            "blocked_reasons": blocked_reasons,
            "keyword_counted_as_eligibility": False,
            "parser_confidence_used_as_eligibility_confidence": False,
            "live_fetch_performed": False,
            "freshness_claimed": False,
        }
    )


def extraction_invariant_failures(result: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    if result.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")

    status = result.get("extraction_status")
    if status not in {"extracted", "blocked"}:
        fails.append(f"unknown_extraction_status:{status}")

    if not result.get("raw_text_present") and status != "blocked":
        fails.append("missing_raw_text_did_not_block")

    if status == "blocked" and not result.get("blocked_reasons"):
        fails.append("blocked_without_a_reason")

    # A cited claim must carry a usable span.
    for q in result.get("evidence_quotes") or []:
        s, e = q.get("start"), q.get("end")
        if not isinstance(s, int) or not isinstance(e, int) or s < 0 or e <= s:
            field = q.get("field")
            fails.append(f"evidence_quote_without_a_valid_span:{field}")
        if not str(q.get("quote") or "").strip():
            fails.append(f"evidence_quote_without_text:{q.get('field')}")

    # A date may not claim more precision than its source string.
    for d in result.get("dates_found") or []:
        if d.get("precision") == "month" and d.get("certain"):
            fails.append(f"month_precision_date_claimed_certain:{d.get('raw')}")
        if d.get("uncertainty_markers") and d.get("certain"):
            fails.append(f"hedged_date_claimed_certain:{d.get('raw')}")

    # Missing close date is never presentable as firm.
    if not result.get("close_date") and result.get("close_date_certain"):
        fails.append("missing_close_date_claimed_certain")

    # Every recorded eligibility-context mention must actually be in one.
    for m in result.get("applicant_class_mentions") or []:
        if not m.get("in_eligibility_context"):
            phrase = m.get("phrase")
            fails.append(f"out_of_context_mention_recorded_as_eligibility:{phrase}")
        if m.get("section_kind") in NON_ELIGIBILITY_CONTEXT_KINDS:
            fails.append(f"mention_section_kind_disagrees:{m.get('phrase')}")

    if result.get("eligibility_confidence") not in {"none", "low", "medium", "high"}:
        fails.append("eligibility_confidence_out_of_vocabulary")

    for forbidden in (
        "keyword_counted_as_eligibility",
        "parser_confidence_used_as_eligibility_confidence",
        "live_fetch_performed",
        "freshness_claimed",
    ):
        if result.get(forbidden) is not False:
            fails.append(f"forbidden_claim:{forbidden}")

    return fails
