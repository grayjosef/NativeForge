"""Federal source lane (Gate 77B).

The federal lane is the most uniform of the three and therefore the right one to
build first: a small number of canonical entry points, consistent applicant-type
vocabulary, and an authoritative amendment channel in the Federal Register.

The rule this module exists to hold, and the one Gate 77's corpus triage proved
is load-bearing: **a parent department is not a program.** IHS and SAMHSA both
sit under HHS and are not interchangeable. A live Grants.gov search for a SAMHSA
seed currently returns an IHS opportunity, and treating "both are HHS" as
alignment would have silently attributed one agency's grant to another's source.
See doc 423.

So `agency` here is the department (HHS), `subagency` is the operating division
(SAMHSA, IHS), and ownership comparisons use the most specific level available.
A source that needs a subagency and does not name one is incomplete, not
approximately complete.

Nothing here fetches. `monitoring_allowed` and `coverage_claimed` are False on
every record this gate produces.
"""

from __future__ import annotations

import json
import re
from typing import Any

from nativeforge.services.source_registry_service import (
    ROBOTS_TERMS_CLEARED,
    ROBOTS_TERMS_STATUSES,
)

SCHEMA_VERSION = "nf_federal_source_lane_v1"

FEDERAL_SOURCE_FAMILIES = frozenset(
    {
        "grants_gov",
        "federal_register",
        "agency_nofo_page",
        "agency_program_page",
        "native_specific_federal_program_page",
        "sam_gov_assistance_listing",
        "agency_rss_feed",
        "unknown",
    }
)

# Families that describe a single agency's own pages. For these, naming the
# department alone is insufficient — the whole point of the source is that it
# belongs to one program.
SUBAGENCY_REQUIRED_FAMILIES = frozenset(
    {
        "agency_nofo_page",
        "agency_program_page",
        "native_specific_federal_program_page",
        "agency_rss_feed",
    }
)

# Government-wide indexes. A department is not expected because they span all of
# them.
CROSS_AGENCY_FAMILIES = frozenset(
    {"grants_gov", "federal_register", "sam_gov_assistance_listing"}
)

FEDERAL_PROGRAM_SCOPES = frozenset(
    {
        "government_wide",
        "department_wide",
        "operating_division",
        "single_program",
        "unknown",
    }
)

PROMOTION_STATUSES = frozenset(
    {
        "discovered",
        "triaged",
        "approved_for_monitoring",
        "monitoring",
        "blocked",
        "unknown",
    }
)
MONITORING_STATUSES = frozenset({"approved_for_monitoring", "monitoring"})

ACCESS_METHODS = frozenset(
    {
        "public_api",
        "rss_or_atom",
        "bulk_download",
        "html_page_scheduled_check",
        "manual_operator_check",
        "unknown",
    }
)

# Departments whose operating divisions are commonly conflated. Recorded so the
# alignment check can say *why* it refused, not to grant any of them authority.
KNOWN_DEPARTMENTS = frozenset(
    {"HHS", "DOI", "DOE", "DOJ", "USDA", "ED", "DOT", "EPA", "HUD"}
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _normalize(value: str | None) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def split_agency_identifier(identifier: str | None) -> dict[str, str | None]:
    """Split a federal agency identifier into department and operating division.

    Handles the shapes this repo actually contains:
    ``"SAMHSA / HHS"``, ``"HHS-IHS"``, ``"HHS"``. Returns the pieces without
    deciding which is authoritative — that is the caller's job.
    """
    raw = str(identifier or "").strip()
    if not raw:
        return {"department": None, "subagency": None, "raw": None}

    parts: list[str]
    if "/" in raw:
        parts = [p.strip() for p in raw.split("/") if p.strip()]
    elif "-" in raw:
        parts = [p.strip() for p in raw.split("-") if p.strip()]
    else:
        parts = [raw]

    department: str | None = None
    subagency: str | None = None
    for part in parts:
        if part.upper() in KNOWN_DEPARTMENTS:
            department = part.upper()
        else:
            subagency = subagency or part
    if department is None and len(parts) == 1:
        # A single unrecognised token: treat it as the most specific thing we
        # know, which is the subagency.
        subagency = parts[0]
    return {"department": department, "subagency": subagency, "raw": raw}


def federal_agencies_align(left: str | None, right: str | None) -> dict[str, Any]:
    """Whether two federal agency identifiers denote the same program owner.

    Aligns only at the most specific level both sides declare. Two identifiers
    sharing a department but naming **different** operating divisions do NOT
    align — that is the IHS/SAMHSA case, and collapsing it is exactly the
    cross-program substitution the ownership guard exists to refuse.
    """
    a = split_agency_identifier(left)
    b = split_agency_identifier(right)

    if not a["raw"] or not b["raw"]:
        return {
            "aligned": False,
            "reason": "missing_agency_identifier",
            "left": a,
            "right": b,
        }

    a_sub, b_sub = _normalize(a["subagency"]), _normalize(b["subagency"])
    a_dep, b_dep = _normalize(a["department"]), _normalize(b["department"])

    if a_sub and b_sub:
        if a_sub == b_sub:
            return {"aligned": True, "reason": "subagency_match", "left": a, "right": b}
        return {
            "aligned": False,
            # Named explicitly so a reader sees the department match was
            # considered and deliberately rejected.
            "reason": (
                "different_subagency_same_department"
                if a_dep and a_dep == b_dep
                else "different_subagency"
            ),
            "left": a,
            "right": b,
        }

    # Only one side names an operating division. A department-level identifier
    # cannot confirm a program-level one.
    if a_sub or b_sub:
        return {
            "aligned": False,
            "reason": "subagency_required_but_only_department_supplied",
            "left": a,
            "right": b,
        }

    if a_dep and a_dep == b_dep:
        return {"aligned": True, "reason": "department_match", "left": a, "right": b}
    return {"aligned": False, "reason": "different_department", "left": a, "right": b}


def build_federal_source(
    *,
    source_id: str,
    source_family: str = "unknown",
    agency: str | None = None,
    subagency: str | None = None,
    bureau: str | None = None,
    program_name: str | None = None,
    source_url: str | None = None,
    access_method: str = "unknown",
    robots_terms_status: str = "unreviewed",
    refresh_cadence: str = "unknown",
    federal_program_scope: str = "unknown",
    native_relevance_expected: bool = False,
    native_relevance_rationale: str | None = None,
    provenance_url: str | None = None,
    promotion_status: str = "discovered",
    last_checked_at: str | None = None,
) -> dict[str, Any]:
    """Build one federal source record. Incomplete is incomplete, not approximate."""
    family = source_family if source_family in FEDERAL_SOURCE_FAMILIES else "unknown"
    robots = (
        robots_terms_status
        if robots_terms_status in ROBOTS_TERMS_STATUSES
        else "unknown"
    )
    promo = promotion_status if promotion_status in PROMOTION_STATUSES else "unknown"
    access = access_method if access_method in ACCESS_METHODS else "unknown"
    scope = (
        federal_program_scope
        if federal_program_scope in FEDERAL_PROGRAM_SCOPES
        else "unknown"
    )

    blocked: list[str] = []
    incomplete: list[str] = []

    if family == "unknown":
        blocked.append("source_family_unknown")

    # A federal source with no agency at all is incomplete regardless of family.
    if not agency and not subagency:
        incomplete.append("no_agency")

    # Agency-specific families must name their operating division. "HHS" does
    # not identify whose NOFO page this is.
    if family in SUBAGENCY_REQUIRED_FAMILIES and not subagency:
        incomplete.append("subagency_required_for_agency_specific_source")

    if not source_url:
        incomplete.append("no_source_url")
    if not provenance_url:
        incomplete.append("no_provenance_url")

    if robots not in ROBOTS_TERMS_CLEARED:
        blocked.append(f"robots_terms_not_cleared:{robots}")

    complete = not incomplete
    # Monitoring needs a permitting status, cleared terms, and completeness.
    monitoring_allowed = promo in MONITORING_STATUSES and not blocked and complete
    if promo in MONITORING_STATUSES and not monitoring_allowed:
        blocked.append("marked_monitoring_but_not_eligible")

    # Coverage credit needs provenance and completeness. Freshness cannot be
    # claimed without a check timestamp.
    counts_toward_coverage = complete and bool(provenance_url)
    freshness_claimable = bool(last_checked_at)

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "source_id": source_id,
            "source_family": family,
            "lane": "federal",
            "agency": agency,
            "subagency": subagency,
            "bureau": bureau,
            "agency_identifier": split_agency_identifier(
                subagency
                and agency
                and f"{subagency} / {agency}"
                or (subagency or agency)
            ),
            "program_name": program_name,
            "source_url": source_url,
            "access_method": access,
            "robots_terms_status": robots,
            "robots_terms_cleared": robots in ROBOTS_TERMS_CLEARED,
            "refresh_cadence": refresh_cadence,
            "federal_program_scope": scope,
            "native_relevance_expected": bool(native_relevance_expected),
            "native_relevance_rationale": native_relevance_rationale,
            "provenance_url": provenance_url,
            "promotion_status": promo,
            "last_checked_at": last_checked_at,
            "complete": complete,
            "incomplete_reasons": incomplete,
            "blocked_reasons": blocked,
            "monitoring_allowed": monitoring_allowed,
            "counts_toward_coverage": counts_toward_coverage,
            "freshness_claimable": freshness_claimable,
            # Honest boundaries for this gate.
            "coverage_claimed": False,
            "live_ingestion_claimed": False,
        }
    )


def federal_source_invariant_failures(record: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    if record.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")
    if record.get("source_family") not in FEDERAL_SOURCE_FAMILIES:
        fails.append("source_family_invalid")
    if record.get("lane") != "federal":
        fails.append("federal_source_left_the_federal_lane")
    if record.get("federal_program_scope") not in FEDERAL_PROGRAM_SCOPES:
        fails.append("federal_program_scope_invalid")

    if record.get("monitoring_allowed"):
        if record.get("promotion_status") not in MONITORING_STATUSES:
            fails.append("monitoring_from_non_monitoring_status")
        if not record.get("robots_terms_cleared"):
            fails.append("monitoring_without_cleared_terms")
        if not record.get("complete"):
            fails.append("monitoring_an_incomplete_source")
        if record.get("blocked_reasons"):
            fails.append("monitoring_with_blocked_reasons")

    if record.get("counts_toward_coverage") and not record.get("provenance_url"):
        fails.append("coverage_credit_without_provenance")
    if record.get("freshness_claimable") and not record.get("last_checked_at"):
        fails.append("freshness_claimable_without_a_check_timestamp")

    if (
        record.get("source_family") in SUBAGENCY_REQUIRED_FAMILIES
        and record.get("complete")
        and not record.get("subagency")
    ):
        fails.append("agency_specific_source_complete_without_a_subagency")

    for forbidden in ("coverage_claimed", "live_ingestion_claimed"):
        if record.get(forbidden) is not False:
            fails.append(f"forbidden_claim:{forbidden}")
    return fails
