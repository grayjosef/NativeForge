"""External source registry seed (Gate 90C).

Converts imported CSV rows into NativeForge registry seed objects **without
activating monitoring**.

## Why this does not reuse `source_registry_service.build_source_record`

Gate 76's registry derives trust rather than accepting it, and its
``PROMOTION_STATUSES`` include ``approved_for_monitoring`` and ``monitoring``.
Projecting 55 unreviewed external rows through it would put them one field away
from a monitoring status they have not earned.

So the seed layer keeps them separate and *bridges* to Gate 76's vocabulary
instead of forking it: every seed carries a ``gate76_promotion_status`` of
``discovered`` and a ``gate76_robots_terms_status`` of ``unreviewed``, which are
the weakest members of those existing frozensets. Nothing here can produce a
value in ``MONITORING_STATUSES``, and an invariant proves it.

That is the campaign's usual answer - bridge onto the existing vocabulary,
never redeclare it - applied where the existing vocabulary is too permissive to
adopt wholesale.

## The four separations this layer maintains

``registry_status``     the source exists in our list
``monitoring_status``   whether we are watching it          (always not_started)
``terms_status``        whether we are allowed to watch it
``eligibility_status``  whether a customer could apply      (never determined here)
``allowability_status`` whether an award could buy software (never determined here)

Being in the registry answers only the first.
"""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.external_source_registry_import_service import (
    MONITORING_STATUS,
    REGISTRY_STATUS,
)
from nativeforge.services.source_registry_service import (
    MONITORING_STATUSES,
    PROMOTION_STATUSES,
    ROBOTS_TERMS_STATUSES,
)

SCHEMA_VERSION = "nf_external_source_registry_seed_v1"

# Bridge onto Gate 76's vocabulary at its weakest members. Both are asserted
# against the imported frozensets by an invariant, so a rename upstream fails
# here rather than drifting.
GATE76_PROMOTION_STATUS = "discovered"
GATE76_ROBOTS_TERMS_STATUS = "unreviewed"

# Monitoring methods that can only ever be executed by a person.
HUMAN_ONLY_METHODS = frozenset({"human review only", "email bulletin/manual intake"})

# Terms statuses that permit an automated check once someone implements the
# obligation. Everything else needs a human decision first.
AUTOMATABLE_AFTER_REVIEW = frozenset({"NO_REVIEW_REQUIRED", "ATTRIBUTION_REQUIRED"})


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def build_source_registry_seed(*, imported_source: dict[str, Any]) -> dict[str, Any]:
    """One imported row -> one registry seed object."""
    s = imported_source
    terms_status = s.get("terms_status") or "UNKNOWN"
    method = s.get("monitoring_method") or ""
    requires_login = s.get("requires_login") or ""

    human_review_only = (
        terms_status == "HUMAN_REVIEW_ONLY"
        or method in HUMAN_ONLY_METHODS
        or requires_login == "Yes"
    )
    legal_terms_review_required = terms_status not in AUTOMATABLE_AFTER_REVIEW

    blocked = list(s.get("activation_blocked_reasons") or [])
    if human_review_only and "human_review_only" not in blocked:
        blocked.append("human_review_only")

    # `has_api` describes the source. It says nothing about our permission to
    # call it, so the two are reported side by side and never merged.
    api_capable = s.get("has_api") == "Yes"

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "source_id": s.get("source_id"),
            "source_name": s.get("source_name"),
            "source_type": s.get("source_type"),
            "jurisdiction_class": s.get("federal_or_state_or_private"),
            "state_if_applicable": s.get("state_if_applicable"),
            "priority_tier": s.get("priority_tier"),
            "monitoring_method": method,
            "url": s.get("url"),
            # --- statuses, kept apart on purpose -------------------------
            "registry_status": REGISTRY_STATUS,
            "monitoring_status": MONITORING_STATUS,
            "terms_status": terms_status,
            "state_scope_status": s.get("state_scope_status"),
            "eligibility_status": s.get("eligibility_status"),
            "allowability_status": s.get("allowability_status"),
            # --- the flags the gate asks to be exposed -------------------
            "customer_state_filter_required": s.get("state_scope_status")
            == "state_scoped",
            "legal_terms_review_required": legal_terms_review_required,
            "human_review_only": human_review_only,
            # --- capability vs approval ----------------------------------
            "api_capable": api_capable,
            "api_approved": False,
            "feed_capable": s.get("has_rss_or_email") == "Yes",
            "requires_login": requires_login,
            "activation_blocked_reasons": blocked,
            # --- bridge to Gate 76, at its weakest members ---------------
            "gate76_promotion_status": GATE76_PROMOTION_STATUS,
            "gate76_robots_terms_status": GATE76_ROBOTS_TERMS_STATUS,
            "fabricated": False,
        }
    )


def build_registry_seed_set(*, imported: dict[str, Any]) -> dict[str, Any]:
    seeds = [
        build_source_registry_seed(imported_source=s)
        for s in (imported.get("sources") or [])
    ]

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "seed_count": len(seeds),
            "seeds": seeds,
            "monitored_count": 0,
            "api_approved_count": 0,
            "human_review_only_count": sum(1 for s in seeds if s["human_review_only"]),
            "legal_terms_review_required_count": sum(
                1 for s in seeds if s["legal_terms_review_required"]
            ),
            "customer_state_filter_required_count": sum(
                1 for s in seeds if s["customer_state_filter_required"]
            ),
            "monitoring_started": False,
            "live_coverage_claimed": False,
            "source_monitoring_claimed": False,
            "urls_fetched": 0,
            "fabricated": False,
        }
    )


def seed_invariant_failures(seed_set: dict[str, Any]) -> list[str]:
    fails: list[str] = []

    if seed_set.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")
    for constant in (
        "monitoring_started",
        "live_coverage_claimed",
        "source_monitoring_claimed",
    ):
        if seed_set.get(constant) is not False:
            fails.append(f"seed_claimed:{constant}")
    if seed_set.get("monitored_count") != 0:
        fails.append("monitored_count_non_zero")
    if seed_set.get("api_approved_count") != 0:
        fails.append("api_approved_count_non_zero")

    # The bridge must land on real Gate 76 members, and on non-monitoring ones.
    if GATE76_PROMOTION_STATUS not in PROMOTION_STATUSES:
        fails.append("gate76_promotion_status_not_a_registry_member")
    if GATE76_PROMOTION_STATUS in MONITORING_STATUSES:
        fails.append("gate76_bridge_lands_on_a_monitoring_status")
    if GATE76_ROBOTS_TERMS_STATUS not in ROBOTS_TERMS_STATUSES:
        fails.append("gate76_robots_status_not_a_registry_member")

    for seed in seed_set.get("seeds") or []:
        sid = seed.get("source_id")
        if seed.get("monitoring_status") != MONITORING_STATUS:
            fails.append(f"seed_monitoring_started:{sid}")
        if seed.get("registry_status") != REGISTRY_STATUS:
            fails.append(f"seed_registry_status_wrong:{sid}")
        if seed.get("api_approved") is not False:
            fails.append(f"seed_api_approved:{sid}")
        if seed.get("gate76_promotion_status") in MONITORING_STATUSES:
            fails.append(f"seed_promoted_to_monitoring:{sid}")
        # A state-scoped seed that does not require filtering would be visible
        # to every customer.
        if (
            seed.get("state_scope_status") == "state_scoped"
            and not seed.get("customer_state_filter_required")
        ):
            fails.append(f"state_seed_without_filter_requirement:{sid}")
        if seed.get("human_review_only") and not seed.get(
            "legal_terms_review_required"
        ):
            fails.append(f"human_review_only_without_review_flag:{sid}")
        if not seed.get("activation_blocked_reasons"):
            fails.append(f"seed_without_blocked_reasons:{sid}")

    return fails
