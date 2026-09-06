"""Gate 143D: is source monitoring ready to be *reasoned about*, not run?

## Two flags, and the whole gate is keeping them apart

```text
source_monitoring_preflight_ready   can this system evaluate every source,
                                    classify what blocks it, and prove no live
                                    call path is active?   TRUE

source_monitoring_live              is anything actually being checked?
                                    FALSE, and nothing here can make it true.
```

`source_monitoring_live` is not answered here at all. It is read from
`source_scheduler_readiness_service`, which already derives it from four
conjuncts — runtime mode, worker, trigger, persistent backend — and reports
false because five components are absent. A second answer to one question is
the shape Gate 114 spent a gate collapsing.

## What preflight readiness requires

```text
the registry loads                        177 rows
every row is classified                   by the allowlist
the collector preflight works             seven declared policies
the choke point scan is clean             no unapproved network call site
no live call was made                     0, and proved by parsing
the tenant watchlist can name a source     Gate 140's registry check
activation blockers are NAMED              not merely counted
tenant_digest_operational is true          there is nothing to monitor for
                                           otherwise
```

## What it explicitly does not require

```text
a monitorable source                 there are ZERO, and requiring one would
                                     make the readiness lane unreachable until
                                     a human finishes a terms review
a collector                          the thing readiness is NOT
a scheduler runtime                  same
live source access                   same
```

Stated as fields. An unsatisfiable conjunct makes every "not ready" above it
unfalsifiable — Gate 134F's lesson, kept out of a fourth lane now.

## Production stays false

`production_source_monitoring` has no branch that sets it, and an invariant
fails if a passing preflight ever sets `source_monitoring_live`.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "nf_source_monitoring_readiness_v1"

CONTROLLED_SCOPE = "controlled_dev_demo"

SCOPE_NONE = "none"
SCOPE_PRODUCTION = "production"
READINESS_SCOPES: tuple[str, ...] = (SCOPE_NONE, CONTROLLED_SCOPE, SCOPE_PRODUCTION)

READINESS_ROUTE_MODULE = "src/nativeforge/api/source_monitoring_readiness_routes.py"

REQUIRED_DEPENDENCY = "require_demo_org_session"

#: Modules this readiness depends on. Each must exist and must not import a
#: network client outside Gate 94's approved chokepoint.
MONITORING_MODULES: tuple[str, ...] = (
    "src/nativeforge/services/source_monitoring_approved_source_service.py",
    "src/nativeforge/services/source_collector_configuration_preflight_service.py",
    "src/nativeforge/services/source_monitoring_readiness_service.py",
)

#: Top-level packages that exist to make requests. `urllib` and `http` are
#: deliberately ABSENT: both have inert submodules (`urllib.parse`,
#: `urllib.robotparser`) that parse strings and open nothing, and Gate 94's
#: enforcement service already draws that line. `_is_network_module` asks it.
NETWORK_LIBRARIES: frozenset[str] = frozenset(
    {
        "httpx",
        "requests",
        "aiohttp",
        "urllib3",
        "socket",
        "ftplib",
        "telnetlib",
        "selenium",
        "playwright",
    }
)

#: Claims this module never makes.
NOT_APPROVED: tuple[str, ...] = (
    "source_monitoring_live",
    "production_source_monitoring",
    "collector_activation",
    "live_source_coverage",
    "scraping",
    "robots_bypass",
    "terms_review_bypass",
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def detect_readiness_route_module(*, repo_root: Path | None = None) -> dict[str, Any]:
    """Does the readiness route module exist, and is it session-wired?

    ``repo_root`` is injectable so the absent branch is reachable. Parsed for
    `Depends(require_demo_org_session)` rather than searched as a substring.
    """
    root = repo_root if repo_root is not None else _repo_root()
    path = root / READINESS_ROUTE_MODULE
    if not path.is_file():
        return {
            "route_module": READINESS_ROUTE_MODULE,
            "route_module_available": False,
            "session_wired": False,
            "makes_no_live_call": True,
            "blocked_reasons": ["route_module_does_not_exist"],
        }

    body = path.read_text(encoding="utf-8", errors="replace")
    blocked: list[str] = []
    session_wired = bool(re.search(rf"Depends\(\s*{REQUIRED_DEPENDENCY}\s*\)", body))
    if not session_wired:
        blocked.append("route_module_does_not_depend_on_a_session_org_context")

    makes_no_live_call = not re.search(
        r"\bhttpx\.|requests\.get|aiohttp\.|urlopen\(", body
    )
    if not makes_no_live_call:
        blocked.append("route_module_looks_like_it_fetches")

    return _json_safe(
        {
            "route_module": READINESS_ROUTE_MODULE,
            "route_module_available": True,
            "session_wired": session_wired,
            "makes_no_live_call": makes_no_live_call,
            "blocked_reasons": sorted(set(blocked)),
        }
    )


def _is_network_module(dotted: str) -> bool:
    """Would importing this module let a caller reach a host?

    `urllib.parse` and `urllib.robotparser` would not. Gate 94's enforcement
    service owns that distinction; this asks it rather than keeping a second
    list that could disagree.
    """
    from nativeforge.services.hermetic_network_enforcement_service import (
        INERT_URLLIB_SUBMODULES,
        NETWORK_HTTP_SUBMODULES,
        NETWORK_URLLIB_SUBMODULES,
    )

    name = str(dotted or "").strip()
    if not name:
        return False
    if name in INERT_URLLIB_SUBMODULES:
        return False
    if name in NETWORK_URLLIB_SUBMODULES or name in NETWORK_HTTP_SUBMODULES:
        return True
    return name.split(".")[0] in NETWORK_LIBRARIES


def detect_network_imports(*, repo_root: Path | None = None) -> dict[str, Any]:
    """Does any monitoring module import something that could reach a source?

    Parsed with `ast`. A docstring naming `httpx` is not an import, and a probe
    that could not tell the difference would report on prose.
    """
    import ast

    root = repo_root if repo_root is not None else _repo_root()
    findings: dict[str, list[str]] = {}
    missing: list[str] = []

    for relative in MONITORING_MODULES:
        path = root / relative
        if not path.is_file():
            missing.append(relative)
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
        except SyntaxError:
            findings[relative] = ["module_does_not_parse"]
            continue
        # Full dotted paths, so `urllib.parse` and `urllib.request` stay
        # different things.
        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(a.name for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                imported.add(node.module)
        found = sorted(name for name in imported if _is_network_module(name))
        if found:
            findings[relative] = found

    return _json_safe(
        {
            "modules_checked": list(MONITORING_MODULES),
            "modules_missing": sorted(missing),
            "network_imports": findings,
            "any_network_library_imported": bool(findings),
            "network_libraries_watched": sorted(NETWORK_LIBRARIES),
        }
    )


def build_source_monitoring_readiness(
    *,
    registry_evaluation: dict[str, Any] | None = None,
    collector_preflight: dict[str, Any] | None = None,
    chokepoint_scan: dict[str, Any] | None = None,
    watchlist_can_name_sources: bool | None = None,
    tenant_digest_operational: bool | None = None,
    route_smoke: dict[str, Any] | None = None,
    repo_root: Path | None = None,
    measure: bool = True,
) -> dict[str, Any]:
    """Is the preflight ready? Calls no source and activates nothing."""
    from nativeforge.services.source_monitoring_approved_source_service import (
        allowlist_invariant_failures,
        evaluate_registry,
    )

    evaluation = (
        registry_evaluation
        if registry_evaluation is not None
        else (evaluate_registry() if measure else {})
    )
    collector = collector_preflight or {}
    smoke = route_smoke or {}

    if chokepoint_scan is not None:
        scan = chokepoint_scan
    elif measure:
        from nativeforge.services.hermetic_network_enforcement_service import (
            scan_for_network_call_sites,
        )

        scan = scan_for_network_call_sites()
    else:
        scan = {}

    module = detect_readiness_route_module(repo_root=repo_root)
    imports = detect_network_imports(repo_root=repo_root)

    blocked: list[str] = []
    blocked.extend(f"route_module:{r}" for r in module["blocked_reasons"])
    blocked.extend(
        f"allowlist_invariant:{f}" for f in allowlist_invariant_failures(evaluation)
    )

    if imports["any_network_library_imported"]:
        blocked.append(
            "a_monitoring_module_imports_a_network_library:"
            + ",".join(sorted(imports["network_imports"]))
        )
    if imports["modules_missing"]:
        blocked.append(
            "monitoring_module_missing:" + ",".join(imports["modules_missing"])
        )

    # -- what preflight must prove ------------------------------------------
    registry_loaded = int(evaluation.get("registry_row_count") or 0) > 0
    every_row_classified = int(evaluation.get("evaluated_count") or 0) == int(
        evaluation.get("registry_row_count") or -1
    )
    collector_preflight_works = bool(collector.get("state"))
    chokepoint_clean = bool(scan.get("clean"))
    watchlist_ok = (
        bool(watchlist_can_name_sources)
        if watchlist_can_name_sources is not None
        else False
    )
    digest_live = (
        bool(tenant_digest_operational)
        if tenant_digest_operational is not None
        else False
    )

    if not registry_loaded:
        blocked.append("the_source_registry_did_not_load")
    if not every_row_classified:
        blocked.append("not_every_registry_row_was_classified")
    if not collector:
        blocked.append("no_collector_preflight_was_supplied")
    elif not collector_preflight_works:
        blocked.append("the_collector_preflight_produced_no_state")
    if not scan:
        blocked.append("no_chokepoint_scan_was_supplied")
    elif not chokepoint_clean:
        blocked.append(
            f"chokepoint_scan_found_{int(scan.get('unapproved_count') or 0)}_"
            "unapproved_call_sites"
        )
    if not watchlist_ok:
        blocked.append("the_watchlist_cannot_name_a_registry_source")
    if not digest_live:
        blocked.append("tenant_digest_is_not_operational")

    # -- what must NOT have happened ----------------------------------------
    fetches = int(evaluation.get("network_calls") or 0) + int(
        collector.get("network_calls") or 0
    )
    if fetches:
        blocked.append(f"a_network_call_was_made:{fetches}")
    if evaluation.get("collector_activated") or collector.get("collector_activated"):
        blocked.append("a_collector_was_activated")
    if evaluation.get("source_monitoring_live") or collector.get(
        "source_monitoring_live"
    ):
        blocked.append("something_claimed_source_monitoring_live")

    if smoke:
        for name in (
            "readiness_routes_operational",
            "unauthenticated_refused",
            "cross_org_refused",
        ):
            if not smoke.get(name):
                blocked.append(f"smoke_did_not_prove:{name}")
        blocked.extend(f"smoke:{r}" for r in smoke.get("blocked_reasons") or [])

    ready = bool(
        module["route_module_available"]
        and module["session_wired"]
        and module["makes_no_live_call"]
        and registry_loaded
        and every_row_classified
        and collector_preflight_works
        and chokepoint_clean
        and watchlist_ok
        and digest_live
        and not blocked
    )

    # `source_monitoring_live` is read from the scheduler and nowhere else.
    from nativeforge.services.source_scheduler_readiness_service import (
        build_scheduler_readiness,
    )

    scheduler = build_scheduler_readiness()
    monitoring_live = bool(scheduler.get("source_monitoring_live"))

    activation_blockers = _activation_blockers(evaluation, scheduler)

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "source_monitoring_preflight_ready": ready,
            "source_monitoring_live": monitoring_live,
            "scope": CONTROLLED_SCOPE if ready else SCOPE_NONE,
            "scopes": list(READINESS_SCOPES),
            "registry_loaded": registry_loaded,
            "registry_row_count": int(evaluation.get("registry_row_count") or 0),
            "every_row_classified": every_row_classified,
            "by_state": evaluation.get("by_state") or {},
            "monitorable_count": int(evaluation.get("monitorable_count") or 0),
            "collector_preflight_state": collector.get("state"),
            "collector_preflight_works": collector_preflight_works,
            "chokepoint_clean": chokepoint_clean,
            "chokepoint_unapproved_count": int(scan.get("unapproved_count") or 0),
            "chokepoint_files_scanned": int(scan.get("files_scanned") or 0),
            "watchlist_can_name_sources": watchlist_ok,
            "tenant_digest_operational": digest_live,
            "route_module": module,
            "network_imports": imports,
            "scheduler_runtime_mode": scheduler.get("runtime_mode"),
            "scheduler_components_missing": list(
                scheduler.get("components_missing") or []
            ),
            "activation_blockers": activation_blockers,
            # Named as fields, not implied. Requiring any of them would make
            # this lane unreachable until a human finishes a terms review.
            "monitorable_source_required_for_readiness": False,
            "collector_required_for_readiness": False,
            "scheduler_runtime_required_for_readiness": False,
            "live_source_access_required_for_readiness": False,
            # Constants. No branch sets any of them.
            "collector_activated": False,
            "fetch_performed": False,
            "network_calls": 0,
            "live_source_coverage": False,
            "production_source_monitoring": False,
            "customer_auth_live": False,
            "real_organization_touched": False,
            "api_key_values_reported": False,
            "not_approved": list(NOT_APPROVED),
            "blocked_reasons": sorted(set(blocked)),
        }
    )


def _activation_blockers(
    evaluation: dict[str, Any], scheduler: dict[str, Any]
) -> list[dict[str, str]]:
    """What activation would still need, each named with its owner.

    Named rather than counted: "47 blockers" tells an operator nothing about
    what to do next, and every one of these has a different owner.
    """
    by_state = evaluation.get("by_state") or {}
    blockers: list[dict[str, str]] = []

    if by_state.get("terms_blocked"):
        blockers.append(
            {
                "blocker": "terms_review_incomplete",
                "count": str(by_state["terms_blocked"]),
                "owner": "a human reviewing each source's terms of use",
                "why": "the registry has no terms column, so every unreviewed "
                "row is UNKNOWN and UNKNOWN is blocking",
            }
        )
    if by_state.get("human_review_blocked"):
        blockers.append(
            {
                "blocker": "human_review_only_sources",
                "count": str(by_state["human_review_blocked"]),
                "owner": "a human",
                "why": "the terms page is client-rendered and served no policy "
                "text; nobody could read it, which is not permission",
            }
        )
    if by_state.get("api_key_missing"):
        blockers.append(
            {
                "blocker": "credential_and_role_required",
                "count": str(by_state["api_key_missing"]),
                "owner": "whoever can obtain the key and the role",
                "why": "scraping is prohibited and the API needs both",
            }
        )
    for component in scheduler.get("components_missing") or []:
        blockers.append(
            {
                "blocker": f"scheduler_component_absent:{component}",
                "count": "1",
                "owner": "a later gate",
                "why": "nothing can run a check without it",
            }
        )
    return blockers


def source_monitoring_readiness_invariant_failures(
    result: dict[str, Any],
) -> list[str]:
    """What must never be true of a source monitoring readiness result."""
    fails: list[str] = []

    scope = result.get("scope")
    if scope not in READINESS_SCOPES:
        fails.append(f"scope_not_recognised:{scope}")

    if result.get("source_monitoring_preflight_ready"):
        if scope != CONTROLLED_SCOPE:
            fails.append(f"ready_outside_the_scope:{scope}")
        for field in (
            "registry_loaded",
            "every_row_classified",
            "collector_preflight_works",
            "chokepoint_clean",
            "watchlist_can_name_sources",
            "tenant_digest_operational",
        ):
            if not result.get(field):
                fails.append(f"ready_without:{field}")
        if result.get("blocked_reasons"):
            fails.append("ready_alongside_blockers")

    # The load-bearing separation of the whole gate.
    if result.get("source_monitoring_preflight_ready") and result.get(
        "source_monitoring_live"
    ):
        fails.append("a_preflight_activated_source_monitoring")

    for field in (
        "collector_activated",
        "fetch_performed",
        "live_source_coverage",
        "production_source_monitoring",
        "customer_auth_live",
        "real_organization_touched",
        "api_key_values_reported",
    ):
        if result.get(field):
            fails.append(f"claimed:{field}")
    if result.get("network_calls"):
        fails.append("nonzero:network_calls")

    for field in (
        "monitorable_source_required_for_readiness",
        "collector_required_for_readiness",
        "scheduler_runtime_required_for_readiness",
        "live_source_access_required_for_readiness",
    ):
        if result.get(field):
            fails.append(f"required_for_a_preflight:{field}")

    imports = result.get("network_imports") or {}
    if imports.get("any_network_library_imported"):
        fails.append("a_monitoring_module_imports_a_network_library")

    if result.get("chokepoint_unapproved_count"):
        fails.append("unapproved_network_call_sites_exist")

    missing = set(NOT_APPROVED) - set(result.get("not_approved") or [])
    if missing:
        fails.append(f"not_approved_list_lost_entries:{sorted(missing)}")

    if not result.get("source_monitoring_preflight_ready") and not result.get(
        "blocked_reasons"
    ):
        fails.append("not_ready_and_nothing_blocked_it")

    return fails
