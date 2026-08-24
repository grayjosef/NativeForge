"""South Carolina state source lane (Gate 78B).

The SC lane, built after the federal lane because South Carolina is the first
production-quality proving ground and the initial customer set is SC-based
Native and tribal organizations.

The rule that shapes everything here, and the one most likely to be got wrong:
**SC-specific is not SC-only.** A federal opportunity that an SC organization
can pursue is a *federal* source and stays in the federal lane. Only sources
owned and administered by South Carolina belong here. Collapsing the two would
undercount federal coverage and overcount state coverage, and would tell a
customer their funding landscape is smaller and more local than it is — which
for a tribal organization in a state with few state-administered Native
programs would be actively misleading.

`sc_state_source_adapter_config_service` already states this as
``organization_geography_must_not_filter_federal``. This module enforces it at
the record level.

The second rule, inherited rather than restated: **state recognition is not
federal recognition.** `recognition_routing_contract_service` (Block 27) already
says *"State-recognized status is never treated as federally recognized"*. South
Carolina has state-recognized tribes, so this is the concrete, local case rather
than an abstraction. Recognition relevance here is a **set**, and membership in
one tier never implies another.

Nothing here fetches. `coverage_claimed` and `monitoring_allowed` are False on
every record this gate produces.
"""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.sc_federal_discovery_improvement_service import (
    RECOGNITION_ROUTES,
)
from nativeforge.services.source_registry_service import (
    ROBOTS_TERMS_CLEARED,
    ROBOTS_TERMS_STATUSES,
)

SCHEMA_VERSION = "nf_sc_state_source_lane_v1"

STATE_CODE = "SC"

SC_SOURCE_FAMILIES = frozenset(
    {
        "sc_state_grant_portal",
        "sc_agency_grant_page",
        "sc_agency_program_page",
        "sc_procurement_or_contracting_page",
        "sc_foundation",
        "sc_community_foundation",
        "sc_regional_council",
        "sc_local_government",
        "native_intermediary",
        "unknown",
    }
)

# Families administered by a named state agency. For these, "South Carolina" is
# not enough — the agency owns the page and the program.
STATE_AGENCY_REQUIRED_FAMILIES = frozenset(
    {
        "sc_agency_grant_page",
        "sc_agency_program_page",
        "sc_procurement_or_contracting_page",
    }
)

# Private or sub-state families. A state agency is not expected.
NON_STATE_AGENCY_FAMILIES = frozenset(
    {
        "sc_foundation",
        "sc_community_foundation",
        "sc_regional_council",
        "sc_local_government",
        "native_intermediary",
    }
)

STATE_PROGRAM_SCOPES = frozenset(
    {
        "statewide",
        "agency_wide",
        "single_program",
        "regional",
        "local",
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

# Source-level *expectation* of who a source tends to serve. Deliberately named
# "relevance" rather than "eligibility": a source that often carries tribal
# opportunities does not make any particular opportunity open to any particular
# applicant. That determination is opportunity-level and evidence-gated.
RECOGNITION_RELEVANCE = frozenset(
    {
        "state_recognized_relevant",
        "federally_recognized_relevant",
        "native_nonprofit_relevant",
        "native_business_relevant",
        "native_community_relevant",
        "unknown",
    }
)

# Bridge onto the existing Gate 56 vocabulary so the improvement scorer keeps
# working and the divergence stays visible. `native_community_relevant` has no
# Gate 56 route — it describes a community served, not an applicant type — so it
# maps to unknown rather than borrowing one.
RECOGNITION_ROUTE_MAP: dict[str, str] = {
    "federally_recognized_relevant": "federally_recognized",
    "state_recognized_relevant": "state_recognized",
    "native_nonprofit_relevant": "native_nonprofit",
    "native_business_relevant": "native_business_economic_development",
    "native_community_relevant": "unknown",
    "unknown": "unknown",
}


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def recognition_route(relevance: str) -> str:
    """Project an SC relevance tag onto the Gate 56 recognition route set."""
    mapped = RECOGNITION_ROUTE_MAP.get(relevance, "unknown")
    return mapped if mapped in RECOGNITION_ROUTES else "unknown"


def normalize_recognition_relevance(tags: list[str] | None) -> dict[str, Any]:
    """Normalise a relevance tag set, keeping each tier independent.

    Returns the recognised tags, the Gate 56 routes they project onto, and the
    unrecognised remainder for review. Crucially it performs **no inference**:
    a federally-recognized tag never adds a state-recognized one, or vice versa.
    """
    supplied = [t for t in (tags or []) if t in RECOGNITION_RELEVANCE]
    unrecognised = sorted({t for t in (tags or []) if t not in RECOGNITION_RELEVANCE})
    known = sorted({t for t in supplied if t != "unknown"})

    return {
        "recognition_relevance": known or ["unknown"],
        "recognition_routes": sorted(
            {recognition_route(t) for t in known} - {"unknown"}
        )
        or ["unknown"],
        "unrecognised_relevance_tags": unrecognised,
        "recognition_known": bool(known),
        "state_recognized_relevant": "state_recognized_relevant" in known,
        "federally_recognized_relevant": "federally_recognized_relevant" in known,
    }


def build_sc_source(
    *,
    source_id: str,
    source_family: str = "unknown",
    state: str = STATE_CODE,
    state_agency: str | None = None,
    subagency: str | None = None,
    program_name: str | None = None,
    source_url: str | None = None,
    access_method: str = "unknown",
    robots_terms_status: str = "unreviewed",
    refresh_cadence: str = "unknown",
    state_program_scope: str = "unknown",
    native_relevance_expected: bool = False,
    native_relevance_rationale: str | None = None,
    recognition_relevance: list[str] | None = None,
    provenance_url: str | None = None,
    promotion_status: str = "discovered",
    last_checked_at: str | None = None,
    federal_agency: str | None = None,
) -> dict[str, Any]:
    """Build one SC state-lane source record.

    ``federal_agency`` is accepted **so it can be rejected**. A source owned by a
    federal agency is not an SC state source, and taking the field and refusing
    it makes that boundary visible in the record rather than relying on callers
    to know.
    """
    family = source_family if source_family in SC_SOURCE_FAMILIES else "unknown"
    robots = (
        robots_terms_status
        if robots_terms_status in ROBOTS_TERMS_STATUSES
        else "unknown"
    )
    promo = promotion_status if promotion_status in PROMOTION_STATUSES else "unknown"
    access = access_method if access_method in ACCESS_METHODS else "unknown"
    scope = (
        state_program_scope
        if state_program_scope in STATE_PROGRAM_SCOPES
        else "unknown"
    )
    routing = normalize_recognition_relevance(recognition_relevance)

    blocked: list[str] = []
    incomplete: list[str] = []

    if family == "unknown":
        blocked.append("source_family_unknown")

    # ── the lane boundary ────────────────────────────────────────────────
    if str(state or "").upper() != STATE_CODE:
        blocked.append(f"not_a_south_carolina_source:{state or 'none'}")
    if federal_agency:
        # A federal opportunity relevant to SC belongs in the federal lane.
        blocked.append(f"federally_owned_source_not_sc_state:{federal_agency}")

    # ── completeness ─────────────────────────────────────────────────────
    if family in STATE_AGENCY_REQUIRED_FAMILIES and not state_agency:
        incomplete.append("state_agency_required_for_agency_specific_source")
    if not source_url:
        incomplete.append("no_source_url")
    if not provenance_url:
        incomplete.append("no_provenance_url")

    if robots not in ROBOTS_TERMS_CLEARED:
        blocked.append(f"robots_terms_not_cleared:{robots}")

    if routing["unrecognised_relevance_tags"]:
        incomplete.append("unrecognised_recognition_relevance_tags")

    complete = not incomplete
    monitoring_allowed = promo in MONITORING_STATUSES and not blocked and complete
    if promo in MONITORING_STATUSES and not monitoring_allowed:
        blocked.append("marked_monitoring_but_not_eligible")

    counts_toward_coverage = complete and bool(provenance_url) and not blocked
    freshness_claimable = bool(last_checked_at)

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "source_id": source_id,
            "source_family": family,
            "lane": "sc_state",
            "state": STATE_CODE if str(state or "").upper() == STATE_CODE else state,
            "state_agency": state_agency,
            "subagency": subagency,
            # Always None on an SC state record. Present so its absence is an
            # asserted property rather than an omission.
            "federal_agency": None,
            "rejected_federal_agency": federal_agency,
            "program_name": program_name,
            "source_url": source_url,
            "access_method": access,
            "robots_terms_status": robots,
            "robots_terms_cleared": robots in ROBOTS_TERMS_CLEARED,
            "refresh_cadence": refresh_cadence,
            "state_program_scope": scope,
            "native_relevance_expected": bool(native_relevance_expected),
            "native_relevance_rationale": native_relevance_rationale,
            **routing,
            "provenance_url": provenance_url,
            "promotion_status": promo,
            "last_checked_at": last_checked_at,
            "complete": complete,
            "incomplete_reasons": incomplete,
            "blocked_reasons": blocked,
            "monitoring_allowed": monitoring_allowed,
            "counts_toward_coverage": counts_toward_coverage,
            "freshness_claimable": freshness_claimable,
            # Source-level expectation is never opportunity-level eligibility.
            "eligibility_determined": False,
            # Honest boundaries for this gate.
            "coverage_claimed": False,
            "live_ingestion_claimed": False,
        }
    )


def sc_source_invariant_failures(record: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    if record.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")
    if record.get("source_family") not in SC_SOURCE_FAMILIES:
        fails.append("source_family_invalid")
    if record.get("lane") != "sc_state":
        fails.append("sc_source_left_the_sc_state_lane")
    if record.get("state_program_scope") not in STATE_PROGRAM_SCOPES:
        fails.append("state_program_scope_invalid")

    # An SC state source may never carry a federal owner.
    if record.get("federal_agency"):
        fails.append("sc_state_source_carries_a_federal_agency")

    for tag in record.get("recognition_relevance") or []:
        if tag not in RECOGNITION_RELEVANCE:
            fails.append(f"recognition_relevance_invalid:{tag}")

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
        record.get("source_family") in STATE_AGENCY_REQUIRED_FAMILIES
        and record.get("complete")
        and not record.get("state_agency")
    ):
        fails.append("agency_specific_source_complete_without_a_state_agency")

    # Source-level relevance must never be reported as eligibility.
    if record.get("eligibility_determined") is not False:
        fails.append("forbidden_claim:eligibility_determined")
    for forbidden in ("coverage_claimed", "live_ingestion_claimed"):
        if record.get(forbidden) is not False:
            fails.append(f"forbidden_claim:{forbidden}")
    return fails
