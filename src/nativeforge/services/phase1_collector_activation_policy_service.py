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


def _production_store_available() -> bool:
    """Detected via the readiness service, which detects each component."""
    try:
        from nativeforge.services.raw_payload_production_readiness_service import (
            build_production_readiness,
        )
    except ImportError:
        return False
    return bool(
        build_production_readiness()["production_raw_payload_store_available"]
    )


def _body_store_implementation() -> bool:
    try:
        from nativeforge.services.raw_payload_body_store_contract_service import (
            detect_body_store_implementation,
        )
    except ImportError:
        return False
    return bool(detect_body_store_implementation())


def _body_store_configured() -> bool:
    try:
        from nativeforge.services.raw_payload_body_store_contract_service import (
            build_body_store_contract,
        )
    except ImportError:
        return False
    return bool(build_body_store_contract()["body_store_configured"])


def _metadata_table_available() -> bool:
    try:
        from nativeforge.services.production_raw_payload_repository_service import (
            detect_metadata_table,
        )
    except ImportError:
        return False
    return bool(detect_metadata_table())


def _scheduler_runtime_available() -> bool:
    """Gate 98F: is there a scheduler, detected via Gate 98E?

    Activating a collector and scheduling one are different questions. A
    collector can be activated for operator-triggered checks on a platform with
    no worker at all; a *monitor* cannot. This is the second half, and it is
    detected rather than declared.
    """
    try:
        from nativeforge.services.source_scheduler_readiness_service import (
            build_scheduler_readiness,
        )
    except ImportError:
        return False
    readiness = build_scheduler_readiness()
    return bool(
        readiness["scheduler_runtime_available"]
        and readiness["background_worker_available"]
    )


def _monitoring_live() -> bool:
    """Whether anything is actually monitoring, detected via Gate 98E."""
    try:
        from nativeforge.services.source_scheduler_readiness_service import (
            build_scheduler_readiness,
        )
    except ImportError:
        return False
    return bool(build_scheduler_readiness()["source_monitoring_live"])


def _dry_run_worker_available() -> bool:
    """Gate 100D: a dry-run worker exists and buys nothing here.

    Reported on the matrix so the distinction is on the record. A worker that
    marks jobs is not a worker that runs them, and `may_schedule_monitor`
    continues to require `_scheduler_runtime_available()`, which requires a
    detected background worker - of which there is none.
    """
    try:
        from nativeforge.services.source_scheduler_readiness_service import (
            build_scheduler_readiness,
        )
    except ImportError:
        return False
    return bool(build_scheduler_readiness().get("dry_run_worker_available"))


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

    scheduler_runtime_available = _scheduler_runtime_available()

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
            # Constants for this gate, held by invariants.
            "may_fetch_live_now": False,
            "may_surface_customer_data": False,
            # Gate 98F: derived, not asserted.
            #
            # This was `False` outright. Gate 97 found two guards of exactly
            # that shape and had to convert them: a constant that is correct
            # today encodes one moment as a permanent law, and it would go on
            # reading False after somebody deployed a worker. Scheduling a
            # monitor needs the source cleared for activation *and* something
            # that can run it, so it is now the conjunction of the two - which
            # still reads False today, on its own.
            "may_schedule_monitor": bool(
                preflight_passed and scheduler_runtime_available
            ),
            "scheduler_runtime_available": scheduler_runtime_available,
            "activation_is_not_scheduler_readiness": True,
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
            # Gate 98F: derived. Nothing can be monitoring without a runtime to
            # run it, and Gate 98E detects whether one exists.
            "monitors_active": sum(1 for r in rows if r["may_schedule_monitor"])
            if _monitoring_live()
            else 0,
            "scheduler_runtime_available": _scheduler_runtime_available(),
            "source_monitoring_live": _monitoring_live(),
            # Gate 100D. On the record, and load-bearing for nothing.
            "dry_run_worker_available": _dry_run_worker_available(),
            "live_fetch_performed": False,
            "live_source_coverage": False,
            # Gate 95. Three separate facts. The local store exists and is
            # usable for fixtures and dry-runs; production storage does not
            # exist, and a local store is not a step toward claiming it does.
            "raw_payload_store_contract_available": True,
            "local_raw_payload_store_available": detect_store_implementation()
            in STORE_IMPLEMENTATION_SATISFYING,
            # Gate 96: detected, not hardcoded. It reads False today because
            # no body store is configured - but it reads False by *derivation*
            # rather than by assertion, so it will change on its own when a
            # body store exists rather than needing someone to remember.
            "production_raw_payload_store_available": _production_store_available(),
            "metadata_table_available": _metadata_table_available(),
            # Gate 97: the two halves of the body-store question, reported
            # apart so neither can stand in for the other.
            "body_store_implementation_available": _body_store_implementation(),
            "body_store_configured": _body_store_configured(),
            # A live collection needs production storage. Dry-run scaffolding
            # may use the local store.
            "live_collection_requires_production_store": True,
            "sources_may_fetch_live_now": 0,
            # Gate 98F: derived from the rows rather than restated beside them.
            "sources_may_schedule_monitor": sum(
                1 for r in rows if r["may_schedule_monitor"]
            ),
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
        "sources_may_fetch_live_now",
        "sources_may_surface_customer_data",
    ):
        if matrix.get(counter):
            fails.append(f"matrix_reported_nonzero:{counter}")

    # Gate 98F: the two monitoring counters were in the list above, asserted at
    # zero. That is the constant-versus-derivation defect Gate 97 corrected for
    # the payload store, and it would have kept reading zero after a worker was
    # deployed. They are now checked for *agreement* with the rows they
    # summarise, which holds them at zero today and keeps holding them honest
    # after that stops being true.
    rows = matrix.get("sources") or []
    schedulable = sum(1 for r in rows if r.get("may_schedule_monitor"))
    if matrix.get("sources_may_schedule_monitor") != schedulable:
        fails.append("schedulable_count_disagrees_with_the_rows")

    monitors = matrix.get("monitors_active")
    if not matrix.get("source_monitoring_live") and monitors:
        fails.append("monitors_active_without_live_monitoring")
    if isinstance(monitors, int) and monitors > schedulable:
        fails.append("more_monitors_active_than_sources_may_schedule")

    if matrix.get("sources_may_schedule_monitor") and not matrix.get(
        "scheduler_runtime_available"
    ):
        fails.append("sources_schedulable_without_a_scheduler_runtime")

    # Gate 100D. A dry-run worker may never be the thing that makes a source
    # schedulable or a collector fetchable. `scheduler_runtime_available` here
    # already requires a detected background worker; this fails loudly if a
    # future edit ever lets the dry-run answer stand in for it.
    if matrix.get("dry_run_worker_available") and not matrix.get(
        "scheduler_runtime_available"
    ):
        if matrix.get("sources_may_schedule_monitor") or matrix.get("monitors_active"):
            fails.append("dry_run_worker_read_as_a_production_worker")
        for source in matrix.get("sources") or []:
            if source.get("may_schedule_monitor") or source.get("may_fetch_live_now"):
                fails.append(
                    f"dry_run_worker_permitted_live_work:{source.get('source_id')}"
                )

    # Gate 95/96/97: a local store is not a production store, a metadata table
    # alone is not production storage, and an implementation is not a
    # configuration.
    #
    # Gate 96 wrote these as `is not False` - a constant, correct at the time
    # because nothing could configure a body store. Gate 97 makes configuration
    # possible, and a constant that was true of one moment is not a law. These
    # are now checks on the *derivation*: production availability must follow
    # from its components, and no single component may stand in for the whole.
    available = matrix.get("production_raw_payload_store_available")
    metadata = matrix.get("metadata_table_available")
    implementation = matrix.get("body_store_implementation_available")
    configured = matrix.get("body_store_configured")

    if available and not configured:
        fails.append("metadata_table_treated_as_production_storage")
        fails.append("implementation_treated_as_a_configured_body_store")
    if available and not metadata:
        fails.append("available_without_a_metadata_table")
    if available and not implementation:
        fails.append("available_without_a_body_store_implementation")
    if configured and not implementation:
        fails.append("configured_without_an_implementation")

    if matrix.get("live_collection_requires_production_store") is not True:
        fails.append("live_collection_production_requirement_dropped")

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
            "may_surface_customer_data",
            "fetch_performed",
        ):
            if source.get(constant) is not False:
                fails.append(f"source_claimed:{sid}:{constant}")

        # Gate 98F: a derivation, checked as one. Scheduling a monitor needs
        # both halves - the source cleared, and something to run it.
        if source.get("may_schedule_monitor"):
            if not source.get("preflight_passed"):
                fails.append(f"schedulable_without_a_preflight_pass:{sid}")
            if not source.get("scheduler_runtime_available"):
                fails.append(f"schedulable_without_a_scheduler_runtime:{sid}")

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
