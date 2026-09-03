"""Gate 139F: awarded operational tracking, measured instead of declared.

## The constant this replaces

`awarded_operational_tracking` was a literal `False` in nine places and no
service derived it:

```text
dev_header_kill_artifact_service.py:310        False
login_live_dev_header_kill_artifact_service    False
first_dev_org_binding_artifact_service.py:326  False
customer_auth_activation_gate_service          False   (Gate 138F)
award_requirement_proof_audit_persistence_…    False
```

All correct today, and all of which would keep saying `False` after the thing
became real. Same family Gate 114A removed for `customer_persistence_live`:
a fact stated several ways, every one a constant.

## Four lanes, and repository-live is not route-live

```text
awarded grants          repository + route
award requirements      repository + route
proof / audit           repository + route
document metadata       repository + route, metadata only
```

Each lane reports both, separately. Gate 138 established why: a lane that
round-trips at the repository and has no route is not something a customer can
use, and averaging the two into one word is how "operational" comes to mean
nothing.

## What the document lane does not need

Object storage. `object_store_configured` is false, the schema refuses an
`object_key` while it is, and a document row is a reference. Requiring a store
for **metadata** readiness would make the lane permanently unreachable — the
unsatisfiable-conjunct shape Gate 134F removed — so metadata readiness does not
ask for it, and body readiness is reported separately and stays false.

## Production stays false

`awarded_operational_tracking` here is `controlled_dev_demo`. Production
tracking additionally needs `customer_auth_live` and a verified operational
binding, both false, and there is no branch in this module that sets it true.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "nf_awarded_operational_tracking_readiness_v1"

CONTROLLED_SCOPE = "controlled_dev_demo"

#: The four post-award lanes, and the route module each one needs.
LANE_ROUTE_MODULES: dict[str, str] = {
    "awarded_grants": "src/nativeforge/api/awarded_grants_routes.py",
    "award_requirements": "src/nativeforge/api/award_requirements_routes.py",
    "proof_audit": "src/nativeforge/api/award_requirement_proof_routes.py",
    "document_metadata": "src/nativeforge/api/award_document_routes.py",
}

#: The capability lane each maps to, so this surface and Gate 138's can be
#: compared without a mapping living in a reader's head.
LANE_CAPABILITIES: dict[str, str] = {
    "awarded_grants": "awarded_grants_persistence",
    "award_requirements": "award_requirements_persistence",
    "proof_audit": "proof_audit_persistence",
    "document_metadata": "document_library_persistence",
}

#: What a post-award route module must depend on. Detected by parsing, not by
#: substring: Gate 133 found `if TABLE_NAME in body` counting a docstring
#: mention as a use, and this campaign has now found ten of those.
REQUIRED_DEPENDENCY = "require_demo_org_session"

#: And what it must never read.
FORBIDDEN_DEPENDENCIES: tuple[str, ...] = (
    "get_org_context_with_db",
    "require_demo_org_db",
    "require_real_org_db",
    "get_dev_org_context_explicit_only",
)

DEV_HEADER_NAME = "X-NF-Org-Id"

#: Claims this module never makes.
NOT_APPROVED: tuple[str, ...] = (
    "production_awarded_tracking",
    "production_rollout",
    "controlled_customer_pilot",
    "object_store_configured",
    "document_body_storage",
    "live_source_monitoring",
    "email_delivery",
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def detect_route_module(lane: str, *, repo_root: Path | None = None) -> dict[str, Any]:
    """Does this lane's route module exist, and is it session-wired?

    ``repo_root`` is injectable so the negative branch is reachable without
    deleting a file - otherwise `route_module_available: False` would be
    unreachable for every lane and an unreachable branch is an untested one.
    """
    root = repo_root if repo_root is not None else _repo_root()
    relative = LANE_ROUTE_MODULES.get(lane)
    if relative is None:
        return {
            "lane": lane,
            "route_module": None,
            "route_module_available": False,
            "blocked_reasons": [f"lane_not_recognised:{lane}"],
        }

    path = root / relative
    blocked: list[str] = []
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

    # Wired as a FastAPI dependency, not merely mentioned. `Depends(name)` is
    # what actually attaches it to a route.
    session_wired = bool(re.search(rf"Depends\(\s*{REQUIRED_DEPENDENCY}\s*\)", body))
    if not session_wired:
        blocked.append("route_module_does_not_depend_on_a_session_org_context")

    reads_header = False
    for dependency in FORBIDDEN_DEPENDENCIES:
        if re.search(rf"Depends\(\s*{dependency}\s*\)", body):
            reads_header = True
            blocked.append(f"route_module_reads_the_dev_header_chain:{dependency}")

    # The header name may appear in prose - `post_award_common` explains why it
    # is not a parameter - but never as one.
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


def build_lane_readiness(
    lane: str,
    *,
    route_smoke: dict[str, Any] | None = None,
    repository_proof: dict[str, Any] | None = None,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    """One lane: does it have a route, does the route work, does the repo work?

    Both proofs are supplied by a caller that measured them. Absent evidence is
    absent - false, never assumed - which keeps this deterministic for the
    artifacts it feeds.
    """
    module = detect_route_module(lane, repo_root=repo_root)
    smoke = route_smoke or {}
    repository = repository_proof or {}

    blocked: list[str] = list(module["blocked_reasons"])

    route_ok = bool(smoke.get("route_operational"))
    if not route_ok:
        blocked.append("route_smoke_did_not_prove_this_lane")
        blocked.extend(f"route:{r}" for r in smoke.get("blocked_reasons") or [])

    # Gate 138's round trip, per lane.
    capability = LANE_CAPABILITIES[lane]
    repository_ok = capability in set(
        repository.get("repository_persistence_live_lanes") or []
    )
    if not repository_ok:
        blocked.append("repository_round_trip_did_not_prove_this_lane")

    unauthenticated_fails_closed = bool(smoke.get("unauthenticated_refused"))
    if smoke and not unauthenticated_fails_closed:
        blocked.append("route_did_not_refuse_an_unauthenticated_caller")

    cross_org_refused = bool(smoke.get("cross_org_refused", True))
    if not cross_org_refused:
        blocked.append("route_did_not_refuse_a_cross_organization_read")

    operational = bool(
        module["route_module_available"]
        and module["session_wired"]
        and not module["reads_dev_header"]
        and route_ok
        and repository_ok
        and unauthenticated_fails_closed
        and cross_org_refused
        and not blocked
    )

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "lane": lane,
            "capability": capability,
            "route_module": module["route_module"],
            "route_module_available": module["route_module_available"],
            "route_session_wired": module.get("session_wired", False),
            "route_reads_dev_header": module.get("reads_dev_header", False),
            "route_live": route_ok,
            "repository_live": repository_ok,
            "unauthenticated_refused": unauthenticated_fails_closed,
            "cross_org_refused": cross_org_refused,
            "operational": operational,
            "scope": CONTROLLED_SCOPE if operational else "none",
            "blocked_reasons": sorted(set(blocked)),
        }
    )


def build_awarded_operational_readiness(
    *,
    route_smoke: dict[str, Any] | None = None,
    repository_proof: dict[str, Any] | None = None,
    customer_persistence_live: bool | None = None,
    object_store_configured: bool | None = None,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    """Every lane, and the roll-up nobody may shorten to one word."""
    smoke = route_smoke or {}
    lanes = [
        build_lane_readiness(
            lane,
            route_smoke=(smoke.get("lanes") or {}).get(lane),
            repository_proof=repository_proof,
            repo_root=repo_root,
        )
        for lane in LANE_ROUTE_MODULES
    ]

    persistence_live = (
        bool((repository_proof or {}).get("customer_persistence_live"))
        if customer_persistence_live is None
        else bool(customer_persistence_live)
    )

    if object_store_configured is None:
        from nativeforge.services.award_document_store_repository_service import (
            detect_object_store_configured,
        )

        store_configured = bool(detect_object_store_configured())
    else:
        store_configured = bool(object_store_configured)

    blocked: list[str] = []
    if not persistence_live:
        blocked.append("customer_persistence_is_not_live")
    for lane in lanes:
        if not lane["operational"]:
            blocked.append(f"lane_not_operational:{lane['lane']}")

    end_to_end = bool(smoke.get("end_to_end_proved"))
    if smoke and not end_to_end:
        blocked.append("the_end_to_end_post_award_smoke_did_not_pass")

    tracking = bool(
        persistence_live
        and lanes
        and all(lane["operational"] for lane in lanes)
        and end_to_end
        and not blocked
    )

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "awarded_operational_tracking": tracking,
            "scope": CONTROLLED_SCOPE if tracking else "none",
            "customer_persistence_live": persistence_live,
            "end_to_end_proved": end_to_end,
            "lanes": lanes,
            "route_live_lanes": sorted(
                lane["lane"] for lane in lanes if lane["route_live"]
            ),
            "repository_live_lanes": sorted(
                lane["lane"] for lane in lanes if lane["repository_live"]
            ),
            "blocked_lanes": sorted(
                lane["lane"] for lane in lanes if not lane["operational"]
            ),
            # Metadata readiness does not ask for a store, and body readiness
            # is reported separately rather than folded in.
            "object_store_configured": store_configured,
            "document_metadata_readiness_requires_object_store": False,
            "document_body_storage_ready": False,
            # Constants. No branch sets any of them.
            "production_awarded_tracking": False,
            "production_rollout": False,
            "controlled_customer_pilot": False,
            "customer_auth_live": False,
            "verified_operational_binding": False,
            "real_customer_data_written": False,
            "real_organization_touched": False,
            "object_store_contacted": False,
            "live_grant_sources_called": False,
            "collectors_activated": False,
            "email_sent": False,
            "not_approved": list(NOT_APPROVED),
            "blocked_reasons": sorted(set(blocked)),
        }
    )


def awarded_readiness_invariant_failures(result: dict[str, Any]) -> list[str]:
    """What must never be true of an awarded-tracking readiness result."""
    fails: list[str] = []

    if result.get("awarded_operational_tracking"):
        if result.get("scope") != CONTROLLED_SCOPE:
            fails.append(f"tracking_outside_the_scope:{result.get('scope')}")
        if not result.get("customer_persistence_live"):
            fails.append("tracking_without_live_customer_persistence")
        if not result.get("end_to_end_proved"):
            fails.append("tracking_without_an_end_to_end_proof")
        if result.get("blocked_lanes"):
            fails.append("tracking_with_a_blocked_lane")
        if result.get("blocked_reasons"):
            fails.append("tracking_alongside_blockers")
        for lane in result.get("lanes") or []:
            if not lane.get("route_live"):
                fails.append(f"tracking_with_a_route_dead_lane:{lane.get('lane')}")
            if not lane.get("repository_live"):
                fails.append(f"tracking_with_a_repo_dead_lane:{lane.get('lane')}")
            if lane.get("route_reads_dev_header"):
                fails.append(f"lane_reads_the_dev_header:{lane.get('lane')}")

    for field in (
        "production_awarded_tracking",
        "production_rollout",
        "controlled_customer_pilot",
        "customer_auth_live",
        "verified_operational_binding",
        "real_customer_data_written",
        "real_organization_touched",
        "object_store_contacted",
        "live_grant_sources_called",
        "collectors_activated",
        "email_sent",
        "document_body_storage_ready",
    ):
        if result.get(field):
            fails.append(f"claimed:{field}")

    # A lane that is operational and route-dead is a contradiction, whichever
    # direction it came from.
    for lane in result.get("lanes") or []:
        if lane.get("operational") and lane.get("blocked_reasons"):
            fails.append(f"lane_operational_alongside_blockers:{lane.get('lane')}")

    missing = set(NOT_APPROVED) - set(result.get("not_approved") or [])
    if missing:
        fails.append(f"not_approved_list_lost_entries:{sorted(missing)}")

    if not result.get("awarded_operational_tracking") and not result.get(
        "blocked_reasons"
    ):
        fails.append("nothing_tracked_and_nothing_blocked_it")

    return fails
