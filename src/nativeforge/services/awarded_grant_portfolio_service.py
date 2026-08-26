"""Awarded grant portfolio (Gate 91C).

A customer's grants that are **already won** and must now be administered.

## These are obligations, not opportunities

An awarded grant carries reporting, financial, performance, compliance and
closeout duties with real deadlines. Calling the page "Awarded Grants" rather
than "opportunities" is not branding - it is the difference between something a
customer might do and something they owe.

## Customer-specific, always

An awarded grant belongs to one customer org. It is **not** a source registry
row (Gate 90, 55 shared candidate sources) and **not** a generic opportunity
(Baseline X, 185 shared records). Those are the same for everybody; this is not.

``customer_org_id`` is required and a portfolio record cannot be built without
it - not defaulted, not inferred from context.

## Evidence rules, inherited

Same as every gate since 85:

* no reporting requirement without evidence text
* no due date without source text or customer-provided award terms
* missing award details produce ``HUMAN_REVIEW_REQUIRED``, never a silent
  assumption

A portfolio record with no award end date does not get one computed from a
twelve-month default. It gets a human review item saying the date is missing.
"""

from __future__ import annotations

import json
from typing import Any

SCHEMA_VERSION = "nf_awarded_grant_portfolio_v1"

LIFECYCLE_STATUSES = frozenset(
    {
        "awarded_active",
        "awarded_closeout",
        "awarded_closed",
        "unknown",
    }
)

# Award details that must be present before obligations can be dated. Missing
# any of them is a review item, not a failure - a customer may legitimately not
# have the award package to hand when they mark the grant.
REQUIRED_AWARD_DETAIL_FIELDS: tuple[str, ...] = (
    "award_number",
    "award_start_date",
    "award_end_date",
    "award_amount",
)

# Detail fields that are useful but never block.
OPTIONAL_AWARD_DETAIL_FIELDS: tuple[str, ...] = (
    "award_date",
    "assistance_listing",
    "match_required",
)

REQUIREMENT_CATEGORIES: tuple[str, ...] = (
    "reporting_requirements",
    "financial_requirements",
    "performance_requirements",
    "compliance_requirements",
    "closeout_requirements",
)


class AwardedGrantError(ValueError):
    """Raised when a portfolio record cannot be built honestly."""


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _requirement_has_evidence(requirement: dict[str, Any]) -> bool:
    return bool(str(requirement.get("evidence_quote") or "").strip())


def build_awarded_grant_record(
    *,
    awarded_grant_id: str,
    customer_org_id: str,
    grant_title: str | None = None,
    agency: str | None = None,
    program: str | None = None,
    assistance_listing: str | None = None,
    award_number: str | None = None,
    award_start_date: str | None = None,
    award_end_date: str | None = None,
    award_amount: Any = None,
    match_required: Any = None,
    reporting_requirements: list[dict[str, Any]] | None = None,
    financial_requirements: list[dict[str, Any]] | None = None,
    performance_requirements: list[dict[str, Any]] | None = None,
    compliance_requirements: list[dict[str, Any]] | None = None,
    closeout_requirements: list[dict[str, Any]] | None = None,
    documents: list[dict[str, Any]] | None = None,
    lifecycle_status: str = "awarded_active",
    source_opportunity_id: str | None = None,
) -> dict[str, Any]:
    """Build one awarded-grant portfolio record.

    Raises :class:`AwardedGrantError` without a customer org - an awarded grant
    that belongs to nobody is not a portfolio record.
    """
    if not str(customer_org_id or "").strip():
        raise AwardedGrantError(
            "awarded grant requires customer_org_id; awarded grants are "
            "customer-specific and are not source registry rows"
        )
    if not str(awarded_grant_id or "").strip():
        raise AwardedGrantError("awarded grant requires awarded_grant_id")

    status = lifecycle_status if lifecycle_status in LIFECYCLE_STATUSES else "unknown"

    details = {
        "award_number": award_number,
        "award_start_date": award_start_date,
        "award_end_date": award_end_date,
        "award_amount": award_amount,
        "award_date": None,
        "assistance_listing": assistance_listing,
        "match_required": match_required,
    }
    missing = [
        f
        for f in REQUIRED_AWARD_DETAIL_FIELDS
        if details.get(f) in (None, "", [])
    ]

    human_review: list[str] = []
    for field in missing:
        human_review.append(f"missing_award_detail:{field}")
    if status == "unknown":
        human_review.append(f"unrecognised_lifecycle_status:{lifecycle_status}")

    categories = {
        "reporting_requirements": list(reporting_requirements or []),
        "financial_requirements": list(financial_requirements or []),
        "performance_requirements": list(performance_requirements or []),
        "compliance_requirements": list(compliance_requirements or []),
        "closeout_requirements": list(closeout_requirements or []),
    }

    # Every requirement must carry evidence. One without is not dropped - it is
    # kept and flagged, because a requirement somebody believed in is worth a
    # human look even when its source is missing.
    unevidenced = 0
    for category, items in categories.items():
        for item in items:
            if not _requirement_has_evidence(item):
                unevidenced += 1
                item["human_review_required"] = True
                item.setdefault("blocked_reasons", []).append(
                    "requirement_without_evidence_quote"
                )
                label = (
                    item.get("report_name")
                    or item.get("requirement_name")
                    or "unnamed"
                )
                human_review.append(
                    f"unevidenced_requirement:{category}:{label}"
                )

    # A due date needs a source. Dated obligations with neither source text nor
    # customer-supplied award terms are the exact fabrication this forbids.
    dateless_obligations = 0
    for items in categories.values():
        for item in items:
            if item.get("due_date") and not (
                item.get("evidence_quote") or item.get("customer_provided")
            ):
                dateless_obligations += 1
                item["human_review_required"] = True
                item.setdefault("blocked_reasons", []).append(
                    "due_date_without_source_or_customer_terms"
                )

    reporting_calendar = build_reporting_calendar(
        reporting_requirements=categories["reporting_requirements"],
        award_start_date=award_start_date,
        award_end_date=award_end_date,
    )

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "awarded_grant_id": awarded_grant_id,
            "customer_org_id": customer_org_id,
            "source_opportunity_id": source_opportunity_id,
            "grant_title": grant_title,
            "agency": agency,
            "program": program,
            "assistance_listing": assistance_listing,
            "award_number": award_number,
            "award_start_date": award_start_date,
            "award_end_date": award_end_date,
            "award_amount": award_amount,
            "match_required": match_required,
            **categories,
            "reporting_calendar": reporting_calendar,
            "documents": list(documents or []),
            "human_review_items": human_review,
            "risk_summary": build_risk_summary(
                missing_details=missing,
                unevidenced_requirements=unevidenced,
                dateless_obligations=dateless_obligations,
                categories=categories,
            ),
            "lifecycle_status": status,
            # This record is an obligation, and is customer-specific. Both
            # stated so a consumer cannot treat it as a shared opportunity.
            "is_active_obligation": status in {"awarded_active", "awarded_closeout"},
            "is_customer_specific": True,
            "is_source_registry_row": False,
            "is_generic_opportunity": False,
            "requires_human_review": bool(human_review),
            "fabricated": False,
        }
    )


def build_reporting_calendar(
    *,
    reporting_requirements: list[dict[str, Any]] | None = None,
    award_start_date: str | None = None,
    award_end_date: str | None = None,
) -> dict[str, Any]:
    """Dated obligations, and the ones that cannot be dated.

    A requirement with no source-supported date does **not** get a computed one.
    It lands in ``undated`` with a reason, where a person can see it.
    """
    dated: list[dict[str, Any]] = []
    undated: list[dict[str, Any]] = []

    for requirement in reporting_requirements or []:
        due = requirement.get("due_date") or requirement.get("first_due_date")
        supported = bool(
            requirement.get("evidence_quote") or requirement.get("customer_provided")
        )
        if due and supported:
            dated.append(
                {
                    "report_name": requirement.get("report_name"),
                    "due_date": due,
                    "frequency": requirement.get("report_frequency"),
                    "evidence_quote": requirement.get("evidence_quote"),
                }
            )
        else:
            undated.append(
                {
                    "report_name": requirement.get("report_name"),
                    "reason": (
                        "no_due_date_in_source"
                        if not due
                        else "due_date_without_source_support"
                    ),
                }
            )

    return _json_safe(
        {
            "award_start_date": award_start_date,
            "award_end_date": award_end_date,
            "dated_obligations": dated,
            "undated_obligations": undated,
            "dated_count": len(dated),
            "undated_count": len(undated),
            # No date was computed, inferred or defaulted.
            "dates_inferred": 0,
            "calendar_complete": bool(dated) and not undated,
        }
    )


def build_risk_summary(
    *,
    missing_details: list[str],
    unevidenced_requirements: int,
    dateless_obligations: int,
    categories: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    total_requirements = sum(len(v) for v in categories.values())
    return _json_safe(
        {
            "missing_award_details": list(missing_details),
            "missing_award_detail_count": len(missing_details),
            "unevidenced_requirement_count": unevidenced_requirements,
            "dateless_obligation_count": dateless_obligations,
            "total_requirements": total_requirements,
            "requirements_by_category": {
                k: len(v) for k, v in sorted(categories.items())
            },
            # An award whose details are missing cannot be administered from
            # this record alone, and says so rather than looking complete.
            "administrable_from_this_record": (
                not missing_details and unevidenced_requirements == 0
            ),
        }
    )


def build_portfolio(*, awarded_grants: list[dict[str, Any]]) -> dict[str, Any]:
    """One customer's awarded-grant portfolio."""
    orgs = {g.get("customer_org_id") for g in awarded_grants}
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "awarded_grant_count": len(awarded_grants),
            "awarded_grants": awarded_grants,
            "customer_org_ids": sorted(o for o in orgs if o),
            "active_obligation_count": sum(
                1 for g in awarded_grants if g.get("is_active_obligation")
            ),
            "requires_human_review_count": sum(
                1 for g in awarded_grants if g.get("requires_human_review")
            ),
            "lifecycle_tracking_live": False,
            "fabricated": False,
        }
    )


def awarded_grant_invariant_failures(record: dict[str, Any]) -> list[str]:
    fails: list[str] = []

    if record.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")
    if record.get("fabricated") is not False:
        fails.append("fabricated_must_be_false")

    single = "awarded_grant_id" in record
    entries = [record] if single else (record.get("awarded_grants") or [])

    if not single and record.get("lifecycle_tracking_live") is not False:
        fails.append("lifecycle_tracking_claimed_live")

    for entry in entries:
        gid = entry.get("awarded_grant_id")
        if not entry.get("customer_org_id"):
            fails.append(f"awarded_grant_without_customer_org:{gid}")
        if entry.get("is_customer_specific") is not True:
            fails.append(f"awarded_grant_not_marked_customer_specific:{gid}")
        if entry.get("is_source_registry_row") is not False:
            fails.append(f"awarded_grant_confused_with_registry_row:{gid}")
        if entry.get("is_generic_opportunity") is not False:
            fails.append(f"awarded_grant_confused_with_opportunity:{gid}")
        if entry.get("lifecycle_status") not in LIFECYCLE_STATUSES:
            fails.append(f"lifecycle_status_out_of_vocabulary:{gid}")

        calendar = entry.get("reporting_calendar") or {}
        if calendar.get("dates_inferred"):
            fails.append(f"reporting_calendar_inferred_a_date:{gid}")

        # Every requirement lacking evidence must be flagged, never silently
        # accepted.
        for category in REQUIREMENT_CATEGORIES:
            for item in entry.get(category) or []:
                if not _requirement_has_evidence(item) and not item.get(
                    "human_review_required"
                ):
                    fails.append(f"unevidenced_requirement_not_flagged:{gid}:{category}")

        if entry.get("human_review_items") and not entry.get("requires_human_review"):
            fails.append(f"review_items_without_review_flag:{gid}")

    return fails
