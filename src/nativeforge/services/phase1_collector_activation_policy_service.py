"""Phase 1 collector activation policy (Gate 93D).

Names the preconditions each of the five Phase 1 sources must satisfy before it
may collect, and evaluates whether they are met. All five default to
``not_active`` and, in Gate 93, all five stay there.

## Preconditions are per-source because the constraints are

Two Grants.gov collectors share the attribution requirement and diverge after
it: the daily extract's 7-day retention makes a missed fetch unrecoverable, so
it needs a paging alert policy; Search2 exists to detect amendments, so it needs
the materiality policy or it produces noise nobody can triage.

SAM.gov is the only source whose terms prohibit the obvious implementation
outright. ``no_scraping_ack`` is a required precondition rather than a comment,
because "we know we're not allowed to scrape" is a fact that should have to be
recorded somewhere a reviewer can read.

USAspending's precondition is a *classification*: it carries zero NOFOs, so the
risk is not a bad fetch but a correct fetch surfaced as an open opportunity.

## Three separate answers, and all three are False in this gate

``may_fetch_live_now``       may a request go out right now
``may_schedule_monitor``     may a recurring check be scheduled
``may_surface_customer_data`` may results reach a customer

They are distinct because they fail independently: a source can be safely
fetchable and still not surfaceable, which is exactly the Grants.gov attribution
case. Invariants hold the first two at False for every Gate 93 result.

## Preflight is the gate, not a second opinion

``no Phase 1 source may activate without activation preflight PASS`` is
implemented by *requiring* a preflight result. A source with no preflight is
blocked, not assumed fine — the absence of a check is not the same as a check
that passed.
"""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.source_activation_preflight_service import (
    STORE_IMPLEMENTATION_SATISFYING,
    build_activation_preflight,
    detect_store_implementation,
    preflight_invariant_failures,
)

SCHEMA_VERSION = "nf_phase1_collector_activation_policy_v1"

COLLECTOR_STATUSES = frozenset({"not_active", "activating", "active", "halted"})

# Every precondition name this policy can require.
PRECONDITIONS = frozenset(
    {
        "activation_preflight_pass",
        "grants_gov_attribution",
        "raw_payload_store",
        "retention_alert_policy",
        "amendment_materiality_policy",
        "polling_cadence_policy",
        "public_inspection_handling",
        "api_key",
        "role_and_rate_limit_policy",
        "no_scraping_ack",
        "prior_award_only_classification",
    }
)

PHASE1_SOURCE_IDS: tuple[str, ...] = (
    "grants_gov_daily_extract",
    "grants_gov_search2_fetch",
    "federal_register_api",
    "sam_assistance_listings_api",
    "usaspending_api_v2",
)

# Per-source requirements. Preflight and the raw payload store are universal;
# the rest come from that source's own documented constraint.
REQUIRED_PRECONDITIONS: dict[str, tuple[str, ...]] = {
    "grants_gov_daily_extract": (
        "activation_preflight_pass",
        "grants_gov_attribution",
        "raw_payload_store",
        "retention_alert_policy",
    ),
    "grants_gov_search2_fetch": (
        "activation_preflight_pass",
        "grants_gov_attribution",
        "raw_payload_store",
        "amendment_materiality_policy",
    ),
    "federal_register_api": (
        "activation_preflight_pass",
        "raw_payload_store",
        "polling_cadence_policy",
        "public_inspection_handling",
    ),
    "sam_assistance_listings_api": (
        "activation_preflight_pass",
        "raw_payload_store",
        "api_key",
        "role_and_rate_limit_policy",
        "no_scraping_ack",
    ),
    "usaspending_api_v2": (
        "activation_preflight_pass",
        "raw_payload_store",
        "prior_award_only_classification",
    ),
}

# Sources whose output requires the Grants.gov notice before it is surfaced.
ATTRIBUTION_GATED_SOURCES = frozenset(
    {"grants_gov_daily_extract", "grants_gov_search2_fetch"}
)

# SAM.gov, and the prohibition that is not negotiable by satisfying other rules.
SCRAPING_PROHIBITED_SOURCES = frozenset({"sam_assistance_listings_api"})

# USAspending carries no NOFOs; its records are never open opportunities.
PRIOR_AWARD_ONLY_SOURCES = frozenset({"usaspending_api_v2"})


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def evaluate_phase1_source(
    *,
    source_id: str,
    satisfied_preconditions: list[Any] | None = None,
    preflight: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """One Phase 1 source's activation position. Nothing is activated."""
    if source_id not in REQUIRED_PRECONDITIONS:
        raise ValueError(f"unknown Phase 1 source: {source_id!r}")

    required = REQUIRED_PRECONDITIONS[source_id]

    # Only recognised names count. An unrecognised precondition is reported
    # rather than silently treated as satisfying something.
    declared = [
        str(p).strip() for p in (satisfied_preconditions or []) if str(p).strip()
    ]
    satisfied = {p for p in declared if p in PRECONDITIONS}
    unrecognised = sorted({p for p in declared if p not in PRECONDITIONS})

    # A source with no preflight is blocked. Absence of a check is not a pass.
    preflight_passed = bool(preflight and preflight.get("activation_allowed"))
    if preflight_passed:
        satisfied.add("activation_preflight_pass")
    else:
        satisfied.discard("activation_preflight_pass")

    missing = [p for p in required if p not in satisfied]

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "source_id": source_id,
            # Constant for this gate.
            "collector_status": "not_active",
            "activation_status": (
                "activation_blocked" if missing else "preconditions_satisfied"
            ),
            "required_preconditions": list(required),
            "satisfied_preconditions": sorted(satisfied & set(required)),
            "missing_preconditions": missing,
            "unrecognised_preconditions": unrecognised,
            "preflight_present": preflight is not None,
            "preflight_passed": preflight_passed,
            # All three constants for this gate, held by invariants.
            "may_fetch_live_now": False,
            "may_schedule_monitor": False,
            "may_surface_customer_data": False,
            # Source-specific facts that do not change with configuration.
            "attribution_required": source_id in ATTRIBUTION_GATED_SOURCES,
            "scraping_prohibited": source_id in SCRAPING_PROHIBITED_SOURCES,
            "prior_award_only": source_id in PRIOR_AWARD_ONLY_SOURCES,
            "fetch_performed": False,
            "fabricated": False,
        }
    )


def build_phase1_activation_matrix(
    *,
    satisfied_by_source: dict[str, list[Any]] | None = None,
    preflight_by_source: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """All five sources, evaluated together."""
    satisfied_by_source = satisfied_by_source or {}
    preflight_by_source = preflight_by_source or {}

    rows = [
        evaluate_phase1_source(
            source_id=sid,
            satisfied_preconditions=satisfied_by_source.get(sid),
            preflight=preflight_by_source.get(sid),
        )
        for sid in PHASE1_SOURCE_IDS
    ]

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "phase": 1,
            "source_count": len(rows),
            "sources": rows,
            "collectors_active": 0,
            "monitors_active": 0,
            "live_fetch_performed": False,
            "live_source_coverage": False,
            # Gate 95. Three separate facts. The local store exists and is
            # usable for fixtures and dry-runs; production storage does not
            # exist, and a local store is not a step toward claiming it does.
            "raw_payload_store_contract_available": True,
            "local_raw_payload_store_available": detect_store_implementation()
            in STORE_IMPLEMENTATION_SATISFYING,
            "production_raw_payload_store_available": False,
            "sources_may_fetch_live_now": 0,
            "sources_may_schedule_monitor": 0,
            "sources_may_surface_customer_data": 0,
            "fabricated": False,
        }
    )


def default_phase1_preflights() -> dict[str, dict[str, Any]]:
    """Preflight for each Phase 1 source as things actually stand today.

    Nothing here is aspirational: the raw payload store does not exist, no
    credential is held, and no scheduler policy is wired, so every source
    reports the requirements it is actually missing.
    """
    common = dict(
        legal_review_status="not_required",
        rate_limit_status="policy_declared",
        # Gate 93A found no durable payload store, so this is `missing`, not
        # `contract_satisfied`. Writing the contract is not implementing it.
        storage_status="missing",
        scheduler_status="missing",
        monitoring_status="not_started",
    )
    return {
        "grants_gov_daily_extract": build_activation_preflight(
            source_id="grants_gov_daily_extract",
            source_name="Grants.gov daily XML extract",
            source_role="corpus_of_record",
            collector_type="bulk_extract",
            terms_status="ATTRIBUTION_REQUIRED",
            attribution_status="present_and_verbatim",
            credential_status="not_required",
            user_agent_status="not_required",
            **common,
        ),
        "grants_gov_search2_fetch": build_activation_preflight(
            source_id="grants_gov_search2_fetch",
            source_name="Grants.gov Search2 + fetchOpportunity",
            source_role="delta_accelerator",
            collector_type="public_api",
            terms_status="ATTRIBUTION_REQUIRED",
            attribution_status="present_and_verbatim",
            credential_status="not_required",
            user_agent_status="not_required",
            **common,
        ),
        "federal_register_api": build_activation_preflight(
            source_id="federal_register_api",
            source_name="Federal Register API",
            source_role="notice_feed",
            collector_type="public_api",
            terms_status="NO_REVIEW_REQUIRED",
            attribution_status="not_required",
            credential_status="not_required",
            user_agent_status="not_required",
            **common,
        ),
        "sam_assistance_listings_api": build_activation_preflight(
            source_id="sam_assistance_listings_api",
            source_name="SAM.gov Assistance Listings API",
            source_role="program_catalog",
            collector_type="public_api_with_key",
            terms_status="TERMS_REVIEW_REQUIRED",
            attribution_status="not_required",
            # No key is held and no SAM role has been obtained.
            credential_status="missing",
            user_agent_status="not_required",
            **common,
        ),
        "usaspending_api_v2": build_activation_preflight(
            source_id="usaspending_api_v2",
            source_name="USAspending API v2",
            source_role="prior_award_intelligence",
            collector_type="public_api",
            terms_status="NO_REVIEW_REQUIRED",
            attribution_status="not_required",
            credential_status="not_required",
            user_agent_status="not_required",
            **common,
        ),
    }


def policy_invariant_failures(matrix: dict[str, Any]) -> list[str]:
    fails: list[str] = []

    if matrix.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")
    if matrix.get("fabricated") is not False:
        fails.append("fabricated_must_be_false")

    for constant in ("live_fetch_performed", "live_source_coverage"):
        if matrix.get(constant) is not False:
            fails.append(f"matrix_claimed:{constant}")
    for counter in (
        "collectors_active",
        "monitors_active",
        "sources_may_fetch_live_now",
        "sources_may_schedule_monitor",
        "sources_may_surface_customer_data",
    ):
        if matrix.get(counter):
            fails.append(f"matrix_reported_nonzero:{counter}")

    # Gate 95: a local store is not a production store.
    if matrix.get("production_raw_payload_store_available") is not False:
        fails.append("matrix_claimed_production_payload_storage")

    seen = [s.get("source_id") for s in matrix.get("sources") or []]
    if seen != list(PHASE1_SOURCE_IDS):
        fails.append("phase1_source_set_altered")

    for source in matrix.get("sources") or []:
        sid = source.get("source_id")
        if source.get("collector_status") not in COLLECTOR_STATUSES:
            fails.append(f"collector_status_out_of_vocabulary:{sid}")
        if source.get("collector_status") != "not_active":
            fails.append(f"collector_marked_active:{sid}")
        for constant in (
            "may_fetch_live_now",
            "may_schedule_monitor",
            "may_surface_customer_data",
            "fetch_performed",
        ):
            if source.get(constant) is not False:
                fails.append(f"source_claimed:{sid}:{constant}")

        required = set(source.get("required_preconditions") or [])
        if required - PRECONDITIONS:
            fails.append(f"precondition_out_of_vocabulary:{sid}")
        if required != set(REQUIRED_PRECONDITIONS.get(sid, ())):
            fails.append(f"required_preconditions_altered:{sid}")

        # Preflight is mandatory for every Phase 1 source, and its absence
        # must show up as a missing precondition rather than as silence.
        if "activation_preflight_pass" not in required:
            fails.append(f"preflight_not_required:{sid}")
        reported_missing = source.get("missing_preconditions") or []
        if not source.get("preflight_passed") and (
            "activation_preflight_pass" not in reported_missing
        ):
            fails.append(f"failed_preflight_not_reported_missing:{sid}")

        # Satisfied and missing together account for every requirement.
        satisfied = set(source.get("satisfied_preconditions") or [])
        missing = set(source.get("missing_preconditions") or [])
        if satisfied & missing:
            fails.append(f"precondition_both_satisfied_and_missing:{sid}")
        if satisfied | missing != required:
            fails.append(f"precondition_dropped:{sid}")

        # Source-specific facts are not configurable away.
        if sid in ATTRIBUTION_GATED_SOURCES:
            if source.get("attribution_required") is not True:
                fails.append(f"grants_gov_source_without_attribution_requirement:{sid}")
            if "grants_gov_attribution" not in required:
                fails.append(f"attribution_missing_from_preconditions:{sid}")
        if sid in SCRAPING_PROHIBITED_SOURCES:
            if source.get("scraping_prohibited") is not True:
                fails.append(f"scraping_prohibition_dropped:{sid}")
            if "no_scraping_ack" not in required:
                fails.append(f"no_scraping_ack_missing:{sid}")
            if "api_key" not in required:
                fails.append(f"sam_api_key_not_required:{sid}")
        if sid in PRIOR_AWARD_ONLY_SOURCES:
            if source.get("prior_award_only") is not True:
                fails.append(f"prior_award_only_classification_dropped:{sid}")

        # The universal one.
        if "raw_payload_store" not in required:
            fails.append(f"raw_payload_store_not_required:{sid}")

    return fails


def phase1_preflight_invariant_failures(
    preflights: dict[str, dict[str, Any]],
) -> list[str]:
    """Every Phase 1 preflight must itself be a valid preflight."""
    fails: list[str] = []
    for sid, result in preflights.items():
        for failure in preflight_invariant_failures(result):
            fails.append(f"{sid}:{failure}")
    return fails
