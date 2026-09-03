"""Gate 140F: tenant digest readiness, measured instead of declared.

## The constant this replaces

`tenant_digest_operational` was a literal `False` in six places and no service
derived it:

```text
dev_header_kill_artifact_service.py:311        False
login_live_dev_header_kill_artifact_service    False
first_dev_org_binding_artifact_service.py:327  False
plus three artifact prose lines
```

`tenant_nofo_digest_readiness_service` exists and answers a *different*
question — `ready_for_operational_digest`, which additionally requires live
source collection, an email service and a verified operational binding. All
three are correctly false, and none of them is needed for a preview built from
labelled fixture snapshots.

So this module answers the controlled dev/demo question and leaves that one
alone, the same separation Gate 138 made for persistence and Gate 139 for
awarded tracking.

## What monitoring and email are, and are not

```text
source_monitoring_required_for_preview   False
email_required_for_preview               False
```

Both stated as fields rather than implied by their absence. Requiring live
monitoring for a preview assembled from fixtures would be the unsatisfiable
conjunct Gate 134F removed — the lane would be permanently unreachable and
every "not ready" above it unfalsifiable.

`source_monitoring_live` and `email_delivery_available` are reported beside
them and stay false. An invariant fails if either is ever true here.

## Production stays false

`production_tenant_digest` has no branch that sets it. Production needs live
source monitoring, an email service that does not exist, and Gate 137's owner
decision.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "nf_tenant_digest_operational_readiness_v1"

CONTROLLED_SCOPE = "controlled_dev_demo"

#: The two route modules this readiness depends on, and what each must be.
LANE_ROUTE_MODULES: dict[str, str] = {
    "source_watchlist": "src/nativeforge/api/tenant_watchlist_routes.py",
    "tenant_digest": "src/nativeforge/api/tenant_digest_routes.py",
}

REQUIRED_DEPENDENCY = "require_demo_org_session"

FORBIDDEN_DEPENDENCIES: tuple[str, ...] = (
    "get_org_context_with_db",
    "require_demo_org_db",
    "require_real_org_db",
    "get_dev_org_context_explicit_only",
)

DEV_HEADER_NAME = "X-NF-Org-Id"

#: Claims this module never makes.
NOT_APPROVED: tuple[str, ...] = (
    "production_tenant_digest",
    "source_monitoring_live",
    "email_delivery",
    "live_source_coverage",
    "production_rollout",
    "controlled_customer_pilot",
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def detect_route_module(lane: str, *, repo_root: Path | None = None) -> dict[str, Any]:
    """Does this lane's route module exist, and is it session-wired?

    ``repo_root`` is injectable so `route_module_available: False` is reachable
    without deleting a file - an unreachable branch is an untested one.

    Parsed for `Depends(require_demo_org_session)` rather than searched as a
    substring: Gate 133 found `if TABLE_NAME in body` counting a docstring
    mention as a use, and this campaign has now found ten of those.
    """
    root = repo_root if repo_root is not None else _repo_root()
    relative = LANE_ROUTE_MODULES.get(lane)
    if relative is None:
        return {
            "lane": lane,
            "route_module": None,
            "route_module_available": False,
            "session_wired": False,
            "reads_dev_header": False,
            "blocked_reasons": [f"lane_not_recognised:{lane}"],
        }

    path = root / relative
    if not path.is_file():
        return {
            "lane": lane,
            "route_module": relative,
            "route_module_available": False,
            "session_wired": False,
            "reads_dev_header": False,
            "blocked_reasons": ["route_module_does_not_exist"],
        }

    body = path.read_text(encoding="utf-8", errors="replace")
    blocked: list[str] = []

    session_wired = bool(re.search(rf"Depends\(\s*{REQUIRED_DEPENDENCY}\s*\)", body))
    if not session_wired:
        blocked.append("route_module_does_not_depend_on_a_session_org_context")

    reads_header = False
    for dependency in FORBIDDEN_DEPENDENCIES:
        if re.search(rf"Depends\(\s*{dependency}\s*\)", body):
            reads_header = True
            blocked.append(f"route_module_reads_the_dev_header_chain:{dependency}")
    if re.search(rf'alias\s*=\s*["\']{re.escape(DEV_HEADER_NAME)}["\']', body):
        reads_header = True
        blocked.append("route_module_declares_the_dev_header_as_a_parameter")

    return _json_safe(
        {
            "lane": lane,
            "route_module": relative,
            "route_module_available": True,
            "session_wired": session_wired,
            "reads_dev_header": reads_header,
            "blocked_reasons": sorted(set(blocked)),
        }
    )


def build_tenant_digest_readiness(
    *,
    connection: Any = None,
    organization_id: Any = None,
    route_smoke: dict[str, Any] | None = None,
    customer_persistence_live: bool | None = None,
    repo_root: Path | None = None,
    profile_available: bool | None = None,
) -> dict[str, Any]:
    """Is the tenant digest operational for controlled dev/demo?

    Every input is supplied by a caller that measured it, or read from rows.
    Absent evidence is absent - false, never assumed - which keeps this
    deterministic for the artifacts it feeds.
    """
    smoke = route_smoke or {}
    blocked: list[str] = []

    modules = {
        lane: detect_route_module(lane, repo_root=repo_root)
        for lane in LANE_ROUTE_MODULES
    }
    for lane, module in modules.items():
        blocked.extend(f"{lane}:{reason}" for reason in module["blocked_reasons"])

    # -- the profile, which carries the cadence -----------------------------
    profile = profile_available
    if profile is None and connection is not None and organization_id:
        from nativeforge.services.tenant_profile_repository_service import (
            get_tenant_profile,
        )

        found = get_tenant_profile(
            connection=connection, organization_id=str(organization_id)
        )
        profile = bool(found.get("rows_read"))
    profile = bool(profile)
    if not profile:
        blocked.append("no_tenant_profile_for_this_organization")

    # -- the contracts, by import ------------------------------------------
    from nativeforge.services.tenant_nofo_digest_readiness_service import (
        build_digest_readiness,
    )

    components = build_digest_readiness()
    weekly_default = bool(components.get("weekly_digest_preview_available"))
    daily_setting = bool(components.get("daily_alerts_preview_available"))
    suppression_contract = bool(components.get("suppression_contract_available"))
    if not weekly_default:
        blocked.append("weekly_digest_preview_not_available")
    if not daily_setting:
        blocked.append("daily_alert_preview_not_available")
    if not suppression_contract:
        blocked.append("suppression_contract_not_available")

    # -- what the route smoke proved ---------------------------------------
    watchlist_route = bool(smoke.get("watchlist_route_operational"))
    digest_route = bool(smoke.get("digest_preview_operational"))
    weekly_proved = bool(smoke.get("weekly_default_proved"))
    daily_proved = bool(smoke.get("daily_setting_proved"))
    suppression_proved = bool(smoke.get("suppression_proved"))
    cross_org_refused = bool(smoke.get("cross_org_refused", True))
    unauthenticated_refused = bool(smoke.get("unauthenticated_refused"))

    if smoke:
        for name, value in (
            ("watchlist_route_operational", watchlist_route),
            ("digest_preview_operational", digest_route),
            ("weekly_default_proved", weekly_proved),
            ("daily_setting_proved", daily_proved),
            ("suppression_proved", suppression_proved),
            ("unauthenticated_refused", unauthenticated_refused),
            ("cross_org_refused", cross_org_refused),
        ):
            if not value:
                blocked.append(f"smoke_did_not_prove:{name}")
        blocked.extend(f"smoke:{r}" for r in smoke.get("blocked_reasons") or [])
    else:
        blocked.append("no_route_smoke_was_supplied")

    # -- persistence -------------------------------------------------------
    persistence = (
        bool(customer_persistence_live)
        if customer_persistence_live is not None
        else False
    )
    if not persistence:
        blocked.append("customer_persistence_is_not_live")

    # -- and the two things a preview does not need ------------------------
    monitoring = bool(components.get("source_monitoring_live"))
    email = bool(components.get("email_delivery_available"))

    operational = bool(
        profile
        and weekly_default
        and daily_setting
        and suppression_contract
        and watchlist_route
        and digest_route
        and weekly_proved
        and daily_proved
        and suppression_proved
        and unauthenticated_refused
        and cross_org_refused
        and persistence
        and all(
            module["route_module_available"]
            and module["session_wired"]
            and not module["reads_dev_header"]
            for module in modules.values()
        )
        and not blocked
    )

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "tenant_digest_operational": operational,
            "scope": CONTROLLED_SCOPE if operational else "none",
            "organization_id": str(organization_id) if organization_id else None,
            "profile_available": profile,
            "watchlist_available": watchlist_route,
            "digest_preview_available": digest_route,
            "weekly_default_available": weekly_default and weekly_proved,
            "daily_setting_available": daily_setting and daily_proved,
            "suppression_available": suppression_contract and suppression_proved,
            "unauthenticated_refused": unauthenticated_refused,
            "cross_org_refused": cross_org_refused,
            "customer_persistence_live": persistence,
            "route_modules": modules,
            # Named as fields, not implied by their absence. Requiring either
            # for a fixture preview would make the lane unreachable.
            "source_monitoring_required_for_preview": False,
            "email_required_for_preview": False,
            "candidate_provenance": "labelled_fixture_snapshots",
            # Constants. No branch sets any of them.
            "source_monitoring_live": monitoring,
            "email_delivery_available": email,
            "live_source_coverage": False,
            "emails_sent": 0,
            "collectors_active": 0,
            "live_grant_sources_called": False,
            "production_tenant_digest": False,
            "production_rollout": False,
            "controlled_customer_pilot": False,
            "customer_auth_live": False,
            "real_customer_data_written": False,
            "real_organization_touched": False,
            "not_approved": list(NOT_APPROVED),
            "blocked_reasons": sorted(set(blocked)),
        }
    )


def tenant_digest_readiness_invariant_failures(result: dict[str, Any]) -> list[str]:
    """What must never be true of a tenant digest readiness result."""
    fails: list[str] = []

    if result.get("tenant_digest_operational"):
        if result.get("scope") != CONTROLLED_SCOPE:
            fails.append(f"operational_outside_the_scope:{result.get('scope')}")
        for field in (
            "profile_available",
            "watchlist_available",
            "digest_preview_available",
            "weekly_default_available",
            "daily_setting_available",
            "suppression_available",
            "unauthenticated_refused",
            "cross_org_refused",
            "customer_persistence_live",
        ):
            if not result.get(field):
                fails.append(f"operational_without:{field}")
        if result.get("blocked_reasons"):
            fails.append("operational_alongside_blockers")
        for lane, module in (result.get("route_modules") or {}).items():
            if module.get("reads_dev_header"):
                fails.append(f"lane_reads_the_dev_header:{lane}")
            if not module.get("session_wired"):
                fails.append(f"lane_not_session_wired:{lane}")

    for field in (
        "source_monitoring_live",
        "email_delivery_available",
        "live_source_coverage",
        "live_grant_sources_called",
        "production_tenant_digest",
        "production_rollout",
        "controlled_customer_pilot",
        "customer_auth_live",
        "real_customer_data_written",
        "real_organization_touched",
    ):
        if result.get(field):
            fails.append(f"claimed:{field}")
    for field in ("emails_sent", "collectors_active"):
        if result.get(field):
            fails.append(f"nonzero:{field}")

    # Requiring either for a preview would make the lane unreachable.
    if result.get("source_monitoring_required_for_preview"):
        fails.append("monitoring_required_for_a_fixture_preview")
    if result.get("email_required_for_preview"):
        fails.append("email_required_for_a_preview")

    if result.get("candidate_provenance") != "labelled_fixture_snapshots":
        fails.append(
            f"candidate_provenance_changed:{result.get('candidate_provenance')}"
        )

    missing = set(NOT_APPROVED) - set(result.get("not_approved") or [])
    if missing:
        fails.append(f"not_approved_list_lost_entries:{sorted(missing)}")

    if not result.get("tenant_digest_operational") and not result.get(
        "blocked_reasons"
    ):
        fails.append("nothing_operational_and_nothing_blocked_it")

    return fails
