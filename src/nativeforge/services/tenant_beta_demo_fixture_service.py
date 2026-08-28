"""Tenant beta demo fixtures (Gate 103E).

Four demo tenant profiles for the beta, built without inventing facts about any
real Tribe.

## Generic identities, deliberately

```text
nf-demo-tenant-01 … nf-demo-tenant-04
"Demo Tenant One" … "Demo Tenant Four"
```

No real Tribe is named. Not "Catawba", not any of the state-recognised entities
in the SC registry rows, not a lightly-disguised variant. The demo is about the
*product*, and putting a real government's name on a fabricated eligibility
profile is a harm to that government whatever the disclaimer says.

`REAL_TRIBE_NAME_TOKENS` lists what must never appear in a generated fixture, and
an invariant scans every generated name and service area for them. When real
tenant facts are supplied by the operator, `build_supplied_tenant_profile` takes
them with a real status — the fixture path and the real path are different
functions so nobody reaches the fabricating one by accident.

## Every fact is `demo_fixture` or `unknown`

Nothing a fixture produces is `verified` or `tenant_supplied`, and an invariant
enforces it. The four things the demo genuinely needs — a name, an operating
state, a tenant kind, a digest preference — are `demo_fixture`. Everything
consequential is `unknown`:

```text
recognition_status   unknown    never fabricated, for any tenant
applicant_classes    unknown    per-opportunity, not a profile constant
service_area         unknown    a real geography claim about a real people
```

That leaves the demo profiles deliberately incomplete, and the incompleteness is
the point: a demo that shows `recognition_status: unknown` is showing how the
product behaves when it does not know, which is most of the time.

## SC operating state is a fixture value, not a claim

Two of the four fixtures carry `operating_states: ["SC"]` with status
`demo_fixture`, because the beta's priority is South Carolina and the demo has to
show SC prioritisation working. That is a stated fixture, not an assertion that
any particular Tribe operates there.
"""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.tenant_beta_profile_service import (
    FACT_STATUSES,
    TRACKED_FACT_FIELDS,
    build_tenant_beta_profile,
    profile_invariant_failures,
)

SCHEMA_VERSION = "nf_tenant_beta_demo_fixture_v1"

DEMO_TENANT_COUNT = 4

# Statuses a fixture may produce. Never `verified`, never `tenant_supplied`.
FIXTURE_PERMITTED_STATUSES = frozenset({"demo_fixture", "unknown"})

# Names that must never appear in a generated fixture. Real federally and
# state-recognised entities, and the tokens a near-miss would use.
#
# This is a blocklist of things NOT to write, so a guard that scans source text
# for these strings would flag this very declaration - Gate 93 hit exactly that
# and the scanner there had to learn to skip declared blocklists.
REAL_TRIBE_NAME_TOKENS: tuple[str, ...] = (
    "catawba",
    "cherokee",
    "pee dee",
    "santee",
    "edisto",
    "waccamaw",
    "chicora",
    "beaver creek",
    "wassamasaw",
    "natchez",
    "sumter",
    "choctaw",
    "chickasaw",
    "creek",
    "seminole",
    "navajo",
    "lumbee",
)

# The four fixtures. Two in SC so prioritisation is demonstrable, one in another
# state so tenant-specificity is demonstrable, one with no state at all so the
# unknown path is demonstrable.
DEMO_TENANT_SPECS: tuple[dict[str, Any], ...] = (
    {
        "tenant_id": "nf-demo-tenant-01",
        "tenant_name": "Demo Tenant One",
        "tenant_kind": "tribal_government",
        "operating_states": ["SC"],
        "digest_frequency": "weekly",
        "daily_alerts_audience": "grants_admin",
        "awarded_grants_enabled": True,
        "reporting_tracking_enabled": True,
    },
    {
        "tenant_id": "nf-demo-tenant-02",
        "tenant_name": "Demo Tenant Two",
        "tenant_kind": "tribal_government",
        "operating_states": ["SC"],
        "digest_frequency": "weekly",
        "daily_alerts_audience": "none",
        "awarded_grants_enabled": True,
        "reporting_tracking_enabled": True,
    },
    {
        "tenant_id": "nf-demo-tenant-03",
        "tenant_name": "Demo Tenant Three",
        "tenant_kind": "native_nonprofit",
        "operating_states": ["NC"],
        "digest_frequency": "weekly",
        "daily_alerts_audience": "none",
        "awarded_grants_enabled": True,
        "reporting_tracking_enabled": False,
    },
    {
        # No operating state at all. Shows the unknown path, and shows that a
        # tenant without SC does not get SC prioritisation.
        "tenant_id": "nf-demo-tenant-04",
        "tenant_name": "Demo Tenant Four",
        "tenant_kind": "unknown",
        "operating_states": [],
        "digest_frequency": "weekly",
        "daily_alerts_audience": "none",
        "awarded_grants_enabled": False,
        "reporting_tracking_enabled": False,
    },
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _names_a_real_tribe(text: Any) -> bool:
    lowered = str(text or "").lower()
    return any(token in lowered for token in REAL_TRIBE_NAME_TOKENS)


def build_demo_tenant_profile(spec: dict[str, Any]) -> dict[str, Any]:
    """One demo profile. Every supplied fact is `demo_fixture`; the rest unknown.

    Recognition status, applicant classes and service area are deliberately not
    passed - they stay `unknown`, because fabricating them is the specific harm
    this service exists to avoid.
    """
    return build_tenant_beta_profile(
        tenant_id=spec["tenant_id"],
        tenant_name=spec["tenant_name"],
        tenant_name_status="demo_fixture",
        tenant_kind=spec["tenant_kind"],
        tenant_kind_status="demo_fixture" if spec["tenant_kind"] != "unknown" else None,
        # Never fabricated, for any tenant, at any status.
        recognition_status=None,
        applicant_classes=None,
        service_area=None,
        operating_states=spec["operating_states"],
        operating_states_status="demo_fixture" if spec["operating_states"] else None,
        digest_frequency=spec["digest_frequency"],
        daily_alerts_audience=spec["daily_alerts_audience"],
        awarded_grants_enabled=spec["awarded_grants_enabled"],
        reporting_tracking_enabled=spec["reporting_tracking_enabled"],
        human_review_notes=[
            "demo fixture: recognition status, applicant classes and service "
            "area are unknown by design and must be supplied by the tenant "
            "before any eligibility decision",
        ],
    )


def build_supplied_tenant_profile(**kwargs: Any) -> dict[str, Any]:
    """The real path, kept separate from the fixture path.

    A caller with actual tenant facts uses this and supplies real statuses.
    Separating the two functions means nobody reaches the fabricating one by
    passing a flag.
    """
    return build_tenant_beta_profile(**kwargs)


def build_demo_tenant_fixture_set() -> dict[str, Any]:
    """All four demo tenants. Deterministic, and nothing real is named."""
    profiles = [build_demo_tenant_profile(spec) for spec in DEMO_TENANT_SPECS]

    verified = 0
    unknown = 0
    demo_fixture = 0
    for profile in profiles:
        for field in TRACKED_FACT_FIELDS:
            fact = profile.get(field) or {}
            status = fact.get("status")
            if status == "verified":
                verified += 1
            elif status == "demo_fixture":
                demo_fixture += 1
            elif status in {"unknown", "needs_human_review"}:
                unknown += 1

    blocked_reasons: list[str] = [
        "demo_fixture_profiles_are_not_tenant_facts",
        "recognition_status_unknown_for_every_demo_tenant",
        "applicant_classes_unknown_for_every_demo_tenant",
    ]
    named = [
        p["tenant_id"]
        for p in profiles
        if _names_a_real_tribe((p.get("tenant_name") or {}).get("value"))
    ]
    if named:
        blocked_reasons.append(f"fixture_named_a_real_tribe:{len(named)}")

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "tenant_profiles": profiles,
            "tenant_count": len(profiles),
            "fixture_status": "demo_fixture",
            "facts_verified_count": verified,
            "facts_unknown_count": unknown,
            "facts_demo_fixture_count": demo_fixture,
            "sc_priority_count": sum(1 for p in profiles if p.get("sc_priority")),
            "real_tribe_named": bool(named),
            "blocked_reasons": sorted(set(blocked_reasons)),
            # A fixture is not a tenant, and not coverage.
            "tenant_facts_verified": False,
            "eligibility_determined": False,
            "source_monitoring_live": False,
            "live_source_coverage": False,
            "fabricated": False,
        }
    )


def demo_fixture_invariant_failures(result: dict[str, Any]) -> list[str]:
    fails: list[str] = []

    if result.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")
    if result.get("fabricated") is not False:
        fails.append("fabricated_must_be_false")

    for constant in (
        "tenant_facts_verified",
        "eligibility_determined",
        "source_monitoring_live",
        "live_source_coverage",
        "real_tribe_named",
    ):
        if result.get(constant) is not False:
            fails.append(f"fixture_claimed:{constant}")

    if result.get("fixture_status") != "demo_fixture":
        fails.append("fixture_set_not_marked_demo_fixture")

    profiles = result.get("tenant_profiles")
    if not isinstance(profiles, list):
        fails.append("tenant_profiles_not_a_list")
        return fails
    if len(profiles) != DEMO_TENANT_COUNT:
        fails.append(f"expected_{DEMO_TENANT_COUNT}_demo_tenants")

    for profile in profiles:
        tenant_id = profile.get("tenant_id")

        # Each profile must still satisfy the profile contract.
        for failure in profile_invariant_failures(profile):
            fails.append(f"profile_invariant:{tenant_id}:{failure}")

        # A fixture may never produce a verified or tenant-supplied fact.
        for field in TRACKED_FACT_FIELDS:
            fact = profile.get(field) or {}
            status = fact.get("status")
            if status not in FACT_STATUSES:
                fails.append(f"fact_status_out_of_vocabulary:{tenant_id}:{field}")
            elif status not in FIXTURE_PERMITTED_STATUSES | {"needs_human_review"}:
                fails.append(f"fixture_claimed_a_real_fact:{tenant_id}:{field}")

        # The three that are never fabricated, for any tenant.
        for field in ("recognition_status", "applicant_classes", "service_area"):
            fact = profile.get(field) or {}
            if fact.get("value") is not None:
                fails.append(f"fixture_fabricated:{tenant_id}:{field}")

        # No real Tribe may be named, anywhere a name could hide.
        for field in ("tenant_name", "service_area"):
            fact = profile.get(field) or {}
            if _names_a_real_tribe(fact.get("value")):
                fails.append(f"fixture_named_a_real_tribe:{tenant_id}:{field}")
        if _names_a_real_tribe(tenant_id):
            fails.append(f"fixture_id_named_a_real_tribe:{tenant_id}")

    # Counts derived from the profiles, never asserted beside them.
    if result.get("tenant_count") != len(profiles):
        fails.append("tenant_count_disagrees_with_the_profiles")
    if result.get("facts_verified_count"):
        fails.append("fixture_reported_a_verified_fact")
    if result.get("sc_priority_count") != sum(
        1 for p in profiles if p.get("sc_priority")
    ):
        fails.append("sc_priority_count_disagrees_with_the_profiles")

    if not result.get("blocked_reasons"):
        fails.append("fixture_set_without_a_caveat")

    return fails
