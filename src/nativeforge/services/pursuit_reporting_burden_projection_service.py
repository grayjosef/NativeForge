"""Pursuit reporting-burden projection (Gate 91D).

Shows a customer what a grant would cost them to administer **if they won it**,
while the decision is still theirs to make.

## Projected is not active

This is the distinction the whole lane separation exists to protect:

=====================  ==========================  ==========================
                       Projected burden            Active obligation
=====================  ==========================  ==========================
when                   before award                after award
source                 NOFO text                   award document and terms
status                 an estimate                 a duty with dates
if wrong               a bad pursuit decision      a missed federal deadline
=====================  ==========================  ==========================

Every field here is prefixed ``projected_`` and every result carries
``is_active_obligation: False``. A projection must never be rendered as a
reporting calendar, because a customer reading an estimated quarterly-report
date as a real one will plan around it.

## Burden is not eligibility

A high burden means a grant is expensive to administer. It does not mean the
customer cannot apply, and ``burden_fit`` must never be wired into the exclusion
model. ``affects_eligibility`` is a constant ``False``.

Unclear burden does not mean no-go either. It means a person should look before
the pursuit decision - which is what ``human_review_required`` is for.

## A note on the commercial incentive

This lane surfaces places where NativeForge is the answer:
``system_need`` feeds sales and support recommendations. A projection that
overstates burden sells more software.

The evidence rules are what keep that honest. Every projected requirement needs
a quote, and a burden status derived from no requirements at all is ``unclear``,
never ``manageable`` and never ``requires_new_systems``.
"""

from __future__ import annotations

import json
from typing import Any

SCHEMA_VERSION = "nf_pursuit_reporting_burden_projection_v1"

BURDEN_STATUSES = frozenset(
    {
        "manageable",
        "manageable_with_support",
        "high_burden",
        "requires_dedicated_staff",
        "requires_new_systems",
        "unclear",
        "human_review_required",
    }
)

# Statuses that describe a measured burden. Anything outside this set means the
# evidence did not support a conclusion.
DETERMINATE_BURDEN_STATUSES = frozenset(
    {
        "manageable",
        "manageable_with_support",
        "high_burden",
        "requires_dedicated_staff",
        "requires_new_systems",
    }
)

SYSTEM_NEEDS = frozenset(
    {"none_identified", "possible", "likely", "required", "unclear"}
)

STAFFING_NEEDS = frozenset(
    {"existing_staff_likely_sufficient", "additional_effort_likely",
     "dedicated_staff_likely", "unclear"}
)

PROJECTED_CATEGORIES: tuple[str, ...] = (
    "projected_reporting_requirements",
    "projected_financial_requirements",
    "projected_performance_requirements",
    "projected_compliance_requirements",
    "projected_closeout_requirements",
)

# Requirement counts at which burden escalates. Thresholds are declared rather
# than buried so they can be argued with.
HIGH_BURDEN_REQUIREMENT_COUNT = 8
DEDICATED_STAFF_REQUIREMENT_COUNT = 14


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _evidenced(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [i for i in items if str(i.get("evidence_quote") or "").strip()]


def project_pursuit_reporting_burden(
    *,
    opportunity_id: str,
    reporting_requirements: list[dict[str, Any]] | None = None,
    financial_requirements: list[dict[str, Any]] | None = None,
    performance_requirements: list[dict[str, Any]] | None = None,
    compliance_requirements: list[dict[str, Any]] | None = None,
    closeout_requirements: list[dict[str, Any]] | None = None,
    extraction_complete: bool = False,
) -> dict[str, Any]:
    """Project post-award burden for a pursuit-stage opportunity.

    ``extraction_complete`` says whether the source document was fully read. A
    partial read cannot support a burden conclusion, however few requirements it
    happened to find - absence of evidence is not evidence of low burden.
    """
    categories = {
        "projected_reporting_requirements": list(reporting_requirements or []),
        "projected_financial_requirements": list(financial_requirements or []),
        "projected_performance_requirements": list(performance_requirements or []),
        "projected_compliance_requirements": list(compliance_requirements or []),
        "projected_closeout_requirements": list(closeout_requirements or []),
    }

    blocked: list[str] = []
    evidence_quotes: list[dict[str, Any]] = []
    unevidenced = 0

    for name, items in categories.items():
        for item in items:
            quote = str(item.get("evidence_quote") or "").strip()
            if quote:
                evidence_quotes.append(
                    {
                        "category": name,
                        "requirement": item.get("report_name")
                        or item.get("requirement_name"),
                        "evidence_quote": quote,
                        "evidence_location": item.get("evidence_location"),
                        "source_document_id": item.get("source_document_id"),
                    }
                )
            else:
                unevidenced += 1

    evidenced_total = len(evidence_quotes)

    if unevidenced:
        blocked.append(f"unevidenced_projected_requirements:{unevidenced}")

    # --- burden status ---------------------------------------------------
    # Deny by default: a conclusion requires a complete read AND evidence.
    if not extraction_complete:
        burden_fit = "unclear"
        blocked.append("source_extraction_incomplete")
    elif evidenced_total == 0:
        # Nothing found in a document that was fully read is still not proof of
        # low burden - the document may simply not state its reporting terms.
        burden_fit = "unclear"
        blocked.append("no_evidenced_requirements_found")
    elif evidenced_total >= DEDICATED_STAFF_REQUIREMENT_COUNT:
        burden_fit = "requires_dedicated_staff"
    elif evidenced_total >= HIGH_BURDEN_REQUIREMENT_COUNT:
        burden_fit = "high_burden"
    else:
        burden_fit = "manageable_with_support"

    # --- system and staffing need ----------------------------------------
    data_signals = sum(
        1
        for item in categories["projected_performance_requirements"]
        if item.get("data_collection_required")
        or item.get("participant_tracking_required")
    )
    if not extraction_complete or evidenced_total == 0:
        system_need = "unclear"
        staffing_need = "unclear"
    elif data_signals >= 2 or burden_fit == "requires_dedicated_staff":
        system_need = "likely"
        staffing_need = "dedicated_staff_likely"
    elif data_signals or burden_fit == "high_burden":
        system_need = "possible"
        staffing_need = "additional_effort_likely"
    else:
        system_need = "none_identified"
        staffing_need = "existing_staff_likely_sufficient"

    human_review = (
        burden_fit not in DETERMINATE_BURDEN_STATUSES
        or bool(unevidenced)
        or not extraction_complete
    )

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "opportunity_id": opportunity_id,
            **categories,
            "burden_fit": burden_fit,
            "system_need": system_need,
            "staffing_need": staffing_need,
            "evidence_quotes": evidence_quotes,
            "evidenced_requirement_count": evidenced_total,
            "unevidenced_requirement_count": unevidenced,
            "extraction_complete": bool(extraction_complete),
            "human_review_required": human_review,
            "blocked_reasons": blocked,
            # The separations, asserted rather than described.
            "is_projection": True,
            "is_active_obligation": False,
            "affects_eligibility": False,
            "is_legal_advice": False,
            "requires_award_before_obligations_begin": True,
            "fabricated": False,
        }
    )


def projection_invariant_failures(result: dict[str, Any]) -> list[str]:
    fails: list[str] = []

    if result.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")
    if result.get("fabricated") is not False:
        fails.append("fabricated_must_be_false")

    # The four constants that keep a projection a projection.
    if result.get("is_projection") is not True:
        fails.append("projection_not_labelled_as_projection")
    if result.get("is_active_obligation") is not False:
        fails.append("projection_claimed_as_active_obligation")
    if result.get("affects_eligibility") is not False:
        fails.append("burden_wired_into_eligibility")
    if result.get("requires_award_before_obligations_begin") is not True:
        fails.append("obligations_claimed_before_award")

    if result.get("burden_fit") not in BURDEN_STATUSES:
        fails.append(f"burden_fit_out_of_vocabulary:{result.get('burden_fit')}")
    if result.get("system_need") not in SYSTEM_NEEDS:
        fails.append("system_need_out_of_vocabulary")
    if result.get("staffing_need") not in STAFFING_NEEDS:
        fails.append("staffing_need_out_of_vocabulary")

    # A determinate burden requires a complete read and evidence behind it.
    if result.get("burden_fit") in DETERMINATE_BURDEN_STATUSES:
        if not result.get("extraction_complete"):
            fails.append("determinate_burden_from_incomplete_extraction")
        if not result.get("evidenced_requirement_count"):
            fails.append("determinate_burden_without_evidence")

    if result.get("burden_fit") not in DETERMINATE_BURDEN_STATUSES and not result.get(
        "human_review_required"
    ):
        fails.append("indeterminate_burden_without_human_review")

    # Every field carrying requirements must be prefixed `projected_`, so a
    # consumer cannot mistake one for an awarded-grant category.
    for key in result:
        if key.endswith("_requirements") and not key.startswith("projected_"):
            fails.append(f"requirement_field_not_marked_projected:{key}")

    return fails
