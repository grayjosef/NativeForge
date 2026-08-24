"""Production source registry contract (Gate 76B).

A source record with a lifecycle. The question this answers is not "which
sources should we pursue" — `source_candidate_registry_service` already does
that — but "is this source cleared to be monitored, and is it stale or retired".

The control that matters: **unresolved robots/terms blocks monitoring.** A
registry that lets a source be monitored before someone has read its terms is a
scraping incident waiting to be discovered by the site owner. The gating is in
`can_monitor` rather than in a runbook, so it cannot be forgotten under
deadline pressure.

Nothing here fetches anything. There is no live coverage, no source is
monitored, and `last_checked_at` is only ever what a caller supplies — this
module never invents one.

Vocabulary note. `opportunity_discovery_quality_service` (Gate 54) already has a
10-value `SOURCE_TYPES` set with different names for overlapping concepts. Two
vocabularies for one idea drift, so `QUALITY_SOURCE_TYPE_MAP` below maps this
registry's types onto that set explicitly, keeping the existing scorer working
and making the divergence visible. See doc 418.
"""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.opportunity_discovery_quality_service import (
    SOURCE_TYPES as QUALITY_SOURCE_TYPES,
)

SCHEMA_VERSION = "nf_source_registry_v1"

SOURCE_TYPES = frozenset(
    {
        "grants_gov",
        "federal_agency_nofo_page",
        "federal_register",
        "state_grant_portal",
        "state_agency_page",
        "foundation",
        "community_foundation",
        "corporate_grants",
        "native_intermediary",
        "university_research",
        "local_regional",
        "unknown",
    }
)

# Explicit bridge to the Gate 54 scorer's vocabulary. Anything unmapped scores
# as "unknown" rather than silently as something else.
QUALITY_SOURCE_TYPE_MAP: dict[str, str] = {
    "grants_gov": "grants_gov",
    "federal_agency_nofo_page": "federal_agency_native_relevant",
    "federal_register": "federal_agency_native_relevant",
    "state_grant_portal": "state_grant_portal",
    "state_agency_page": "tribal_or_state_agency",
    "foundation": "philanthropic_foundation",
    "community_foundation": "philanthropic_foundation",
    "corporate_grants": "corporate_community_giving",
    "native_intermediary": "native_specific_intermediary",
    "university_research": "university_research_partnership",
    "local_regional": "local_or_regional",
    "unknown": "unknown",
}

JURISDICTIONS = frozenset({"federal", "state", "local", "tribal", "private", "unknown"})

PROMOTION_STATUSES = frozenset(
    {
        "discovered",
        "triaged",
        "approved_for_monitoring",
        "monitoring",
        "blocked_terms",
        "blocked_low_quality",
        "stale",
        "retired",
        "unknown",
    }
)

# Only these two permit monitoring. Derived denial set, so a status added later
# denies until someone deliberately permits it.
MONITORING_STATUSES = frozenset({"approved_for_monitoring", "monitoring"})
NON_MONITORING_STATUSES = PROMOTION_STATUSES - MONITORING_STATUSES

# Statuses that keep a source visible rather than hiding it. A stale source that
# disappears looks like a source we never had, which is how coverage silently
# shrinks.
VISIBLE_TERMINAL_STATUSES = frozenset({"stale", "retired"})

ROBOTS_TERMS_STATUSES = frozenset(
    {
        "reviewed_allowed",
        "reviewed_allowed_with_rate_limit",
        "reviewed_disallowed",
        "reviewed_requires_agreement",
        "unreviewed",
        "unknown",
    }
)

# Only a completed review that came back permissive clears monitoring.
ROBOTS_TERMS_CLEARED = frozenset(
    {"reviewed_allowed", "reviewed_allowed_with_rate_limit"}
)

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

REFRESH_CADENCES = frozenset(
    {"daily", "weekly", "biweekly", "monthly", "quarterly", "ad_hoc", "unknown"}
)

STALENESS_STATUSES = frozenset({"fresh", "aging", "stale", "unknown"})

RETIREMENT_STATUSES = frozenset({"active", "retirement_proposed", "retired", "unknown"})


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def quality_source_type(source_type: str) -> str:
    """Project a registry source type onto the Gate 54 scorer's vocabulary."""
    mapped = QUALITY_SOURCE_TYPE_MAP.get(source_type, "unknown")
    return mapped if mapped in QUALITY_SOURCE_TYPES else "unknown"


def build_source_record(
    *,
    source_id: str,
    source_name: str | None = None,
    source_url: str | None = None,
    source_type: str = "unknown",
    jurisdiction: str = "unknown",
    state: str | None = None,
    federal_agency: str | None = None,
    access_method: str = "unknown",
    refresh_cadence: str = "unknown",
    robots_terms_status: str = "unreviewed",
    promotion_status: str = "discovered",
    retirement_status: str = "active",
    last_checked_at: str | None = None,
    last_changed_at: str | None = None,
    staleness_status: str = "unknown",
    native_relevance_rationale: str | None = None,
    provenance_url: str | None = None,
    duplicate_group_id: str | None = None,
    is_duplicate: bool = False,
    created_at: str | None = None,
    updated_at: str | None = None,
) -> dict[str, Any]:
    """Build a source record, deriving trust rather than accepting it."""
    stype = source_type if source_type in SOURCE_TYPES else "unknown"
    juris = jurisdiction if jurisdiction in JURISDICTIONS else "unknown"
    access = access_method if access_method in ACCESS_METHODS else "unknown"
    cadence = refresh_cadence if refresh_cadence in REFRESH_CADENCES else "unknown"
    robots = (
        robots_terms_status
        if robots_terms_status in ROBOTS_TERMS_STATUSES
        else "unknown"
    )
    promo = promotion_status if promotion_status in PROMOTION_STATUSES else "unknown"
    retire = (
        retirement_status if retirement_status in RETIREMENT_STATUSES else "unknown"
    )
    stale = staleness_status if staleness_status in STALENESS_STATUSES else "unknown"

    # Derived overrides. A retired source is retired whatever the promotion
    # column says, and a source we have never checked has unknown staleness
    # rather than "fresh" — absence of evidence is not freshness.
    if retire == "retired":
        promo = "retired"
    if not last_checked_at:
        stale = "unknown"

    blocked: list[str] = []

    if promo == "unknown":
        blocked.append("promotion_status_unknown")
    if stype == "unknown":
        blocked.append("source_type_unknown")
    if robots not in ROBOTS_TERMS_CLEARED:
        blocked.append(f"robots_terms_not_cleared:{robots}")
    if promo == "blocked_terms":
        blocked.append("promotion_status_blocked_terms")
    if promo == "blocked_low_quality":
        blocked.append("promotion_status_blocked_low_quality")
    if promo in VISIBLE_TERMINAL_STATUSES:
        blocked.append(f"promotion_status_terminal:{promo}")
    if not source_url:
        blocked.append("no_source_url")

    # Monitoring requires the status to permit it AND nothing to block it.
    can_monitor = promo in MONITORING_STATUSES and not blocked
    if promo in MONITORING_STATUSES and blocked:
        # A source marked monitoring that cannot be monitored is a data defect
        # worth naming, not silently downgrading.
        blocked.append("marked_monitoring_but_not_eligible")

    # Quality credit requires provenance. Without a URL showing where the claim
    # came from, a high score is an assertion.
    has_provenance = bool(provenance_url)
    quality_credit_eligible = has_provenance and not is_duplicate

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "source_id": source_id,
            "source_name": source_name,
            "source_url": source_url,
            "source_type": stype,
            "quality_source_type": quality_source_type(stype),
            "jurisdiction": juris,
            "state": state,
            "federal_agency": federal_agency,
            "access_method": access,
            "refresh_cadence": cadence,
            "robots_terms_status": robots,
            "robots_terms_cleared": robots in ROBOTS_TERMS_CLEARED,
            "promotion_status": promo,
            "retirement_status": retire,
            "last_checked_at": last_checked_at,
            "last_changed_at": last_changed_at,
            "staleness_status": stale,
            "native_relevance_rationale": native_relevance_rationale,
            "provenance_url": provenance_url,
            "has_provenance": has_provenance,
            "duplicate_group_id": duplicate_group_id,
            "is_duplicate": bool(is_duplicate),
            "can_monitor": can_monitor,
            "blocked_reasons": blocked,
            "quality_credit_eligible": quality_credit_eligible,
            "visible": True,
            "created_at": created_at,
            "updated_at": updated_at,
            # Honest boundaries.
            "live_coverage_claimed": False,
            "monitoring_active": False,
        }
    )


def score_source_quality(record: dict[str, Any]) -> dict[str, Any]:
    """Score one source 0.0-1.0. Duplicates and missing provenance earn nothing.

    Deliberately not a volume metric. A registry of 500 unprovenanced duplicates
    scores zero, which is the point.
    """
    components: dict[str, float] = {
        "provenance": 0.0,
        "terms_reviewed": 0.0,
        "typed": 0.0,
        "cadence_declared": 0.0,
        "native_rationale": 0.0,
    }
    notes: list[str] = []

    if record.get("is_duplicate"):
        # A duplicate contributes nothing, so raw source count cannot be
        # inflated by re-listing the same portal.
        notes.append("duplicate_scores_zero")
        return _json_safe(
            {
                "schema_version": SCHEMA_VERSION,
                "source_id": record.get("source_id"),
                "quality_score": 0.0,
                "components": components,
                "notes": notes,
                "counts_toward_coverage": False,
            }
        )

    if not record.get("has_provenance"):
        notes.append("no_provenance_no_credit")
        return _json_safe(
            {
                "schema_version": SCHEMA_VERSION,
                "source_id": record.get("source_id"),
                "quality_score": 0.0,
                "components": components,
                "notes": notes,
                "counts_toward_coverage": False,
            }
        )

    components["provenance"] = 1.0
    if record.get("robots_terms_status") in ROBOTS_TERMS_CLEARED:
        components["terms_reviewed"] = 1.0
    elif record.get("robots_terms_status") not in {"unreviewed", "unknown"}:
        # A completed review that came back disallowed is still a completed
        # review; it earns half credit for being known.
        components["terms_reviewed"] = 0.5
    if record.get("source_type") != "unknown":
        components["typed"] = 1.0
    if record.get("refresh_cadence") != "unknown":
        components["cadence_declared"] = 1.0
    if record.get("native_relevance_rationale"):
        components["native_rationale"] = 1.0

    # A stale or retired source stays visible and stays counted as what it is,
    # but does not contribute current coverage quality.
    counts = record.get("promotion_status") not in VISIBLE_TERMINAL_STATUSES
    if not counts:
        notes.append(
            f"terminal_status_excluded_from_current_coverage:{record.get('promotion_status')}"
        )

    score = round(sum(components.values()) / len(components), 4)
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "source_id": record.get("source_id"),
            "quality_score": score if counts else 0.0,
            "components": components,
            "notes": notes,
            "counts_toward_coverage": counts,
        }
    )


def source_record_invariant_failures(record: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    if record.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")
    for field, vocab in (
        ("source_type", SOURCE_TYPES),
        ("jurisdiction", JURISDICTIONS),
        ("access_method", ACCESS_METHODS),
        ("refresh_cadence", REFRESH_CADENCES),
        ("robots_terms_status", ROBOTS_TERMS_STATUSES),
        ("promotion_status", PROMOTION_STATUSES),
        ("retirement_status", RETIREMENT_STATUSES),
        ("staleness_status", STALENESS_STATUSES),
    ):
        if record.get(field) not in vocab:
            fails.append(f"{field}_invalid")

    if record.get("can_monitor"):
        if record.get("promotion_status") not in MONITORING_STATUSES:
            fails.append("monitoring_from_non_monitoring_status")
        if record.get("robots_terms_status") not in ROBOTS_TERMS_CLEARED:
            fails.append("monitoring_without_cleared_terms")
        if record.get("source_type") == "unknown":
            fails.append("monitoring_an_unknown_source_type")
        if record.get("blocked_reasons"):
            fails.append("monitoring_with_blocked_reasons")

    if record.get("quality_credit_eligible"):
        if not record.get("has_provenance"):
            fails.append("quality_credit_without_provenance")
        if record.get("is_duplicate"):
            fails.append("quality_credit_for_duplicate")

    # A source we have never checked must not claim freshness.
    if (
        not record.get("last_checked_at")
        and record.get("staleness_status") != "unknown"
    ):
        fails.append("staleness_claimed_without_a_check_timestamp")

    # Stale and retired sources stay visible.
    if record.get("promotion_status") in VISIBLE_TERMINAL_STATUSES and not record.get(
        "visible"
    ):
        fails.append("terminal_status_hidden_instead_of_visible")

    for forbidden in ("live_coverage_claimed", "monitoring_active"):
        if record.get(forbidden) is not False:
            fails.append(f"forbidden_claim:{forbidden}")
    return fails
