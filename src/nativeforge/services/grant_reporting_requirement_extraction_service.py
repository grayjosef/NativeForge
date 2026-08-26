"""Grant reporting requirement extraction (Gate 91H).

Reads post-award obligations out of deterministic document text.

## The rule, and why it is the whole module

**No obligation without evidence.**

Every requirement carries the quote that produced it, the character span it sits
at, and the document it came from. A requirement whose quote does not appear in
the source text is rejected by an invariant, not merely warned about.

This matters more here than anywhere else in the campaign. "Federal grants
generally require SF-425 quarterly" is true as background and is **not** a
finding about a specific notice. A burden profile assembled from federal-grant
folklore would look authoritative, be unfalsifiable, and send a customer
planning around deadlines nobody imposed. So a match is only ever a match
against text that is actually in front of us.

## Three distinctions that must survive

**Application vs post-award.** "Submit a budget narrative with your
application" is not a reporting obligation. Sections detected as application
instructions are extracted into a separate bucket and never counted as burden.

**Recipient vs subrecipient.** "Subrecipients must submit quarterly" binds
somebody the customer would pass money to, not the customer. Recorded on each
requirement, defaulting to ``unknown`` rather than ``recipient``.

**Required vs optional.** "Grantees are encouraged to report outcomes" is
guidance. Cue words are matched and the distinction is preserved; anything
without a clear obligation cue is ``human_review_required``.

## Deterministic, non-AI

Literal cue phrases and regular expressions over text produced by the Gate 81/82
adapters. No model, no embedding, no classifier - a test greps this source. The
same text produces the same requirements every time.

## What it does not do

No due date is inferred. A frequency of "quarterly" does **not** become four
dated deadlines: dating an obligation needs a stated date or customer-supplied
award terms, and Gate 91C's calendar puts undated obligations in their own list
rather than computing them.
"""

from __future__ import annotations

import json
import re
from typing import Any

SCHEMA_VERSION = "nf_grant_reporting_requirement_extraction_v1"

REQUIREMENT_CATEGORIES: tuple[str, ...] = (
    "reporting_requirements",
    "financial_requirements",
    "performance_requirements",
    "compliance_requirements",
    "closeout_requirements",
)

CONFIDENCES = frozenset({"quoted", "cued", "unclear"})

DUTY_HOLDERS = frozenset({"recipient", "subrecipient", "unknown"})

REQUIREMENT_FORCE = frozenset({"required", "optional_guidance", "unclear"})

TIMING = frozenset({"post_award", "application", "unclear"})

# Cue phrases that make an obligation binding. Matched literally.
OBLIGATION_CUES: tuple[str, ...] = (
    "must submit",
    "must provide",
    "must report",
    "must maintain",
    "must retain",
    "must comply",
    "is required to",
    "are required to",
    "shall submit",
    "shall provide",
    "shall report",
    "recipients must",
    "grantees must",
    "required to submit",
)

# Cue phrases that mark guidance rather than obligation.
OPTIONAL_CUES: tuple[str, ...] = (
    "are encouraged to",
    "is encouraged to",
    "may choose to",
    "recommended that",
    "best practice",
    "optional",
)

# Cues that bind a subrecipient rather than the recipient.
SUBRECIPIENT_CUES: tuple[str, ...] = (
    "subrecipient",
    "sub-recipient",
    "subawardee",
    "sub-award recipient",
)

# Cues that place a requirement at application time, not post-award.
APPLICATION_CUES: tuple[str, ...] = (
    "with your application",
    "with the application",
    "at time of application",
    "application package must",
    "to apply",
    "application must include",
)

# Category cue sets. A sentence may match more than one; each match becomes its
# own requirement so a quote is never split across categories.
CATEGORY_CUES: dict[str, tuple[str, ...]] = {
    "reporting_requirements": (
        "progress report", "performance report", "annual report",
        "quarterly report", "semi-annual report", "final report",
        "interim report", "sf-ppr", "report to the",
    ),
    "financial_requirements": (
        "sf-425", "federal financial report", "financial report",
        "drawdown", "cost share", "match requirement", "matching funds",
        "indirect cost", "single audit", "audit requirement",
        # Application-time financial documents. Cued here so they are
        # *detected*, then routed to the application bucket by their timing -
        # a sentence matching no category at all is dropped silently, which
        # would hide an application requirement rather than separate it.
        "budget narrative", "budget justification", "budget detail",
    ),
    "performance_requirements": (
        "performance measure", "performance indicator", "outcome data",
        "participant data", "demographic data", "evaluation plan",
        "data collection", "track participants",
    ),
    "compliance_requirements": (
        "certification", "assurance", "civil rights", "environmental review",
        "tribal resolution", "record retention", "retain records",
        "procurement standard", "monitor subrecipient", "data security",
    ),
    "closeout_requirements": (
        "closeout", "close-out", "final financial report",
        "final performance report", "liquidate", "final invention statement",
    ),
}

# Frequency cues. Recorded as stated - never expanded into dates.
FREQUENCY_CUES: dict[str, str] = {
    "quarterly": "quarterly",
    "semi-annual": "semi_annual",
    "semiannual": "semi_annual",
    "annually": "annual",
    "annual": "annual",
    "monthly": "monthly",
    "final": "final",
    "within 90 days": "within_90_days",
    "within 120 days": "within_120_days",
}

_SENTENCE_SPLIT = re.compile(r"(?<=[.;:])\s+|\n{2,}")
_MAX_QUOTE = 400


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _sentences_with_spans(text: str) -> list[tuple[str, int, int]]:
    """Split into sentences, keeping each one's character span."""
    out: list[tuple[str, int, int]] = []
    cursor = 0
    for piece in _SENTENCE_SPLIT.split(text):
        if piece is None:
            continue
        start = text.find(piece, cursor)
        if start < 0:
            continue
        end = start + len(piece)
        cursor = end
        stripped = piece.strip()
        if stripped:
            offset = piece.index(stripped)
            out.append((stripped, start + offset, start + offset + len(stripped)))
    return out


def _first_cue(haystack: str, cues: tuple[str, ...]) -> str | None:
    for cue in cues:
        if cue in haystack:
            return cue
    return None


def extract_reporting_requirements(
    *,
    document_id: str,
    text: str | None,
    owner_type: str = "opportunity",
    owner_id: str | None = None,
    is_post_award_document: bool = False,
) -> dict[str, Any]:
    """Extract obligations from one document's deterministic text."""
    blocked: list[str] = []

    if not text or not text.strip():
        return _json_safe(
            {
                "schema_version": SCHEMA_VERSION,
                "document_id": document_id,
                "owner_type": owner_type,
                "owner_id": owner_id,
                **{c: [] for c in REQUIREMENT_CATEGORIES},
                "application_requirements": [],
                "human_review_items": [],
                "requirement_count": 0,
                "blocked_reasons": ["no_document_text"],
                "extraction_complete": False,
                "ai_used": False,
                "network_access_performed": False,
                "deterministic": True,
                "fabricated": False,
            }
        )

    lowered = text.lower()
    categories: dict[str, list[dict[str, Any]]] = {
        c: [] for c in REQUIREMENT_CATEGORIES
    }
    application_requirements: list[dict[str, Any]] = []
    human_review: list[dict[str, Any]] = []

    for sentence, start, end in _sentences_with_spans(text):
        low = sentence.lower()

        obligation_cue = _first_cue(low, OBLIGATION_CUES)
        optional_cue = _first_cue(low, OPTIONAL_CUES)
        application_cue = _first_cue(low, APPLICATION_CUES)
        subrecipient_cue = _first_cue(low, SUBRECIPIENT_CUES)

        matched_categories = [
            category
            for category, cues in CATEGORY_CUES.items()
            if _first_cue(low, cues)
        ]
        if not matched_categories:
            continue

        if obligation_cue and not optional_cue:
            force = "required"
        elif optional_cue and not obligation_cue:
            force = "optional_guidance"
        elif obligation_cue and optional_cue:
            force = "unclear"
        else:
            force = "unclear"

        if application_cue:
            timing = "application"
        elif is_post_award_document or obligation_cue:
            timing = "post_award"
        else:
            timing = "unclear"
        duty_holder = "subrecipient" if subrecipient_cue else (
            "recipient" if obligation_cue else "unknown"
        )

        frequency = None
        for cue, normalised in FREQUENCY_CUES.items():
            if cue in low:
                frequency = normalised
                break

        quote = sentence[:_MAX_QUOTE]
        needs_review = (
            force != "required"
            or timing == "unclear"
            or duty_holder == "unknown"
        )

        for category in matched_categories:
            requirement = {
                "requirement_name": _first_cue(low, CATEGORY_CUES[category]),
                "report_name": _first_cue(low, CATEGORY_CUES[category])
                if category == "reporting_requirements"
                else None,
                "category": category,
                "report_frequency": frequency,
                # No date is produced. Ever.
                "due_date": None,
                "first_due_date": None,
                "requirement_force": force,
                "timing": timing,
                "duty_holder": duty_holder,
                "evidence_quote": quote,
                "evidence_location": {"start": start, "end": end},
                "source_document_id": document_id,
                "confidence": "quoted" if force == "required" else "cued",
                "human_review_required": needs_review,
                "blocked_reasons": (
                    [] if not needs_review else [f"requirement_force:{force}"]
                ),
                "customer_provided": False,
            }

            if timing == "application":
                # Not burden. Kept, separately, so it is visible without being
                # counted as a post-award obligation.
                application_requirements.append(requirement)
            else:
                categories[category].append(requirement)

            if needs_review:
                human_review.append(
                    {
                        "category": category,
                        "reason": f"force={force} timing={timing} duty={duty_holder}",
                        "evidence_quote": quote,
                        "source_document_id": document_id,
                    }
                )

    requirement_count = sum(len(v) for v in categories.values())

    # Every quote must actually be in the text. Cheap to check, and it is the
    # difference between an extraction and an assertion.
    for items in categories.values():
        for item in items:
            if item["evidence_quote"] not in text:
                blocked.append(
                    f"quote_not_found_in_source:{item['evidence_quote'][:40]}"
                )

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "document_id": document_id,
            "owner_type": owner_type,
            "owner_id": owner_id,
            **categories,
            # Application-time requirements, deliberately outside the categories.
            "application_requirements": application_requirements,
            "human_review_items": human_review,
            "requirement_count": requirement_count,
            "application_requirement_count": len(application_requirements),
            "blocked_reasons": blocked,
            "extraction_complete": True,
            "text_length": len(text),
            "lowered_length": len(lowered),
            # Constants.
            "ai_used": False,
            "network_access_performed": False,
            "deterministic": True,
            "dates_inferred": 0,
            "fabricated": False,
        }
    )


def extraction_invariant_failures(
    result: dict[str, Any], *, source_text: str | None = None
) -> list[str]:
    fails: list[str] = []

    if result.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")
    if result.get("fabricated") is not False:
        fails.append("fabricated_must_be_false")
    if result.get("ai_used") is not False:
        fails.append("ai_used_for_extraction")
    if result.get("network_access_performed") is not False:
        fails.append("extraction_performed_network_access")
    if result.get("deterministic") is not True:
        fails.append("extraction_not_marked_deterministic")
    if result.get("dates_inferred"):
        fails.append("extraction_inferred_a_date")

    all_items: list[dict[str, Any]] = []
    for category in REQUIREMENT_CATEGORIES:
        all_items.extend(result.get(category) or [])

    for item in all_items:
        name = item.get("requirement_name")

        # The central rule.
        quote = str(item.get("evidence_quote") or "").strip()
        if not quote:
            fails.append(f"requirement_without_evidence_quote:{name}")
        elif source_text is not None and quote not in source_text:
            fails.append(f"quote_not_present_in_source:{name}")

        location = item.get("evidence_location") or {}
        if location.get("start") is None or location.get("end") is None:
            fails.append(f"requirement_without_span:{name}")
        elif location["start"] > location["end"]:
            fails.append(f"requirement_span_inverted:{name}")

        if not item.get("source_document_id"):
            fails.append(f"requirement_without_source_document:{name}")

        if item.get("confidence") not in CONFIDENCES:
            fails.append(f"confidence_out_of_vocabulary:{name}")
        if item.get("duty_holder") not in DUTY_HOLDERS:
            fails.append(f"duty_holder_out_of_vocabulary:{name}")
        if item.get("requirement_force") not in REQUIREMENT_FORCE:
            fails.append(f"requirement_force_out_of_vocabulary:{name}")
        if item.get("timing") not in TIMING:
            fails.append(f"timing_out_of_vocabulary:{name}")

        # No due date may be produced by extraction at all.
        if item.get("due_date") or item.get("first_due_date"):
            fails.append(f"extraction_produced_a_due_date:{name}")

        # An application-time requirement must never sit in a burden category.
        if item.get("timing") == "application":
            fails.append(f"application_requirement_in_post_award_category:{name}")

        # Anything not clearly required must be flagged.
        if item.get("requirement_force") != "required" and not item.get(
            "human_review_required"
        ):
            fails.append(f"non_required_requirement_not_flagged:{name}")

    # Application requirements must carry the application timing.
    for item in result.get("application_requirements") or []:
        if item.get("timing") != "application":
            fails.append("application_bucket_holds_a_non_application_requirement")

    return fails
