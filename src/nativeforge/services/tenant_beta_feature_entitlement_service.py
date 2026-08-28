"""Tenant beta feature entitlement (Gate 103C).

Which beta features are switched on for a tenant, and what that does and does not
mean.

## Entitlement is permission, not capability

The distinction this service exists to hold:

```text
entitled     this tenant is allowed to use the feature
configured   the tenant has supplied what the feature needs
implemented  the feature exists and works
live         the feature is doing something in the world
```

They are four different facts and a flag in a settings table is only the first.
Turning on `weekly_nofo_digest` does not make a digest arrive; turning on
`sc_federal_source_watchlist` does not check a source; turning on
`awarded_grants_workspace` does not verify a single extracted requirement.

Every entitlement result therefore carries the downstream facts alongside the
flags, and invariants fail any result where an entitlement was read as one of
them:

```text
digest_email_delivery_live     false
source_monitoring_live         false
extracted_requirements_verified false
live_source_coverage           false
```

## Implementation status is detected, not declared

`FEATURE_IMPLEMENTATION` records which services back each feature, and
`detect_feature_implementation` imports them. A feature can therefore be
*entitled* and *not implemented*, which is the true state of several of these
today — the digest has no service at all, and saying so is more useful than a
flag that claims otherwise.

## Configuration required is derived from the profile

A feature that needs tenant facts the profile does not carry is reported as
`configuration_required` rather than enabled-and-broken. `sc_federal_source_
watchlist` needs operating states; `tenant_rules_routing_alerts` needs routing
rules; `optional_daily_alerts` needs an audience.
"""

from __future__ import annotations

import importlib.util
import json
from typing import Any

SCHEMA_VERSION = "nf_tenant_beta_feature_entitlement_v1"

BETA_FEATURES: tuple[str, ...] = (
    "tenant_eligibility_profile",
    "sc_federal_source_watchlist",
    "weekly_nofo_digest",
    "optional_daily_alerts",
    "pursuit_suppression",
    "tenant_pursuit_pipeline",
    "reporting_burden_preview",
    "awarded_grants_workspace",
    "tenant_document_library",
    "tenant_rules_routing_alerts",
    "software_capacity_allowability_review",
)

# Features on by default for a beta tenant. `optional_daily_alerts` is off by
# design - the product requirement makes weekly the default and daily an opt-in
# for grants/admin users.
DEFAULT_ENABLED_FEATURES: frozenset[str] = frozenset(BETA_FEATURES) - {
    "optional_daily_alerts"
}

# Which services back each feature. Detected by import, so a feature cannot
# report itself implemented because somebody set a flag.
FEATURE_IMPLEMENTATION: dict[str, tuple[str, ...]] = {
    "tenant_eligibility_profile": (
        "nativeforge.services.tenant_beta_profile_service",
        "nativeforge.services.eligibility_evidence_contract_service",
    ),
    "sc_federal_source_watchlist": (
        "nativeforge.services.tenant_source_priority_service",
    ),
    # Gate 104. Nothing backs it today, and the entitlement says so.
    "weekly_nofo_digest": (),
    "optional_daily_alerts": (),
    "pursuit_suppression": (),
    "tenant_pursuit_pipeline": ("nativeforge.services.pursuit_brief_service",),
    "reporting_burden_preview": (
        "nativeforge.services.awarded_grant_portfolio_service",
    ),
    "awarded_grants_workspace": (
        "nativeforge.services.awarded_grant_portfolio_service",
    ),
    "tenant_document_library": (
        "nativeforge.services.grant_document_attachment_inventory_service",
    ),
    "tenant_rules_routing_alerts": (
        "nativeforge.services.recognition_routing_contract_service",
    ),
    "software_capacity_allowability_review": (
        "nativeforge.services.software_capacity_allowability_review_service",
    ),
}

# What each feature needs from the tenant profile before it can be configured.
FEATURE_CONFIGURATION_REQUIREMENTS: dict[str, tuple[str, ...]] = {
    "sc_federal_source_watchlist": ("operating_states",),
    "tenant_eligibility_profile": ("recognition_status", "applicant_classes"),
    "optional_daily_alerts": ("daily_alerts_audience",),
    "tenant_rules_routing_alerts": ("routing_rules",),
    "tenant_document_library": ("document_library_requirements",),
}

# Features whose entitlement is most likely to be misread as the thing itself.
MISREADABLE_FEATURES: dict[str, str] = {
    "weekly_nofo_digest": "digest_email_delivery_live",
    "optional_daily_alerts": "digest_email_delivery_live",
    "sc_federal_source_watchlist": "source_monitoring_live",
    "awarded_grants_workspace": "extracted_requirements_verified",
}


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _module_importable(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ValueError):
        return False


def detect_feature_implementation() -> dict[str, Any]:
    """Which features have services behind them. Import, not declaration."""
    implemented: dict[str, bool] = {}
    detail: dict[str, list[str]] = {}
    for feature, modules in FEATURE_IMPLEMENTATION.items():
        found = [m for m in modules if _module_importable(m)]
        detail[feature] = sorted(found)
        # No declared modules means nothing backs it. That is a real answer.
        implemented[feature] = bool(modules) and len(found) == len(modules)
    return _json_safe(
        {
            "implemented": implemented,
            "modules_found": detail,
            "detection_method": "importlib.util.find_spec",
        }
    )


def _profile_supplies(profile: dict[str, Any] | None, requirement: str) -> bool:
    """Whether a profile carries an actionable value for a requirement."""
    if not profile:
        return False
    if requirement == "daily_alerts_audience":
        prefs = profile.get("digest_preferences") or {}
        return prefs.get("daily_alerts_audience") not in (None, "none")
    if requirement in {"routing_rules", "document_library_requirements"}:
        return bool(profile.get(requirement))
    fact = profile.get(requirement)
    if not isinstance(fact, dict):
        return bool(fact)
    # A demo fixture configures a demo. It does not configure a real tenant, but
    # it is not nothing either - it is reported as supplied and the profile's
    # own status carries the caveat.
    return fact.get("value") is not None and fact.get("status") != "unknown"


def build_tenant_feature_entitlement(
    *,
    tenant_id: Any,
    profile: dict[str, Any] | None = None,
    requested_features: list[Any] | None = None,
) -> dict[str, Any]:
    """Which features this tenant may use. Nothing is switched on in the world."""
    detected = detect_feature_implementation()
    implemented = detected["implemented"]

    unrecognised: list[str] = []
    if requested_features is None:
        requested = set(DEFAULT_ENABLED_FEATURES)
    else:
        named = {str(f).strip() for f in requested_features if str(f).strip()}
        requested = named & set(BETA_FEATURES)
        # A feature name this service does not know is reported, not silently
        # dropped and not silently honoured.
        unrecognised = sorted(named - set(BETA_FEATURES))

    enabled: list[str] = []
    disabled: list[str] = []
    configuration_required: list[dict[str, Any]] = []
    blocked_reasons: list[str] = []

    for feature in BETA_FEATURES:
        if feature not in requested:
            disabled.append(feature)
            continue

        missing = [
            requirement
            for requirement in FEATURE_CONFIGURATION_REQUIREMENTS.get(feature, ())
            if not _profile_supplies(profile, requirement)
        ]
        if missing:
            configuration_required.append(
                {"feature": feature, "missing": sorted(missing)}
            )
            blocked_reasons.append(f"configuration_required:{feature}")

        enabled.append(feature)
        if not implemented.get(feature):
            blocked_reasons.append(f"feature_not_implemented:{feature}")

    if unrecognised:
        blocked_reasons.append(f"feature_out_of_vocabulary:{len(unrecognised)}")

    human_review_required = bool(
        profile
        and profile.get("profile_fact_status")
        in {"unknown", "needs_human_review", "demo_fixture"}
    )
    if human_review_required:
        blocked_reasons.append(
            f"profile_fact_status:{(profile or {}).get('profile_fact_status')}"
        )

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "tenant_id": tenant_id,
            "enabled_features": sorted(enabled),
            "disabled_features": sorted(disabled),
            "unrecognised_features": unrecognised,
            "configuration_required": sorted(
                configuration_required, key=lambda c: c["feature"]
            ),
            "feature_implementation": implemented,
            "human_review_required": human_review_required,
            "blocked_reasons": sorted(set(blocked_reasons)),
            # Entitlement is permission. These are the things it is not.
            "digest_email_delivery_live": False,
            "source_monitoring_live": False,
            "extracted_requirements_verified": False,
            "live_source_coverage": False,
            "collectors_active": 0,
            "features_implemented_by_enabling": False,
            "fabricated": False,
        }
    )


def entitlement_invariant_failures(result: dict[str, Any]) -> list[str]:
    fails: list[str] = []

    if result.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")
    if result.get("fabricated") is not False:
        fails.append("fabricated_must_be_false")

    for constant in (
        "digest_email_delivery_live",
        "source_monitoring_live",
        "extracted_requirements_verified",
        "live_source_coverage",
        "features_implemented_by_enabling",
    ):
        if result.get(constant) is not False:
            fails.append(f"entitlement_claimed:{constant}")
    if result.get("collectors_active") != 0:
        fails.append("entitlement_claimed_active_collectors")

    enabled = set(result.get("enabled_features") or [])
    disabled = set(result.get("disabled_features") or [])

    if enabled & disabled:
        fails.append("feature_both_enabled_and_disabled")
    if enabled | disabled != set(BETA_FEATURES):
        fails.append("feature_dropped_from_the_checklist")
    for feature in enabled | disabled:
        if feature not in BETA_FEATURES:
            fails.append(f"feature_out_of_vocabulary:{feature}")

    # Enabling a feature may never assert the downstream fact it is confused
    # with. This is the whole point of the service.
    for feature, downstream in MISREADABLE_FEATURES.items():
        if feature in enabled and result.get(downstream) is not False:
            fails.append(f"{feature}_read_as:{downstream}")

    # An enabled feature with nothing behind it must say so.
    implementation = result.get("feature_implementation") or {}
    for feature in enabled:
        if not implementation.get(feature):
            if f"feature_not_implemented:{feature}" not in (
                result.get("blocked_reasons") or []
            ):
                fails.append(f"unimplemented_feature_not_flagged:{feature}")

    # Configuration gaps must name the feature and what is missing.
    for entry in result.get("configuration_required") or []:
        if entry.get("feature") not in BETA_FEATURES:
            fails.append("configuration_entry_out_of_vocabulary")
        if not entry.get("missing"):
            fails.append(f"configuration_required_without_a_reason:{entry.get('feature')}")

    return fails
