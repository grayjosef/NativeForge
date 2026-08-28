"""Tenant beta readiness (Gate 103G).

Whether NativeForge can demo the tenant beta, and whether it can onboard a
paying tenant. Two different questions with two different answers.

## Demo-ready and onboarding-ready are not the same thing

```text
ready_for_demo             can we show the contracts working against fixtures?
ready_for_beta_onboarding  can a real Tribe start using this?
```

The first is true today. The second is not, and the gap is not small: no live
source collection, no email delivery, no customer auth, no customer persistence
path for tenant profiles.

Conflating them is how a working demo becomes a signed contract for something
that does not exist. They are separate fields, separately derived, and an
invariant fails any result where onboarding readiness was reached without every
component behind it.

## Demo readiness is scoped, and the scope is in the name

`ready_for_demo` means **the contract demo against demo-safe fixtures**. It does
not mean a demo of live matching, live digests, or real tenant data, because
none of those exists. The field is reported beside `demo_scope` so the
qualification travels with it.

## Everything detected, nothing declared

Each component is established by importing the service that owns it. A component
can therefore be absent and say so — the digest contract genuinely does not
exist yet, and `digest_contract_available: false` is more useful than a flag
somebody set to true in anticipation of Gate 104.
"""

from __future__ import annotations

import importlib.util
import json
from typing import Any

SCHEMA_VERSION = "nf_tenant_beta_readiness_v1"

# Components that make the contract demo possible.
DEMO_COMPONENT_MODULES: dict[str, str] = {
    "tenant_profiles_available": (
        "nativeforge.services.tenant_beta_profile_service"
    ),
    "tenant_feature_entitlements_available": (
        "nativeforge.services.tenant_beta_feature_entitlement_service"
    ),
    "tenant_source_priority_available": (
        "nativeforge.services.tenant_source_priority_service"
    ),
    "demo_fixtures_available": (
        "nativeforge.services.tenant_beta_demo_fixture_service"
    ),
    "allowability_review_available": (
        "nativeforge.services.software_capacity_allowability_review_service"
    ),
    "awarded_grants_contract_available": (
        "nativeforge.services.awarded_grant_portfolio_service"
    ),
    "reporting_tracking_contract_available": (
        "nativeforge.services.awarded_grant_portfolio_service"
    ),
    # Gate 104. Absent today, and the readiness says so.
    "digest_contract_available": (
        "nativeforge.services.tenant_nofo_digest_service"
    ),
    "pursuit_suppression_contract_available": (
        "nativeforge.services.tenant_pursuit_suppression_service"
    ),
}

# Components an onboarding needs on top of the demo ones. None exists.
ONBOARDING_COMPONENT_KEYS: tuple[str, ...] = (
    "live_source_collection_available",
    "email_delivery_available",
    "customer_auth_live",
    "customer_persistence_live",
)

# The components required for the *contract* demo. `digest_contract_available`
# and `pursuit_suppression_contract_available` are deliberately excluded - they
# are Gate 104's, and the Gate 103 demo shows profiles, entitlement, source
# priority, allowability and the awarded-grants contract.
DEMO_REQUIRED_KEYS: tuple[str, ...] = (
    "tenant_profiles_available",
    "tenant_feature_entitlements_available",
    "tenant_source_priority_available",
    "demo_fixtures_available",
    "allowability_review_available",
    "awarded_grants_contract_available",
)

DEMO_SCOPE = "contract_demo_against_demo_safe_fixtures"

NEXT_ACTION_SEQUENCE: tuple[tuple[str, str], ...] = (
    (
        "build_digest_contract",
        "gate 104 - digest is genuine greenfield; nothing backs it today",
    ),
    (
        "build_pursuit_suppression_contract",
        "gate 104 - tenant-specific, never global, and never a delete",
    ),
    (
        "extend_awarded_grants_requirement_tracking",
        "gate 105 - separate projected burden from active obligations",
    ),
    (
        "prove_customer_persistence_for_tenant_profiles",
        "no tenant profile persists today; NfTribalProfile carries none of the "
        "beta fields",
    ),
    (
        "prove_customer_auth",
        "login is not live; onboarding a paying tenant needs it",
    ),
    (
        "prove_email_delivery",
        "a weekly digest nobody can receive is not a weekly digest",
    ),
    (
        "activate_a_collector_under_the_existing_gates",
        "live source collection is 0; every tenant feature is fixture-backed "
        "until it is not",
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
    """Bridged from Gate 93's policy, which detects each of its own components."""
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


def build_tenant_beta_readiness() -> dict[str, Any]:
    """Can we demo it, and can we onboard on it? Every value detected."""
    components = {
        key: _module_importable(module)
        for key, module in DEMO_COMPONENT_MODULES.items()
    }

    live_source_collection = _detect_live_source_collection()
    # No delivery path, no auth, no tenant-profile persistence. Each is a
    # separate absence and none is inferred from the others.
    email_delivery = _module_importable("nativeforge.services.email_delivery_service")
    customer_auth_live = False
    customer_persistence_live = False

    demo_missing = sorted(key for key in DEMO_REQUIRED_KEYS if not components[key])
    ready_for_demo = not demo_missing

    onboarding_facts = {
        "live_source_collection_available": live_source_collection,
        "email_delivery_available": email_delivery,
        "customer_auth_live": customer_auth_live,
        "customer_persistence_live": customer_persistence_live,
    }
    onboarding_missing = sorted(k for k, v in onboarding_facts.items() if not v)
    ready_for_beta_onboarding = not demo_missing and not onboarding_missing

    blocked_reasons: list[str] = []
    blocked_reasons.extend(f"demo_component_missing:{k}" for k in demo_missing)
    blocked_reasons.extend(f"onboarding_missing:{k}" for k in onboarding_missing)
    for key in ("digest_contract_available", "pursuit_suppression_contract_available"):
        if not components[key]:
            blocked_reasons.append(f"gate_104_component_missing:{key}")

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "tenant_beta_contract_available": ready_for_demo,
            **components,
            **onboarding_facts,
            "ready_for_demo": ready_for_demo,
            "demo_scope": DEMO_SCOPE,
            "ready_for_beta_onboarding": ready_for_beta_onboarding,
            "demo_components_missing": demo_missing,
            "onboarding_components_missing": onboarding_missing,
            "blocked_reasons": sorted(set(blocked_reasons)),
            "next_required_actions": [
                {"action": action, "why": why} for action, why in NEXT_ACTION_SEQUENCE
            ],
            # Boundaries this gate may not soften.
            "source_monitoring_live": False,
            "live_source_coverage": False,
            "collectors_active": 0,
            "production_rollout": False,
            "controlled_customer_pilot": False,
            "fabricated": False,
        }
    )


def readiness_invariant_failures(result: dict[str, Any]) -> list[str]:
    fails: list[str] = []

    if result.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")
    if result.get("fabricated") is not False:
        fails.append("fabricated_must_be_false")

    for constant in (
        "source_monitoring_live",
        "live_source_coverage",
        "production_rollout",
        "controlled_customer_pilot",
    ):
        if result.get(constant) is not False:
            fails.append(f"readiness_claimed:{constant}")
    if result.get("collectors_active") != 0:
        fails.append("readiness_claimed_active_collectors")

    # Demo readiness is derived from its components and scoped by name.
    demo_missing = result.get("demo_components_missing") or []
    if result.get("ready_for_demo") != (not demo_missing):
        fails.append("demo_readiness_disagrees_with_its_components")
    if result.get("ready_for_demo") and result.get("demo_scope") != DEMO_SCOPE:
        fails.append("demo_readiness_without_its_scope")

    # Onboarding readiness needs everything, and each absence is separate.
    onboarding_missing = result.get("onboarding_components_missing") or []
    if result.get("ready_for_beta_onboarding") != (
        not demo_missing and not onboarding_missing
    ):
        fails.append("onboarding_readiness_disagrees_with_its_components")
    if result.get("ready_for_beta_onboarding"):
        for key in ONBOARDING_COMPONENT_KEYS:
            if not result.get(key):
                fails.append(f"onboarding_ready_without:{key}")

    # A demo is never an onboarding.
    if result.get("ready_for_demo") and result.get("ready_for_beta_onboarding"):
        if onboarding_missing:
            fails.append("demo_readiness_read_as_onboarding_readiness")

    # Live collection may never be claimed while collectors are inactive.
    if result.get("live_source_collection_available") and not result.get(
        "collectors_active"
    ):
        fails.append("live_collection_claimed_without_active_collectors")

    # A refusal must name itself.
    if not result.get("ready_for_beta_onboarding") and not result.get(
        "blocked_reasons"
    ):
        fails.append("refusal_without_a_reason")

    actions = [a.get("action") for a in result.get("next_required_actions") or []]
    if actions != [a for a, _ in NEXT_ACTION_SEQUENCE]:
        fails.append("next_required_actions_reordered_or_dropped")

    return fails
