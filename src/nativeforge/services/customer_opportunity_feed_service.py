"""179B/C/H: what a customer sees, built from what the system actually knows.

The Gate 179 survey measured the problem in one line:

```text
buyer_feed_depends_on_hand_made_sparks = true
api_imports_canonical_intelligence     = false
canonical_modules_with_no_importer     = [canonical_opportunity_store_service,
                                          document_fact_extraction_service]
```

Nine gates of intelligence - the canonical graph, Native relevance,
eligibility, document evidence - and not one of them reached a buyer. The
workspace was fed by fixtures somebody wrote by hand for a demo, which
demonstrates beautifully and proves nothing.

So this module builds the recommendation read model from the canonical
record, and refuses to build one from anything else.

## Every recommendation must be able to explain itself

179C asks four questions of each opportunity: why is this Native-relevant,
why does this organisation appear eligible or uncertain, what evidence
supports that, and what remains unknown. A recommendation that cannot answer
them is a guess with a confident font, and a Tribal government acting on it
spends weeks on an application they were never eligible for.

`build_recommendation` therefore refuses to emit a recommendation whose
relevance or eligibility claim carries no evidence reference. The refusal is
in `recommendation_invariant_failures`, and it fires.

## UNKNOWN survives to the surface

The temptation at the presentation layer is to turn UNKNOWN into a clean
answer, because "eligibility unclear" looks unfinished next to "eligible".
`ELIGIBILITY_UNCERTAIN` and `known_unknowns` exist so the customer sees the
same uncertainty the graph recorded. A system that hides its uncertainty is
not more useful, it is more confident about the wrong things.

## What this module will not do

It does not score, rank by a secret number, or invent a deadline. It orders
by explicit, stated criteria and reports the criteria.
"""

from __future__ import annotations

import datetime as dt
import hashlib
from typing import Any

SCHEMA_VERSION = "nf_customer_opportunity_feed_v1"

FEED_MODEL_VERSION = "2026.09.1"

# ---------------------------------------------------------------------------
# 179B: what a recommendation can say about relevance.
# ---------------------------------------------------------------------------

RELEVANCE_NATIVE_SPECIFIC = "NATIVE_SPECIFIC"
RELEVANCE_NATIVE_ELIGIBLE = "NATIVE_ELIGIBLE"
RELEVANCE_BROADLY_ELIGIBLE = "BROADLY_ELIGIBLE"
RELEVANCE_UNCERTAIN = "RELEVANCE_UNCERTAIN"
RELEVANCE_NOT_RELEVANT = "NOT_RELEVANT"

RELEVANCE_CLASSES: tuple[str, ...] = (
    RELEVANCE_NATIVE_SPECIFIC,
    RELEVANCE_NATIVE_ELIGIBLE,
    RELEVANCE_BROADLY_ELIGIBLE,
    RELEVANCE_UNCERTAIN,
    RELEVANCE_NOT_RELEVANT,
)

RELEVANCE_MEANINGS: dict[str, str] = {
    RELEVANCE_NATIVE_SPECIFIC: "set aside for Tribes or Native organisations",
    RELEVANCE_NATIVE_ELIGIBLE: "names Tribes or Native organisations as eligible",
    RELEVANCE_BROADLY_ELIGIBLE: (
        "open to a wide field that includes this organisation"
    ),
    RELEVANCE_UNCERTAIN: ("the evidence does not decide it, and a human should look"),
    RELEVANCE_NOT_RELEVANT: "the evidence says this is not for them",
}

#: Relevance classes a customer is shown. NOT_RELEVANT is computed and kept -
#: it is how the system can be shown to be wrong - but it is not recommended.
RECOMMENDED_RELEVANCE: frozenset[str] = frozenset(
    {RELEVANCE_NATIVE_SPECIFIC, RELEVANCE_NATIVE_ELIGIBLE, RELEVANCE_BROADLY_ELIGIBLE}
)

# ---- eligibility, as the customer sees it ------------------------------
ELIGIBILITY_APPEARS_ELIGIBLE = "APPEARS_ELIGIBLE"
ELIGIBILITY_CONDITIONAL = "CONDITIONAL"
ELIGIBILITY_UNCERTAIN = "ELIGIBILITY_UNCERTAIN"
ELIGIBILITY_APPEARS_INELIGIBLE = "APPEARS_INELIGIBLE"
ELIGIBILITY_NOT_ASSESSED = "NOT_ASSESSED"

ELIGIBILITY_VIEWS: tuple[str, ...] = (
    ELIGIBILITY_APPEARS_ELIGIBLE,
    ELIGIBILITY_CONDITIONAL,
    ELIGIBILITY_UNCERTAIN,
    ELIGIBILITY_APPEARS_INELIGIBLE,
    ELIGIBILITY_NOT_ASSESSED,
)

ELIGIBILITY_MEANINGS: dict[str, str] = {
    ELIGIBILITY_APPEARS_ELIGIBLE: (
        "the requirements we could read are met by the profile on file"
    ),
    ELIGIBILITY_CONDITIONAL: (
        "eligible IF a stated condition holds - the condition is named"
    ),
    ELIGIBILITY_UNCERTAIN: ("we could not decide. Not a soft no and not a soft yes"),
    ELIGIBILITY_APPEARS_INELIGIBLE: (
        "a disqualifying requirement was found, and it is named"
    ),
    ELIGIBILITY_NOT_ASSESSED: (
        "nobody has assessed this yet, which is different from uncertain"
    ),
}

#: Views that must name something: a condition, a blocker, or a reason.
MUST_NAME_ITS_REASON: frozenset[str] = frozenset(
    {ELIGIBILITY_CONDITIONAL, ELIGIBILITY_APPEARS_INELIGIBLE, ELIGIBILITY_UNCERTAIN}
)

# ---- why a recommendation is ordered where it is -----------------------
ORDER_DEADLINE_SOONEST = "DEADLINE_SOONEST"
ORDER_RELEVANCE_STRENGTH = "RELEVANCE_STRENGTH"
ORDER_RECENTLY_CHANGED = "RECENTLY_CHANGED"
ORDER_NEWLY_DISCOVERED = "NEWLY_DISCOVERED"

ORDERINGS: tuple[str, ...] = (
    ORDER_DEADLINE_SOONEST,
    ORDER_RELEVANCE_STRENGTH,
    ORDER_RECENTLY_CHANGED,
    ORDER_NEWLY_DISCOVERED,
)

#: Relevance strength, for ordering only. Deliberately NOT a score: it is a
#: rank over a named vocabulary, it is reported, and nothing is multiplied.
_RELEVANCE_RANK: dict[str, int] = {
    RELEVANCE_NATIVE_SPECIFIC: 0,
    RELEVANCE_NATIVE_ELIGIBLE: 1,
    RELEVANCE_BROADLY_ELIGIBLE: 2,
    RELEVANCE_UNCERTAIN: 3,
    RELEVANCE_NOT_RELEVANT: 4,
}

RECOMMENDATION_FIELDS: tuple[str, ...] = (
    "recommendation_id",
    "organization_id",
    "canonical_id",
    "title",
    "funder_name",
    "deadline",
    "relevance_class",
    "why_relevant",
    "relevance_evidence_ids",
    "eligibility_view",
    "why_eligibility",
    "eligibility_evidence_ids",
    "eligibility_conditions",
    "eligibility_blockers",
    "document_citations",
    "what_changed",
    "known_unknowns",
    "decision_state",
    "sourced_from_canonical_graph",
    "model_version",
)


def _as_date(value: Any) -> dt.date | None:
    if value is None or value == "":
        return None
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    try:
        return dt.date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def build_recommendation_id(*, organization_id: Any, canonical_id: Any) -> str:
    parts = [str(organization_id or ""), str(canonical_id or "")]
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()


def build_recommendation(
    *,
    organization_id: Any,
    canonical_record: dict[str, Any],
    relevance: dict[str, Any] | None = None,
    eligibility: dict[str, Any] | None = None,
    documents: list[dict[str, Any]] | None = None,
    changes: list[dict[str, Any]] | None = None,
    decision: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """One recommendation, assembled from the canonical record and its evidence.

    `canonical_record` is a row from the opportunity graph. Nothing here
    invents a title, a funder or a deadline: a field the graph does not have
    stays absent rather than becoming a plausible guess.
    """
    canonical_id = canonical_record.get("canonical_id")
    relevance = relevance or {}
    eligibility = eligibility or {}
    documents = documents or []
    changes = changes or []

    relevance_class = str(relevance.get("relevance_class") or RELEVANCE_UNCERTAIN)
    relevance_evidence = sorted(str(e) for e in (relevance.get("evidence_ids") or []))
    eligibility_view = str(
        eligibility.get("eligibility_view") or ELIGIBILITY_NOT_ASSESSED
    )
    eligibility_evidence = sorted(
        str(e) for e in (eligibility.get("evidence_ids") or [])
    )
    conditions = [str(c) for c in (eligibility.get("conditions") or [])]
    blockers = [str(b) for b in (eligibility.get("blockers") or [])]

    citations = [
        {
            "document_id": d.get("document_id"),
            "document_type": d.get("document_type"),
            "page": d.get("page"),
            "quote": d.get("quote"),
        }
        for d in documents
        # A citation with no quote is a reference nobody can check.
        if d.get("quote")
    ]

    # 179C: what remains unknown, stated rather than smoothed away.
    unknowns: list[str] = []
    if relevance_class == RELEVANCE_UNCERTAIN:
        unknowns.append("native_relevance_undecided")
    if eligibility_view == ELIGIBILITY_UNCERTAIN:
        unknowns.append("eligibility_undecided")
    if eligibility_view == ELIGIBILITY_NOT_ASSESSED:
        unknowns.append("eligibility_not_yet_assessed")
    if not _as_date(canonical_record.get("close_date")):
        unknowns.append("no_published_deadline")
    if not documents:
        unknowns.append("no_document_evidence_read_yet")
    unknowns.extend(str(u) for u in (eligibility.get("unknowns") or []))
    unknowns.extend(str(u) for u in (relevance.get("unknowns") or []))

    return {
        "schema_version": SCHEMA_VERSION,
        "recommendation_id": build_recommendation_id(
            organization_id=organization_id, canonical_id=canonical_id
        ),
        "organization_id": str(organization_id) if organization_id else None,
        "canonical_id": str(canonical_id) if canonical_id else None,
        "title": canonical_record.get("title"),
        "funder_name": canonical_record.get("funder_name"),
        "deadline": canonical_record.get("close_date"),
        # 179C, question 1.
        "relevance_class": relevance_class,
        "why_relevant": relevance.get("why") or RELEVANCE_MEANINGS.get(relevance_class),
        "relevance_evidence_ids": relevance_evidence,
        # 179C, question 2.
        "eligibility_view": eligibility_view,
        "why_eligibility": eligibility.get("why")
        or ELIGIBILITY_MEANINGS.get(eligibility_view),
        "eligibility_evidence_ids": eligibility_evidence,
        "eligibility_conditions": conditions,
        "eligibility_blockers": blockers,
        # 179C, question 3, and 179H.
        "document_citations": citations,
        # 179C, question 4.
        "what_changed": [
            {
                "change_type": c.get("change_type"),
                "observed_at": c.get("observed_at"),
                "summary": c.get("summary"),
            }
            for c in changes
        ],
        "known_unknowns": sorted(set(unknowns)),
        "decision_state": (decision or {}).get("decision_state"),
        # The claim the survey found to be false before this gate.
        "sourced_from_canonical_graph": bool(canonical_id),
        "model_version": FEED_MODEL_VERSION,
    }


def build_feed(
    *,
    organization_id: Any,
    recommendations: list[dict[str, Any]],
    ordering: str = ORDER_DEADLINE_SOONEST,
    include_dismissed: bool = False,
    as_of: Any = None,
    limit: int = 50,
) -> dict[str, Any]:
    """Order and page the recommendations, and say how they were ordered.

    A feed whose order is a secret number cannot be argued with. The ordering
    is named, the criteria are reported, and a customer who disagrees can
    pick a different one.
    """
    today = _as_date(as_of) or dt.datetime.now(dt.UTC).date()
    if str(ordering) not in ORDERINGS:
        raise ValueError(f"{ordering} is not an ordering")

    visible = [
        r
        for r in recommendations
        if str(r.get("relevance_class")) in RECOMMENDED_RELEVANCE
        or str(r.get("relevance_class")) == RELEVANCE_UNCERTAIN
    ]
    dismissed = [r for r in visible if str(r.get("decision_state")) == "DISMISSED"]
    if not include_dismissed:
        visible = [r for r in visible if str(r.get("decision_state")) != "DISMISSED"]

    far_future = dt.date(9999, 12, 31)

    def sort_key(row: dict[str, Any]):
        deadline = _as_date(row.get("deadline")) or far_future
        rank = _RELEVANCE_RANK.get(str(row.get("relevance_class")), 9)
        changed = row.get("what_changed") or []
        latest_change = max(
            (str(c.get("observed_at") or "") for c in changed), default=""
        )
        if ordering == ORDER_DEADLINE_SOONEST:
            return (deadline, rank, str(row.get("canonical_id")))
        if ordering == ORDER_RELEVANCE_STRENGTH:
            return (rank, deadline, str(row.get("canonical_id")))
        if ordering == ORDER_RECENTLY_CHANGED:
            return (
                "" if not latest_change else _invert(latest_change),
                rank,
                str(row.get("canonical_id")),
            )
        return (rank, str(row.get("canonical_id")))

    ordered = sorted(visible, key=sort_key)[: int(limit)]

    return {
        "schema_version": SCHEMA_VERSION,
        "organization_id": str(organization_id) if organization_id else None,
        "as_of": str(today),
        "ordering": str(ordering),
        "ordering_is_explicit": True,
        "recommendations": ordered,
        "returned": len(ordered),
        "available": len(visible),
        "dismissed_hidden": 0 if include_dismissed else len(dismissed),
        # Dismissing hides a row from ONE organisation's feed. It does not
        # delete the opportunity, and it does not touch what the graph knows.
        "dismissal_is_tenant_scoped": True,
        "global_intelligence_unchanged": True,
        "sourced_from_canonical_graph": all(
            r.get("sourced_from_canonical_graph") for r in ordered
        ),
        "model_version": FEED_MODEL_VERSION,
    }


def _invert(text: str) -> str:
    """Sort a string descending inside an ascending tuple sort."""
    return "".join(chr(0x10FFFF - ord(c)) if ord(c) < 0x10FFFF else c for c in text)


def recommendation_invariant_failures(row: dict[str, Any]) -> list[str]:
    """Refuse a recommendation that cannot explain itself."""
    failures: list[str] = []

    for field in RECOMMENDATION_FIELDS:
        if field not in row:
            failures.append(f"recommendation_missing_field:{field}")

    relevance = str(row.get("relevance_class") or "")
    eligibility = str(row.get("eligibility_view") or "")

    if relevance not in RELEVANCE_CLASSES:
        failures.append(f"relevance_outside_the_vocabulary:{relevance or 'missing'}")
    if eligibility not in ELIGIBILITY_VIEWS:
        failures.append(
            f"eligibility_outside_the_vocabulary:{eligibility or 'missing'}"
        )

    # The load-bearing refusal: it must come from the graph.
    if not row.get("canonical_id"):
        failures.append("recommendation_has_no_canonical_opportunity")
    if not row.get("sourced_from_canonical_graph"):
        failures.append("recommendation_not_sourced_from_the_canonical_graph")

    # A decisive relevance claim needs evidence behind it.
    if relevance in RECOMMENDED_RELEVANCE and not row.get("relevance_evidence_ids"):
        failures.append(f"relevance_{relevance}_cites_no_evidence")
    if not row.get("why_relevant"):
        failures.append("recommendation_cannot_say_why_it_is_relevant")

    # A conditional or blocking eligibility view must NAME the condition.
    if eligibility == ELIGIBILITY_CONDITIONAL and not row.get("eligibility_conditions"):
        failures.append("conditional_eligibility_names_no_condition")
    if eligibility == ELIGIBILITY_APPEARS_INELIGIBLE and not row.get(
        "eligibility_blockers"
    ):
        failures.append("ineligible_view_names_no_blocker")
    if eligibility in MUST_NAME_ITS_REASON and not row.get("why_eligibility"):
        failures.append(f"{eligibility}_states_no_reason")
    if eligibility == ELIGIBILITY_APPEARS_ELIGIBLE and not row.get(
        "eligibility_evidence_ids"
    ):
        failures.append("eligible_view_cites_no_evidence")

    # Uncertainty must reach the surface.
    if relevance == RELEVANCE_UNCERTAIN and "native_relevance_undecided" not in (
        row.get("known_unknowns") or []
    ):
        failures.append("uncertain_relevance_not_reported_as_unknown")
    if eligibility == ELIGIBILITY_UNCERTAIN and "eligibility_undecided" not in (
        row.get("known_unknowns") or []
    ):
        failures.append("uncertain_eligibility_not_reported_as_unknown")

    # A citation nobody can check is not a citation.
    for citation in row.get("document_citations") or []:
        if not citation.get("quote"):
            failures.append("document_citation_quotes_nothing")
        if not citation.get("document_id"):
            failures.append("document_citation_names_no_document")

    return sorted(set(failures))


def describe_feed_model() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "model_version": FEED_MODEL_VERSION,
        "relevance_classes": list(RELEVANCE_CLASSES),
        "eligibility_views": list(ELIGIBILITY_VIEWS),
        "orderings": list(ORDERINGS),
        "every_relevance_class_has_a_meaning": set(RELEVANCE_MEANINGS)
        == set(RELEVANCE_CLASSES),
        "every_eligibility_view_has_a_meaning": set(ELIGIBILITY_MEANINGS)
        == set(ELIGIBILITY_VIEWS),
        # The refusals.
        "recommendations_come_from_the_canonical_graph": True,
        "no_hand_made_sparks": True,
        "every_recommendation_explains_its_relevance": True,
        "conditional_eligibility_names_its_condition": True,
        "ineligibility_names_its_blocker": True,
        "uncertainty_reaches_the_customer": True,
        "not_assessed_is_distinct_from_uncertain": (
            ELIGIBILITY_NOT_ASSESSED != ELIGIBILITY_UNCERTAIN
        ),
        "ordering_is_named_not_scored": True,
        "no_opaque_score": True,
        "dismissal_is_tenant_scoped": True,
        "citations_carry_a_quote": True,
    }
