"""Gate 175E/F/H/K: facts read out of documents, and what to do when they
disagree.

A fact here is never just a value. It carries the document it came from, the
section or page it was read at, the method that read it, and a confidence -
because the whole point of document intelligence is that somebody can be shown
WHERE the answer came from when they ask.

**Conflicts are represented, not resolved.** If the landing page says the
deadline is 1 November and the NOFO says 15 November, NativeForge does not
quietly pick one. It records both, names the disagreement, and applies an
authority rule only where that rule is explicit and evidence-backed:

```text
an AMENDMENT supersedes what it amends          (the funder said so)
an FAQ CLARIFIES without erasing the original   (both survive)
a NOFO outranks a landing-page summary          (the notice is the notice)
anything else -> REVIEW_REQUIRED
```

That last line is the important one. A silent resolution is a guess wearing a
value, and the person who finds out it was wrong is the one whose application
was rejected.

**A fact from an appendix is still a fact.** 175H exists because pipelines
routinely read the NOFO body and stop. The match requirement is in Appendix C;
the eligibility carve-out is in the FAQ published a month later. Those are
binding, and they are cited to their own document.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from nativeforge.services.opportunity_document_service import (
    ABSENCE_IS_MEANINGFUL,
    APPENDIX,
    CLARIFYING_TYPES,
    FAQ,
    NO_FACTS_POSSIBLE,
    NOFO,
    SUPERSEDING_TYPES,
    WEBPAGE,
)

SCHEMA_VERSION = "nf_document_fact_extraction_v1"

# --------------------------------------------------------------------
# 175E: what can be extracted
# --------------------------------------------------------------------

ELIGIBILITY = "ELIGIBILITY"
DEADLINE = "DEADLINE"
FUNDING_AMOUNT = "FUNDING_AMOUNT"
AWARD_FLOOR = "AWARD_FLOOR"
AWARD_CEILING = "AWARD_CEILING"
ESTIMATED_AWARDS = "ESTIMATED_AWARDS"
COST_SHARE = "COST_SHARE"
PERIOD_OF_PERFORMANCE = "PERIOD_OF_PERFORMANCE"
GEOGRAPHY = "GEOGRAPHY"
CONTACT = "CONTACT"
SUBMISSION_METHOD = "SUBMISSION_METHOD"
REQUIRED_DOCUMENTS = "REQUIRED_DOCUMENTS"
EVALUATION_CRITERIA = "EVALUATION_CRITERIA"
PROGRAM_PURPOSE = "PROGRAM_PURPOSE"
NATIVE_RELEVANCE = "NATIVE_RELEVANCE"
SPECIAL_REQUIREMENT = "SPECIAL_REQUIREMENT"

FACT_KINDS: tuple[str, ...] = (
    ELIGIBILITY,
    DEADLINE,
    FUNDING_AMOUNT,
    AWARD_FLOOR,
    AWARD_CEILING,
    ESTIMATED_AWARDS,
    COST_SHARE,
    PERIOD_OF_PERFORMANCE,
    GEOGRAPHY,
    CONTACT,
    SUBMISSION_METHOD,
    REQUIRED_DOCUMENTS,
    EVALUATION_CRITERIA,
    PROGRAM_PURPOSE,
    NATIVE_RELEVANCE,
    SPECIAL_REQUIREMENT,
)

#: Fact kinds where a disagreement changes what somebody does. A contact
#: mismatch is untidy; a deadline mismatch loses a cycle.
MATERIAL_KINDS: frozenset[str] = frozenset(
    {ELIGIBILITY, DEADLINE, COST_SHARE, SUBMISSION_METHOD, AWARD_CEILING}
)

EXTRACTED_BY_RULE = "EXTRACTED_BY_RULE"
EXTRACTED_BY_PARSER = "EXTRACTED_BY_PARSER"
ASSERTED_BY_HUMAN = "ASSERTED_BY_HUMAN"
EXTRACTION_METHODS: tuple[str, ...] = (
    EXTRACTED_BY_RULE,
    EXTRACTED_BY_PARSER,
    ASSERTED_BY_HUMAN,
)

HIGH = "HIGH"
MEDIUM = "MEDIUM"
LOW = "LOW"
CONFIDENCE_LEVELS: tuple[str, ...] = (HIGH, MEDIUM, LOW)

FACT_FIELDS: tuple[str, ...] = (
    "fact_id",
    "canonical_id",
    "document_id",
    "fact_kind",
    "value",
    "source_text",
    "section_ref",
    "page_ref",
    "extraction_method",
    "confidence",
    "document_type",
    "observed_at",
)

# --------------------------------------------------------------------
# 175F: conflicts
# --------------------------------------------------------------------

AMENDMENT_SUPERSEDES = "AMENDMENT_SUPERSEDES"
NOTICE_OUTRANKS_SUMMARY = "NOTICE_OUTRANKS_SUMMARY"
FAQ_CLARIFIES = "FAQ_CLARIFIES"
UNRESOLVED = "UNRESOLVED"

RESOLUTION_RULES: tuple[str, ...] = (
    AMENDMENT_SUPERSEDES,
    NOTICE_OUTRANKS_SUMMARY,
    FAQ_CLARIFIES,
    UNRESOLVED,
)

RESOLUTION_MEANINGS: dict[str, str] = {
    AMENDMENT_SUPERSEDES: (
        "the funder issued an amendment; its value replaces the earlier one "
        "and the earlier one is retained"
    ),
    NOTICE_OUTRANKS_SUMMARY: (
        "the notice document is authoritative over a landing-page summary of it"
    ),
    FAQ_CLARIFIES: (
        "an FAQ explains the original without replacing it; BOTH values remain "
        "on file and the pair goes to review"
    ),
    UNRESOLVED: (
        "no explicit, evidence-backed rule applies - a human decides, and "
        "nothing is silently chosen"
    ),
}

#: Rules that actually select a winner. `FAQ_CLARIFIES` is deliberately absent:
#: a clarification adds meaning and does not overwrite.
SELECTS_A_WINNER: frozenset[str] = frozenset(
    {AMENDMENT_SUPERSEDES, NOTICE_OUTRANKS_SUMMARY}
)


def _json_safe(value: Any) -> Any:
    json.dumps(value, default=str)
    return value


def build_fact_id(
    *,
    canonical_id: Any,
    document_id: Any,
    fact_kind: Any,
    section_ref: Any = None,
) -> str:
    parts = [
        str(canonical_id or ""),
        str(document_id or ""),
        str(fact_kind or ""),
        str(section_ref or ""),
    ]
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()


def build_fact(
    *,
    canonical_id: Any,
    document: dict[str, Any],
    fact_kind: str,
    value: Any,
    source_text: Any,
    section_ref: Any = None,
    page_ref: Any = None,
    extraction_method: str = EXTRACTED_BY_PARSER,
    confidence: str = MEDIUM,
    observed_at: Any = None,
) -> dict[str, Any]:
    """One fact, bound to the document and the place within it."""
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "fact_id": build_fact_id(
                canonical_id=canonical_id,
                document_id=document.get("document_id"),
                fact_kind=fact_kind,
                section_ref=section_ref,
            ),
            "canonical_id": str(canonical_id) if canonical_id else None,
            "document_id": str(document.get("document_id") or "") or None,
            "document_type": str(document.get("document_type") or "") or None,
            "fact_kind": str(fact_kind),
            "value": value,
            # The funder's own words. A value without them cannot be shown to
            # anybody who disputes it.
            "source_text": str(source_text) if source_text is not None else None,
            "section_ref": str(section_ref) if section_ref else None,
            "page_ref": int(page_ref) if page_ref is not None else None,
            "extraction_method": str(extraction_method),
            "confidence": str(confidence),
            "observed_at": observed_at,
            "is_material": str(fact_kind) in MATERIAL_KINDS,
        }
    )


def fact_invariant_failures(
    fact: dict[str, Any], *, document: dict[str, Any] | None = None
) -> list[str]:
    """Refuse a fact that cannot be cited or that a document cannot support."""
    failures: list[str] = []

    for field in FACT_FIELDS:
        if field not in fact:
            failures.append(f"fact_missing_field:{field}")

    kind = str(fact.get("fact_kind") or "")
    if kind not in FACT_KINDS:
        failures.append(f"fact_kind_outside_the_vocabulary:{kind or 'missing'}")

    if str(fact.get("extraction_method") or "") not in EXTRACTION_METHODS:
        failures.append(
            f"extraction_method_outside_the_vocabulary:{fact.get('extraction_method')}"
        )
    if str(fact.get("confidence") or "") not in CONFIDENCE_LEVELS:
        failures.append(f"confidence_outside_the_vocabulary:{fact.get('confidence')}")

    if not fact.get("canonical_id"):
        failures.append("fact_not_bound_to_a_canonical_opportunity")
    # The rule 175N names: a citation requires a document.
    if not fact.get("document_id"):
        failures.append("fact_has_no_document")
    if fact.get("value") in (None, "", [], {}):
        failures.append("fact_has_no_value")
    if not fact.get("source_text"):
        failures.append("fact_has_no_source_text")

    page = fact.get("page_ref")
    if page is not None and int(page) < 1:
        failures.append(f"page_reference_is_not_a_page:{page}")

    if document is not None:
        state = str(document.get("document_state") or "")
        if state in NO_FACTS_POSSIBLE:
            failures.append(f"fact_extracted_from_a_document_in_state_{state}")
        if str(document.get("document_id")) != str(fact.get("document_id")):
            failures.append("fact_cites_a_different_document")
        # A citation beyond the document's own page count is not a citation.
        pages = document.get("page_count")
        if page is not None and pages is not None and int(page) > int(pages):
            failures.append(f"citation_page_{page}_is_outside_a_{pages}_page_document")

    return sorted(set(failures))


def _resolution_for(
    a: dict[str, Any], b: dict[str, Any]
) -> tuple[str, str | None, str]:
    """Which rule applies, which fact wins, and why. Deny by default."""
    a_type = str(a.get("document_type") or "")
    b_type = str(b.get("document_type") or "")

    if a_type in SUPERSEDING_TYPES and b_type not in SUPERSEDING_TYPES:
        return AMENDMENT_SUPERSEDES, str(a["fact_id"]), "an amendment supersedes"
    if b_type in SUPERSEDING_TYPES and a_type not in SUPERSEDING_TYPES:
        return AMENDMENT_SUPERSEDES, str(b["fact_id"]), "an amendment supersedes"

    if a_type in CLARIFYING_TYPES or b_type in CLARIFYING_TYPES:
        # Both survive. Nothing is chosen.
        return FAQ_CLARIFIES, None, "a clarification does not replace"

    notice_types = {NOFO, "FOA", "RFP", "RFA", APPENDIX}
    if a_type in notice_types and b_type == WEBPAGE:
        return NOTICE_OUTRANKS_SUMMARY, str(a["fact_id"]), "the notice is the notice"
    if b_type in notice_types and a_type == WEBPAGE:
        return NOTICE_OUTRANKS_SUMMARY, str(b["fact_id"]), "the notice is the notice"

    return UNRESOLVED, None, "no explicit authority rule applies"


def detect_conflicts(facts: list[dict[str, Any]]) -> dict[str, Any]:
    """175F: find disagreements and represent them. Never choose silently."""
    by_kind: dict[str, list[dict[str, Any]]] = {}
    for fact in facts:
        by_kind.setdefault(str(fact.get("fact_kind")), []).append(fact)

    conflicts: list[dict[str, Any]] = []
    for kind, group in sorted(by_kind.items()):
        values = {
            json.dumps(f.get("value"), sort_keys=True, default=str) for f in group
        }
        if len(values) < 2:
            continue
        # Pairwise, so an operator sees which two documents disagree.
        for index, a in enumerate(group):
            for b in group[index + 1 :]:
                if json.dumps(
                    a.get("value"), sort_keys=True, default=str
                ) == json.dumps(b.get("value"), sort_keys=True, default=str):
                    continue
                rule, winner, why = _resolution_for(a, b)
                conflicts.append(
                    {
                        "conflict_id": hashlib.sha256(
                            f"{a['fact_id']}|{b['fact_id']}".encode()
                        ).hexdigest(),
                        "canonical_id": a.get("canonical_id"),
                        "fact_kind": kind,
                        "fact_ids": sorted([str(a["fact_id"]), str(b["fact_id"])]),
                        "documents": sorted(
                            [str(a["document_id"]), str(b["document_id"])]
                        ),
                        "document_types": sorted(
                            [
                                str(a["document_type"]),
                                str(b["document_type"]),
                            ]
                        ),
                        "values": [a.get("value"), b.get("value")],
                        "resolution_rule": rule,
                        "winning_fact_id": winner,
                        "why": why,
                        "is_material": kind in MATERIAL_KINDS,
                        # Both values are retained, always.
                        "both_values_retained": True,
                        "review_required": rule not in SELECTS_A_WINNER,
                    }
                )

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "fact_count": len(facts),
            "conflict_count": len(conflicts),
            "conflicts": conflicts,
            "material_conflict_count": sum(1 for c in conflicts if c["is_material"]),
            "unresolved_count": sum(
                1 for c in conflicts if c["resolution_rule"] == UNRESOLVED
            ),
            "review_required_count": sum(1 for c in conflicts if c["review_required"]),
            "nothing_was_silently_resolved": all(
                c["resolution_rule"] in SELECTS_A_WINNER or c["review_required"]
                for c in conflicts
            ),
        }
    )


def conflict_invariant_failures(conflict: dict[str, Any]) -> list[str]:
    """Refuse a conflict record that discards a value or picks without a rule."""
    failures: list[str] = []

    rule = str(conflict.get("resolution_rule") or "")
    if rule not in RESOLUTION_RULES:
        failures.append(f"resolution_rule_outside_the_vocabulary:{rule or 'missing'}")

    if len(conflict.get("fact_ids") or []) != 2:
        failures.append("conflict_does_not_name_exactly_two_facts")
    if len(conflict.get("values") or []) != 2:
        failures.append("conflict_does_not_retain_both_values")
    if not conflict.get("both_values_retained"):
        failures.append("conflict_discarded_a_value")

    # A winner without a rule that selects one is a silent resolution.
    if conflict.get("winning_fact_id") and rule not in SELECTS_A_WINNER:
        failures.append(f"conflict_picked_a_winner_under_rule_{rule}")
    if rule in SELECTS_A_WINNER and not conflict.get("winning_fact_id"):
        failures.append(f"rule_{rule}_selected_nobody")
    if rule == UNRESOLVED and not conflict.get("review_required"):
        failures.append("unresolved_conflict_does_not_ask_for_review")
    if rule == FAQ_CLARIFIES and conflict.get("winning_fact_id"):
        failures.append("clarification_overwrote_the_original")

    return sorted(set(failures))


def build_citation(fact: dict[str, Any], document: dict[str, Any]) -> dict[str, Any]:
    """175K: what a customer is shown when they ask "where did that come from"."""
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "fact_id": fact.get("fact_id"),
            "fact_kind": fact.get("fact_kind"),
            "value": fact.get("value"),
            "document_id": document.get("document_id"),
            "document_type": document.get("document_type"),
            "document_title": document.get("title"),
            "location_ref": document.get("location_ref"),
            "section_ref": fact.get("section_ref"),
            "page_ref": fact.get("page_ref"),
            "quoted_text": fact.get("source_text"),
            "content_sha256": document.get("content_sha256"),
            "extraction_method": fact.get("extraction_method"),
            "confidence": fact.get("confidence"),
            "document_state": document.get("document_state"),
            # Whether an ABSENCE in this document would have meant anything.
            "absence_would_be_meaningful": str(document.get("document_state"))
            in ABSENCE_IS_MEANINGFUL,
        }
    )


def citation_invariant_failures(citation: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    if not citation.get("document_id"):
        failures.append("citation_names_no_document")
    if not citation.get("content_sha256"):
        failures.append("citation_names_no_content_hash")
    if not citation.get("quoted_text"):
        failures.append("citation_quotes_nothing")
    if not citation.get("fact_id"):
        failures.append("citation_names_no_fact")
    return sorted(set(failures))


def describe_fact_model() -> dict[str, Any]:
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "fact_kinds": list(FACT_KINDS),
            "extraction_methods": list(EXTRACTION_METHODS),
            "confidence_levels": list(CONFIDENCE_LEVELS),
            "resolution_rules": list(RESOLUTION_RULES),
            "every_rule_has_a_meaning": set(RESOLUTION_MEANINGS)
            == set(RESOLUTION_RULES),
            "material_kinds": sorted(MATERIAL_KINDS),
            "fact_requires_a_document": True,
            "fact_requires_source_text": True,
            "a_clarification_never_overwrites": FAQ_CLARIFIES not in SELECTS_A_WINNER,
            "unresolved_conflicts_go_to_review": True,
            "both_values_are_always_retained": True,
            "appendix_and_faq_are_fact_bearing": sorted({APPENDIX, FAQ}),
            "rules_that_select_a_winner": sorted(SELECTS_A_WINNER),
        }
    )
