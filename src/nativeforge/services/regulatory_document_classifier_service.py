"""Not every government notice is a funding opportunity.

Measured on the Federal Register over 2026-07-01..2026-09-25: of 6,295
documents, 989 match "tribal". Of 100 of those sampled, 10 were NAGPRA
repatriation notices, 4 were funding-shaped, 1 was a meeting notice, and 85
were something else entirely.

Routing that stream into the opportunity graph would fill a Tribe's feed with
inventory-completion notices and Paperwork Reduction Act filings, and would do
it while looking like coverage. So a document is classified before it is
routed, and most classifications do not produce an opportunity.

    FUNDING_NOTICE        may become an opportunity or early signal
    CONSULTATION          real intelligence, never an opportunity
    POLICY_RULEMAKING     real intelligence, never an opportunity
    REPATRIATION_NOTICE   Native-relevant, never an opportunity
    ADMINISTRATIVE        meetings, information collection, corrections
    PROGRAM_NOTICE        a programme exists; no application is implied
    OTHER                 classified as unclassified, which is honest

## Native relevance is not the same question

A repatriation notice is deeply Native-relevant and is not funding. A highway
safety grant amendment is funding and may not be Native-relevant at all. This
module reports both signals separately and decides neither: Gate 173 owns
relevance, and nothing here may pre-empt it.

## Nothing here is the Federal Register

Any publisher of regulatory notices - a state register, an agency bulletin, a
tribal register - supplies its own field map and reuses this unchanged.
"""

from __future__ import annotations

import json
import re
from typing import Any

SCHEMA_VERSION = "nf_regulatory_document_classifier_v1"

# ---- classifications -------------------------------------------------
FUNDING_NOTICE = "FUNDING_NOTICE"
CONSULTATION = "CONSULTATION"
POLICY_RULEMAKING = "POLICY_RULEMAKING"
REPATRIATION_NOTICE = "REPATRIATION_NOTICE"
PROGRAM_NOTICE = "PROGRAM_NOTICE"
ADMINISTRATIVE = "ADMINISTRATIVE"
OTHER = "OTHER"

CLASSIFICATIONS: tuple[str, ...] = (
    FUNDING_NOTICE,
    CONSULTATION,
    POLICY_RULEMAKING,
    REPATRIATION_NOTICE,
    PROGRAM_NOTICE,
    ADMINISTRATIVE,
    OTHER,
)

# ---- routing ---------------------------------------------------------
ROUTE_OPPORTUNITY = "OPPORTUNITY_GRAPH"
ROUTE_EARLY_SIGNAL = "EARLY_SIGNAL"
ROUTE_INTELLIGENCE = "INTELLIGENCE_ONLY"
ROUTE_DISCARD = "NOT_ROUTED"

#: The only classification permitted to reach the opportunity graph. Every
#: other route is still useful; none of them is an opportunity.
OPPORTUNITY_ELIGIBLE: frozenset[str] = frozenset({FUNDING_NOTICE})

ROUTE_FOR_CLASSIFICATION: dict[str, str] = {
    FUNDING_NOTICE: ROUTE_OPPORTUNITY,
    CONSULTATION: ROUTE_INTELLIGENCE,
    POLICY_RULEMAKING: ROUTE_EARLY_SIGNAL,
    REPATRIATION_NOTICE: ROUTE_INTELLIGENCE,
    PROGRAM_NOTICE: ROUTE_EARLY_SIGNAL,
    ADMINISTRATIVE: ROUTE_DISCARD,
    OTHER: ROUTE_DISCARD,
}

# ---- evidence patterns ----------------------------------------------
#: Ordered. The first match wins, and the order encodes which signal is more
#: specific rather than which is more common.
_REPATRIATION_RE = re.compile(
    r"\b(repatriation|inventory\s+completion|nagpra|human\s+remains)\b", re.I
)
#: Deliberately narrow. "grant" alone matches "grant of authority" and
#: "granted", which is how an information-collection filing ends up looking
#: like money.
#: No trailing \b. These alternatives are deliberately PREFIXES - "opportunit"
#: must match "opportunity" and "opportunities", "application" must match
#: "applications" - and a closing boundary would refuse every one of them,
#: silently, by classifying a real funding notice as OTHER. Two regressions
#: caught exactly that.
_FUNDING_RE = re.compile(
    r"\b(notice\s+of\s+funding|funding\s+opportunit|funding\s+availab|"
    r"notice\s+of\s+availab\w*\s+of\s+funds|solicitation\s+for\s+(?:grant|"
    r"application|proposal)|request\s+for\s+application|"
    r"cooperative\s+agreement|financial\s+assistance|"
    r"supplemental\s+funding|grant\s+program|grant\s+funds)",
    re.I,
)
_CONSULTATION_RE = re.compile(
    r"\b(consultation|listening\s+session|tribal\s+consultation|"
    r"government[- ]to[- ]government)\b",
    re.I,
)
_ADMIN_RE = re.compile(
    r"\b(sunshine\s+act|information\s+collection|paperwork\s+reduction|"
    r"advisory\s+(?:committee|council)\s+meeting|notice\s+of\s+meeting|"
    r"correction|teleconference|renewal\s+of\s+charter)\b",
    re.I,
)
_PROGRAM_RE = re.compile(
    r"\b(program\s+(?:notice|announcement|description)|"
    r"annual\s+(?:report|notice)|list\s+of\s+programs)\b",
    re.I,
)

#: Document types a publisher may declare that are inherently rulemaking.
_RULEMAKING_TYPES: frozenset[str] = frozenset({"rule", "proposed rule", "prorule"})

#: Native evidence terms. Entity and programme language only - a place name is
#: not an entity, which is the guard Wave 1D established.
_NATIVE_TERMS: tuple[str, ...] = (
    "tribal",
    "tribe",
    "indian",
    "alaska native",
    "native hawaiian",
    "native american",
    "rancheria",
    "pueblo",
    "nagpra",
)


def _json_safe(value: Any) -> Any:
    return json.loads(json.dumps(value, default=str, sort_keys=True))


def classify_document(
    document: dict[str, Any], *, field_map: dict[str, str] | None = None
) -> dict[str, Any]:
    """What kind of document is this, and where should it go?

    Returns a classification, a route, and the Native evidence it carries -
    three separate answers, because a repatriation notice is Native-relevant
    and not funding, and a highway grant amendment is funding and may not be
    Native-relevant at all.
    """
    fmap = field_map or {}

    def get(key: str) -> str:
        return str(document.get(fmap.get(key, key)) or "").strip()

    title = get("title")
    abstract = get("abstract")
    doc_type = get("doc_type").lower()
    haystack = f"{title} {abstract}"

    reasons: list[str] = []
    classification = OTHER

    if _REPATRIATION_RE.search(haystack):
        classification = REPATRIATION_NOTICE
        reasons.append("repatriation_or_inventory_language")
    elif _ADMIN_RE.search(haystack):
        # Checked BEFORE funding: "Agency Information Collection Activities"
        # filings routinely mention grant programmes they collect data about,
        # and were the false positives in the measured sample.
        classification = ADMINISTRATIVE
        reasons.append("administrative_or_information_collection_language")
    elif _FUNDING_RE.search(haystack):
        classification = FUNDING_NOTICE
        reasons.append("funding_specific_language")
    elif _CONSULTATION_RE.search(haystack):
        classification = CONSULTATION
        reasons.append("consultation_language")
    elif doc_type in _RULEMAKING_TYPES:
        classification = POLICY_RULEMAKING
        reasons.append(f"publisher_document_type:{doc_type}")
    elif _PROGRAM_RE.search(haystack):
        classification = PROGRAM_NOTICE
        reasons.append("program_notice_language")
    else:
        reasons.append("no_classifying_signal_found")

    native_terms = sorted({t for t in _NATIVE_TERMS if t in haystack.lower()})
    route = ROUTE_FOR_CLASSIFICATION.get(classification, ROUTE_DISCARD)

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "classification": classification,
            "route": route,
            "may_become_opportunity": classification in OPPORTUNITY_ELIGIBLE,
            "publisher_document_type": doc_type or None,
            "native_evidence_terms": native_terms,
            "has_native_evidence": bool(native_terms),
            "reasons": sorted(set(reasons)),
            # Three separate questions, answered separately.
            "native_relevance_decided": False,
            "native_relevance_is_decided_by_gate_173": True,
            "eligibility_decided": False,
            "a_notice_is_not_an_opportunity": True,
        }
    )


def summarize_classifications(
    classifications: list[dict[str, Any]],
) -> dict[str, Any]:
    """Counts by class and route, so nobody reports a stream as a pipeline."""
    by_class: dict[str, int] = {c: 0 for c in CLASSIFICATIONS}
    by_route: dict[str, int] = {}
    native = 0
    for entry in classifications:
        cls = str(entry.get("classification") or OTHER)
        by_class[cls] = by_class.get(cls, 0) + 1
        route = str(entry.get("route") or ROUTE_DISCARD)
        by_route[route] = by_route.get(route, 0) + 1
        if entry.get("has_native_evidence"):
            native += 1
    opportunity_eligible = sum(by_class.get(c, 0) for c in OPPORTUNITY_ELIGIBLE)
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "document_count": len(classifications),
            "by_classification": dict(sorted(by_class.items())),
            "by_route": dict(sorted(by_route.items())),
            "documents_with_native_evidence": native,
            "opportunity_eligible_count": opportunity_eligible,
            # The number that stops a stream being reported as a pipeline.
            "documents_not_becoming_opportunities": (
                len(classifications) - opportunity_eligible
            ),
            "document_count_is_not_opportunity_count": True,
        }
    )
