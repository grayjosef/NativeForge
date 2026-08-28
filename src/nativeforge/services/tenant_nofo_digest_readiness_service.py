"""Tenant NOFO digest readiness (Gate 104G).

Whether NativeForge can preview a tenant digest, and whether it can operate one.
Two different questions with two different answers.

## Preview-ready and operational are not the same thing

```text
ready_for_demo_preview       can we show a digest built from fixtures?
ready_for_operational_digest can a real Tribe receive one on a Monday?
```

The first is true after this gate. The second is not, and four things are
missing: email delivery, live source collection, source monitoring, and customer
persistence.

An operational digest is a promise about something arriving. A preview is a
screen. Conflating them is how "the digest works" becomes a commitment nobody can
keep on the first Monday.

## Every component detected by import

A component can be absent and say so. Nothing here anticipates Gate 105 or 106,
and `email_delivery_service` genuinely does not exist — Gate 103 found zero email
services, Gate 104A confirmed it, and this reports it rather than assuming
somebody will add one.
"""

from __future__ import annotations

import importlib.util
import json
from typing import Any

SCHEMA_VERSION = "nf_tenant_nofo_digest_readiness_v1"

# What the preview needs.
PREVIEW_COMPONENT_MODULES: dict[str, str] = {
    "snapshot_contract_available": (
        "nativeforge.services.tenant_nofo_digest_snapshot_service"
    ),
    "change_detection_available": (
        "nativeforge.services.tenant_nofo_digest_change_detection_service"
    ),
    "explanation_service_available": (
        "nativeforge.services.tenant_nofo_digest_item_explanation_service"
    ),
    "suppression_contract_available": (
        "nativeforge.services.tenant_pursuit_suppression_service"
    ),
    "digest_contract_available": (
        "nativeforge.services.tenant_nofo_digest_builder_service"
    ),
    "demo_fixtures_available": (
        "nativeforge.services.tenant_nofo_digest_demo_fixture_service"
    ),
}

# What an operational digest needs on top. None exists.
OPERATIONAL_COMPONENT_KEYS: tuple[str, ...] = (
    "email_delivery_available",
    "live_source_collection_available",
    "customer_persistence_live",
)

DEMO_SCOPE = "digest_preview_from_labelled_fixture_snapshots"

NEXT_ACTION_SEQUENCE: tuple[tuple[str, str], ...] = (
    (
        "build_email_delivery",
        "no email service exists; a weekly digest nobody receives is not a "
        "weekly digest",
    ),
    (
        "persist_tenant_digests",
        "no digest table exists; a digest that cannot be re-read cannot be "
        "audited after a missed deadline",
    ),
    (
        "activate_a_collector_under_the_existing_gates",
        "change detection compares two recorded snapshots today; a live "
        "comparison needs a second real observation",
    ),
    (
        "settle_the_pursuit_pipeline_vocabulary",
        "three vocabularies disagree - PursuitWorkflowStatus, "
        "pursuit_workspace_contract, and doc 570's seven stages",
    ),
    (
        "extend_awarded_grants_requirement_tracking",
        "gate 105 - separate projected burden from active obligations",
    ),
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _module_importable(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ValueError):
        return False


def _detect_live_source_collection() -> bool:
    """Bridged from Gate 93's policy, which detects its own components."""
    try:
        from nativeforge.services.phase1_collector_activation_policy_service import (
            build_phase1_activation_matrix,
            default_phase1_preflights,
        )
    except ImportError:
        return False
    matrix = build_phase1_activation_matrix(
        preflight_by_source=default_phase1_preflights()
    )
    return bool(matrix.get("collectors_active")) or bool(
        matrix.get("sources_may_fetch_live_now")
    )


def _detect_source_monitoring() -> bool:
    """Bridged from Gate 98E."""
    try:
        from nativeforge.services.source_scheduler_readiness_service import (
            build_scheduler_readiness,
        )
    except ImportError:
        return False
    return bool(build_scheduler_readiness().get("source_monitoring_live"))


def build_digest_readiness() -> dict[str, Any]:
    """Can we preview a digest, and can we operate one? Everything detected."""
    components = {
        key: _module_importable(module)
        for key, module in PREVIEW_COMPONENT_MODULES.items()
    }

    email_delivery = _module_importable(
        "nativeforge.services.email_delivery_service"
    )
    live_collection = _detect_live_source_collection()
    monitoring = _detect_source_monitoring()
    customer_persistence = False

    preview_missing = sorted(k for k, v in components.items() if not v)
    ready_for_demo_preview = not preview_missing

    operational_facts = {
        "email_delivery_available": email_delivery,
        "live_source_collection_available": live_collection,
        "customer_persistence_live": customer_persistence,
    }
    operational_missing = sorted(k for k, v in operational_facts.items() if not v)
    ready_for_operational_digest = not preview_missing and not operational_missing

    blocked_reasons = [f"preview_component_missing:{k}" for k in preview_missing]
    blocked_reasons.extend(f"operational_missing:{k}" for k in operational_missing)
    if not monitoring:
        blocked_reasons.append("source_monitoring_not_live")

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            **components,
            **operational_facts,
            "weekly_digest_preview_available": ready_for_demo_preview,
            # Daily previews from the same machinery; the opt-in is per tenant
            # and lives on the profile, not here.
            "daily_alerts_preview_available": ready_for_demo_preview,
            "source_monitoring_live": monitoring,
            "ready_for_demo_preview": ready_for_demo_preview,
            "demo_scope": DEMO_SCOPE,
            "ready_for_operational_digest": ready_for_operational_digest,
            "preview_components_missing": preview_missing,
            "operational_components_missing": operational_missing,
            "blocked_reasons": sorted(set(blocked_reasons)),
            "next_required_actions": [
                {"action": action, "why": why} for action, why in NEXT_ACTION_SEQUENCE
            ],
            # Boundaries this gate may not soften.
            "live_source_coverage": False,
            "emails_sent": 0,
            "collectors_active": 0,
            "fabricated": False,
        }
    )


def digest_readiness_invariant_failures(result: dict[str, Any]) -> list[str]:
    fails: list[str] = []

    if result.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")
    if result.get("fabricated") is not False:
        fails.append("fabricated_must_be_false")

    if result.get("live_source_coverage") is not False:
        fails.append("readiness_claimed:live_source_coverage")
    if result.get("emails_sent") != 0:
        fails.append("readiness_sent_email")
    if result.get("collectors_active") != 0:
        fails.append("readiness_claimed_active_collectors")

    preview_missing = result.get("preview_components_missing") or []
    if result.get("ready_for_demo_preview") != (not preview_missing):
        fails.append("preview_readiness_disagrees_with_its_components")
    if result.get("ready_for_demo_preview") and result.get("demo_scope") != DEMO_SCOPE:
        fails.append("preview_readiness_without_its_scope")

    operational_missing = result.get("operational_components_missing") or []
    if result.get("ready_for_operational_digest") != (
        not preview_missing and not operational_missing
    ):
        fails.append("operational_readiness_disagrees_with_its_components")
    if result.get("ready_for_operational_digest"):
        for key in OPERATIONAL_COMPONENT_KEYS:
            if not result.get(key):
                fails.append(f"operational_ready_without:{key}")

    # A preview is never an operational digest.
    if result.get("ready_for_demo_preview") and result.get(
        "ready_for_operational_digest"
    ):
        if operational_missing:
            fails.append("preview_readiness_read_as_operational")

    if result.get("live_source_collection_available") and not result.get(
        "collectors_active"
    ):
        fails.append("live_collection_claimed_without_active_collectors")

    if not result.get("ready_for_operational_digest") and not result.get(
        "blocked_reasons"
    ):
        fails.append("refusal_without_a_reason")

    actions = [a.get("action") for a in result.get("next_required_actions") or []]
    if actions != [a for a, _ in NEXT_ACTION_SEQUENCE]:
        fails.append("next_required_actions_reordered_or_dropped")

    return fails
