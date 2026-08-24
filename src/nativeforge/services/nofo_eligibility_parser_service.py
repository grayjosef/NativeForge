"""Applicant eligibility parsing from notice text (Gate 81C).

Reads the eligibility sections found by :mod:`nofo_text_extraction_service` and
decides, per applicant class, what the text actually supports - with a character
span for every claim.

Why this exists on top of Gate 79's exclusion service, which already analyses
eligibility prose:

  * **Context.** ``analyse_eligibility_text`` analyses whatever string it is
    handed. Nothing stopped a caller passing an entire notice, so the word
    "tribal" in a background paragraph read exactly like an eligibility rule.
    Here, only text inside a detected eligibility section is ever considered.
  * **Citation.** That analyser returns class *names*, never where it found
    them. Gate 79 requires a citation for any exclusion but could not supply
    one. Every finding here carries ``start``/``end`` offsets and a quote.
  * **Non-Native classes.** It knows seven Native classes. A notice reading
    "only units of local government may apply" names none of them, so the list
    never registered as exclusive and a tribe came back
    ``not_supported_by_evidence`` when the text plainly excluded them.

The vocabulary is a **superset**, never a fork:
``APPLICANT_CLASSES`` (canonical, Gate 79) is a strict subset of
``PARSER_APPLICANT_CLASSES``, and a test pins that. The four extra classes exist
only to make exclusive lists readable; they are dropped before anything reaches
the canonical exclusion service.

Nothing here fetches.
"""

from __future__ import annotations

import json
import re
from typing import Any

from nativeforge.services.eligibility_exclusion_evidence_service import (
    APPLICANT_CLASSES,
    CLASS_PHRASES,
    EXCLUSIVITY_MARKERS,
    RESTRICTION_PHRASES,
    evaluate_all_applicant_classes,
)
from nativeforge.services.nofo_text_extraction_service import (
    ELIGIBILITY_CONTEXT_KINDS,
    find_phrase_spans,
)

SCHEMA_VERSION = "nf_nofo_eligibility_parser_v1"
PARSER_VERSION = "gate81_v1"

# Classes the canonical exclusion service does not know. They are here so an
# exclusive list built entirely from them is legible - which is the only way to
# evidence the exclusion of a class the text never names.
NON_NATIVE_CLASSES = frozenset(
    {
        "local_government",
        "state_government",
        "nonprofit",
        "education_institution",
    }
)

# Superset of the canonical set. Asserted, not assumed - see the drift test.
PARSER_APPLICANT_CLASSES = frozenset(APPLICANT_CLASSES) | NON_NATIVE_CLASSES

NON_NATIVE_CLASS_PHRASES: dict[str, tuple[str, ...]] = {
    "local_government": (
        "unit of local government",
        "units of local government",
        "local government",
        "local governments",
        "county government",
        "municipal government",
        "municipalities",
        "cities and counties",
    ),
    "state_government": (
        "state government",
        "state agency",
        "state agencies",
        "state department",
        "instrumentality of the state",
    ),
    "nonprofit": (
        "nonprofit organization",
        "nonprofit organizations",
        "non-profit organization",
        "501(c)(3)",
        "not-for-profit organization",
    ),
    "education_institution": (
        "institution of higher education",
        "institutions of higher education",
        "local educational agency",
        "school district",
        "public school",
        "college or university",
    ),
}

# The combined map used for detection. CLASS_PHRASES is imported, never copied,
# so the canonical phrasing stays owned by one module.
ALL_CLASS_PHRASES: dict[str, tuple[str, ...]] = {
    **CLASS_PHRASES,
    **NON_NATIVE_CLASS_PHRASES,
}

# Cues that a sentence is removing a class rather than admitting it.
NEGATION_CUES: tuple[str, ...] = (
    "are not eligible",
    "is not eligible",
    "not eligible",
    "are ineligible",
    "is ineligible",
    "ineligible",
    "may not apply",
    "are excluded",
    "is excluded",
    "excluding",
    "does not include",
    "do not include",
    "are not considered eligible",
    "shall not be eligible",
)

# Sentence boundaries. Deliberately coarse: a negation and the class it negates
# almost always share a sentence, and widening the window past that starts
# attaching negations to classes several clauses away.
_SENTENCE_SPLIT = re.compile(r"(?<=[.;:!?])\s+|\n+")

_MAX_QUOTE_CHARS = 300


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _clip(text: str, limit: int = _MAX_QUOTE_CHARS) -> str:
    t = re.sub(r"\s+", " ", text).strip()
    return t if len(t) <= limit else t[: limit - 3].rstrip() + "..."


def _sentences(text: str, base_offset: int) -> list[tuple[int, int, str]]:
    """Yield (absolute_start, absolute_end, sentence_text)."""
    out: list[tuple[int, int, str]] = []
    pos = 0
    for part in _SENTENCE_SPLIT.split(text):
        if part is None:
            continue
        idx = text.find(part, pos)
        if idx < 0:
            continue
        out.append((base_offset + idx, base_offset + idx + len(part), part))
        pos = idx + len(part)
    return out


def eligibility_spans_from_extraction(
    extraction: dict[str, Any], raw_text: str | None
) -> list[tuple[int, int, str]]:
    """Recover (start, end, text) for each eligibility section.

    Spans stay absolute against ``raw_text`` so a citation points into the real
    notice. Without ``raw_text`` only the clipped section quotes survive, and
    the caller is told the spans are not absolute.
    """
    sections = [
        s
        for s in (extraction.get("sections") or [])
        if s.get("kind") in ELIGIBILITY_CONTEXT_KINDS
    ]
    if raw_text:
        return [
            (int(s["start"]), int(s["end"]), raw_text[int(s["start"]) : int(s["end"])])
            for s in sections
        ]
    quoted = extraction.get("eligibility_sections") or []
    return [
        (int(s.get("start", 0)), int(s.get("end", 0)), str(s.get("quote") or ""))
        for s in quoted
    ]


def find_class_mentions(
    spans: list[tuple[int, int, str]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Locate class phrases and negations inside eligibility text only.

    Returns ``(mentions, negations)``. A mention is evidence that the text
    *names* a class; whether that naming admits or removes the class is decided
    by the negation in the same sentence.
    """
    mentions: list[dict[str, Any]] = []
    negations: list[dict[str, Any]] = []

    for base, _end, text in spans:
        sentences = _sentences(text, base)

        for cls, phrases in ALL_CLASS_PHRASES.items():
            for phrase, rel_start, rel_end in find_phrase_spans(text, phrases):
                abs_start = base + rel_start
                abs_end = base + rel_end
                sentence = next(
                    (s for s in sentences if s[0] <= abs_start < s[1]),
                    (base, base + len(text), text),
                )
                # Whitespace-collapse the sentence too, so a cue wrapped across
                # a line break is still seen.
                flat = re.sub(r"\s+", " ", sentence[2]).lower()
                cues = sorted({c for c in NEGATION_CUES if c in flat})
                record = {
                    "applicant_class": cls,
                    "phrase": phrase,
                    "start": abs_start,
                    "end": abs_end,
                    "quote": _clip(sentence[2]),
                    "sentence_start": sentence[0],
                    "sentence_end": sentence[1],
                    "negation_cues": cues,
                    "negated": bool(cues),
                    "canonical": cls in APPLICANT_CLASSES,
                }
                mentions.append(record)
                if cues:
                    negations.append(record)

    mentions.sort(key=lambda d: (d["start"], d["applicant_class"]))
    negations.sort(key=lambda d: (d["start"], d["applicant_class"]))
    return mentions, negations


def find_restrictions(spans: list[tuple[int, int, str]]) -> list[dict[str, Any]]:
    """Locate restriction language and keep it as a restriction.

    "Federal trust land" narrows how an award may be used. It is not a statement
    about who may apply, and promoting it to eligibility would silently rewrite
    a land-use condition into an applicant rule.
    """
    out: list[dict[str, Any]] = []
    for base, _end, text in spans:
        for name, phrases in RESTRICTION_PHRASES.items():
            for phrase, rel_start, rel_end in find_phrase_spans(text, phrases):
                out.append(
                    {
                        "restriction": name,
                        "phrase": phrase,
                        "start": base + rel_start,
                        "end": base + rel_end,
                        "quote": _clip(text[max(0, rel_start - 90) : rel_end + 90]),
                        "is_eligibility_rule": False,
                    }
                )
    out.sort(key=lambda d: d["start"])
    return out


def parse_nofo_eligibility(
    *,
    opportunity_id: str,
    extraction: dict[str, Any],
    raw_text: str | None = None,
    evidence_reference: str | None = None,
    additional_expanding_evidence: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Parse one notice's eligibility sections into a cited, per-class verdict."""
    review_reasons: list[str] = []

    if extraction.get("extraction_status") == "blocked":
        review_reasons.append("extraction_blocked")
        return _blocked(opportunity_id, review_reasons, extraction)

    spans = eligibility_spans_from_extraction(extraction, raw_text)
    spans_absolute = bool(raw_text)
    if not spans:
        review_reasons.append("no_eligibility_section_to_parse")
        return _blocked(opportunity_id, review_reasons, extraction)

    eligibility_text = "\n".join(t for _s, _e, t in spans)
    mentions, negations = find_class_mentions(spans)
    restrictions = find_restrictions(spans)

    named = sorted({m["applicant_class"] for m in mentions if not m["negated"]})
    negated = sorted({m["applicant_class"] for m in negations})
    # A class named in one sentence and negated in another is a conflict we are
    # not entitled to resolve.
    conflicting = sorted(set(named) & set(negated))
    if conflicting:
        review_reasons.append("class_named_and_negated:" + ",".join(conflicting))

    markers_present = any(
        marker in eligibility_text.lower() for marker in EXCLUSIVITY_MARKERS
    )
    if markers_present and not named and not negated:
        # "Eligibility is limited to ..." followed by something no vocabulary
        # recognises. Exclusive, but we cannot say who it admits.
        review_reasons.append("exclusive_list_names_no_recognised_class")

    # A citation is the notice itself plus the span. Without any locator there
    # is nothing to cite, and Gate 79 refuses to exclude uncited.
    reference = evidence_reference or extraction.get("notice_url") or extraction.get(
        "source_url"
    )
    if not reference:
        review_reasons.append("no_citable_reference_for_this_notice")

    # Only the four extra classes are passed as "additional"; canonical ones
    # already have an owner and must not be double-declared.
    additional_named = sorted(
        c for c in named if c in NON_NATIVE_CLASSES
    )
    canonical_negated = sorted(c for c in negated if c in APPLICANT_CLASSES)

    exclusion_result = evaluate_all_applicant_classes(
        opportunity_id=opportunity_id,
        eligibility_text=eligibility_text,
        evidence_reference=reference,
        additional_expanding_evidence=additional_expanding_evidence,
        additional_named_classes=additional_named,
        negated_classes=canonical_negated,
    )

    human_review = bool(review_reasons) or not reference

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "parser_version": PARSER_VERSION,
            "opportunity_id": opportunity_id,
            "notice_id": extraction.get("notice_id"),
            "parse_status": "parsed",
            "spans_absolute": spans_absolute,
            "eligibility_section_count": len(spans),
            "eligibility_text_present": bool(eligibility_text.strip()),
            "class_mentions": mentions,
            "named_classes": named,
            "negated_classes": negated,
            "conflicting_classes": conflicting,
            "additional_named_classes": additional_named,
            "restrictions": restrictions,
            "restriction_names": sorted({r["restriction"] for r in restrictions}),
            "exclusivity_markers_present": markers_present,
            "evidence_reference": reference,
            "has_citation": bool(reference),
            # Canonical, per-class, and directly feedable to
            # native_opportunity_discovery_service(exclusion_result=...).
            "exclusion_result": exclusion_result,
            "excluded_classes": exclusion_result.get("excluded_classes") or [],
            "eligible_classes": exclusion_result.get("eligible_classes") or [],
            "human_review_required": human_review,
            "review_reasons": review_reasons,
            # Boundaries.
            "not_eligible_asserted": False,
            "keyword_counted_as_eligibility": False,
            "restriction_counted_as_eligibility": False,
            "coverage_claimed": False,
            "live_fetch_performed": False,
        }
    )


def _blocked(
    opportunity_id: str, review_reasons: list[str], extraction: dict[str, Any]
) -> dict[str, Any]:
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "parser_version": PARSER_VERSION,
            "opportunity_id": opportunity_id,
            "notice_id": extraction.get("notice_id"),
            "parse_status": "blocked",
            "spans_absolute": False,
            "eligibility_section_count": 0,
            "eligibility_text_present": False,
            "class_mentions": [],
            "named_classes": [],
            "negated_classes": [],
            "conflicting_classes": [],
            "additional_named_classes": [],
            "restrictions": [],
            "restriction_names": [],
            "exclusivity_markers_present": False,
            "evidence_reference": None,
            "has_citation": False,
            "exclusion_result": None,
            "excluded_classes": [],
            "eligible_classes": [],
            "human_review_required": True,
            "review_reasons": review_reasons,
            "not_eligible_asserted": False,
            "keyword_counted_as_eligibility": False,
            "restriction_counted_as_eligibility": False,
            "coverage_claimed": False,
            "live_fetch_performed": False,
        }
    )


def parser_invariant_failures(result: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    if result.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")

    if result.get("parse_status") not in {"parsed", "blocked"}:
        fails.append(f"unknown_parse_status:{result.get('parse_status')}")

    if result.get("parse_status") == "blocked":
        if not result.get("review_reasons"):
            fails.append("blocked_without_a_reason")
        if result.get("excluded_classes"):
            fails.append("blocked_parse_produced_exclusions")

    # Every class this parser reports must belong to the superset.
    for cls in (result.get("named_classes") or []) + (
        result.get("negated_classes") or []
    ):
        if cls not in PARSER_APPLICANT_CLASSES:
            fails.append(f"class_outside_parser_vocabulary:{cls}")

    # Only canonical classes may reach the exclusion contract.
    for cls in result.get("excluded_classes") or []:
        if cls not in APPLICANT_CLASSES:
            fails.append(f"non_canonical_class_in_exclusion_result:{cls}")

    # No exclusion without a citation.
    if result.get("excluded_classes") and not result.get("has_citation"):
        fails.append("exclusion_without_citation")

    # A conflict must never resolve itself into a confident answer.
    if result.get("conflicting_classes") and not result.get("human_review_required"):
        fails.append("conflicting_classes_without_human_review")

    # Every cited mention must carry a usable span.
    for m in result.get("class_mentions") or []:
        s, e = m.get("start"), m.get("end")
        if not isinstance(s, int) or not isinstance(e, int) or s < 0 or e <= s:
            fails.append(f"mention_without_a_valid_span:{m.get('applicant_class')}")

    # Restrictions stay restrictions.
    for r in result.get("restrictions") or []:
        if r.get("is_eligibility_rule") is not False:
            fails.append(f"restriction_promoted_to_eligibility:{r.get('restriction')}")

    overlap = set(result.get("eligible_classes") or []) & set(
        result.get("excluded_classes") or []
    )
    if overlap:
        fails.append(f"class_both_eligible_and_excluded:{sorted(overlap)}")

    for forbidden in (
        "not_eligible_asserted",
        "keyword_counted_as_eligibility",
        "restriction_counted_as_eligibility",
        "coverage_claimed",
        "live_fetch_performed",
    ):
        if result.get(forbidden) is not False:
            fails.append(f"forbidden_claim:{forbidden}")

    return fails
