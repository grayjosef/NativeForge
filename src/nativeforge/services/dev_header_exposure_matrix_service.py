"""Gate 133F: which dev-header routes are actually reachable from outside.

## The gap this closes

`dev_org_header_containment_service` answers "does the tunnel route to the
backend" and concludes from that whether the backend is publicly exposed. Its
answer today is `True`, and it is right - but for one of the two reasons.

```text
cloudflared ingress    ^/api/.*   ->  127.0.0.1:8000    the backend
cloudflared ingress    (hostname) ->  127.0.0.1:5175    the Vite preview
vite preview proxy     /v1        ->  127.0.0.1:8000    the backend, again
```

Every one of the dev-header routes is under `/v1`, so **none of them is reached
by the ingress rule the detector inspects**. They are reached by the preview's
proxy, one hop further in, which the detector never looks at. Remove the
`/api/*` ingress line and it would report the backend contained while all 207
dev-header routes stayed exposed.

Third instance of this shape in three gates: Gate 130's detector read
`~/.cloudflared/config.yml` while the live tunnel ran a different file, Gate
131's migration reader hardcoded one filename for a table defined by two, and
this one models one hop of two. The pattern is a detector that measures a
proxy for the thing instead of the thing.

## Derived from the app, not from grep

A route inherits the dev header through a dependency it does not name -
`require_demo_org_db` depends on `get_org_context_with_db`, which declares the
header. So the matrix walks the resolved dependency tree of every registered
route. Grepping route modules for `X-NF-Org-Id` finds none of them.

## Public reachability is a path question

```text
publicly_routed    the path root matches a cloudflared ingress path rule, OR
                   it matches a preview proxy prefix and the catch-all sends
                   the hostname to the preview
behind_access      measured separately; Cloudflare Access is an edge boundary
                   and gates who reaches the app, not which organization a
                   header may name once they are through
```

`behind_access` is not read from a config file - the Access policy is not in
this repository. It is reported as unknown unless a caller supplies what it
measured, so this module never claims a containment it did not observe.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "nf_dev_header_exposure_matrix_v1"

DEV_HEADER_NAME = "X-NF-Org-Id"

#: Dependencies that consume the dev header, directly or by depending on one
#: that does. Named rather than detected by signature: a dependency that stops
#: reading the header should be removed from this list in the same change.
DEV_HEADER_DEPENDENCIES: frozenset[str] = frozenset(
    {
        "get_org_context_with_db",
        "require_demo_org_db",
        "require_real_org_db",
        "get_org_context_dev",
        "require_demo_org",
        "require_real_org",
        "get_dev_org_context_explicit_only",
    }
)

#: The session-backed replacements. A module using these is converted.
AUTH_DEPENDENCIES: frozenset[str] = frozenset(
    {
        "get_customer_org_context_required",
        "get_customer_org_context_optional",
        "require_customer_demo_org",
        "require_customer_real_org",
        "require_customer_session",
        "optional_customer_session",
    }
)

#: Where the preview's proxy table lives. Read, not assumed.
VITE_CONFIG = "frontend/vite.config.ts"

#: Every cloudflared config, not a chosen one. Gate 130's detector named a
#: single file and the live tunnel ran another.
CLOUDFLARED_GLOBS = ("*.yml", "*.yaml")

MATRIX_COLUMNS: tuple[str, ...] = (
    "module",
    "path_root",
    "routes",
    "consumes_dev_header",
    "publicly_routed",
    "exposure_hop",
    "behind_access",
    "uses_organization_id_authority",
    "replacement_available",
    "conversion_risk",
    "recommended_order",
)

#: Why each module is risky to convert, and in what order. The risk is a
#: judgement; the route counts and the exposure beside it are measured.
CONVERSION_NOTES: dict[str, tuple[str, str]] = {
    "isolation_routes": (
        "none",
        "converted in Gate 133F. Nothing calls it: no frontend code, no script, "
        "no e2e spec. Its only purpose is proving the separation, and a session "
        "proves it better than a header",
    ),
    "stage12_guided_demo_routes": (
        "low",
        "guided demo surface, served from a committed payload; the frontend "
        "reads the payload rather than these routes",
    ),
    "trust_routes": (
        "low",
        "read-only trust manifest; the demo shell calls it and would need a "
        "session first",
    ),
    "activation_routes": (
        "medium",
        "workspace activation flags; writes durable state, so a wrong "
        "organization here persists",
    ),
    "tribal_profile_routes": (
        "medium",
        "customer-owned profile data. A wrong organization writes a Tribe's "
        "facts into another Tribe's row",
    ),
    "form_package_routes": ("medium", "review-gated packages; writes"),
    "nofo_extraction_routes": ("medium", "extraction runs; writes"),
    "pursuit_brief_routes": ("medium", "derived briefs; writes"),
    "spark_scoring_routes": ("medium", "deterministic scores; writes"),
    "grant_spark_routes": ("high", "the discovery surface the demo shell reads"),
    "operator_workbench_advisory_routes": (
        "high",
        "operator advisory surface; the demo shell reads it",
    ),
    "pursuit_routes": ("high", "pursuit workflow, 20 routes, writes throughout"),
    "sprint0_routes": ("high", "foundational org routes other modules assume"),
    "source_ingestion_routes": (
        "high",
        "26 routes; touches the collector boundary, which must stay off",
    ),
    "opportunity_discovery_routes": (
        "highest",
        "84 routes, the largest surface in the application and the one the demo "
        "depends on most",
    ),
}


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _dependency_names(dependant: Any) -> set[str]:
    """Every dependency name in a route's resolved tree, at any depth."""
    names: set[str] = set()
    for sub in getattr(dependant, "dependencies", ()) or ():
        call = getattr(sub, "call", None)
        if call is not None:
            names.add(getattr(call, "__name__", str(call)))
        names |= _dependency_names(sub)
    return names


def _api_routes(routes: Any) -> list[Any]:
    """Flatten routers, including the wrappers `include_router` installs."""
    from fastapi.routing import APIRoute

    out: list[Any] = []
    for route in routes or ():
        if isinstance(route, APIRoute):
            out.append(route)
            continue
        inner = getattr(route, "original_router", None)
        if inner is not None:
            out.extend(_api_routes(getattr(inner, "routes", ())))
    return out


def read_preview_proxy_prefixes(*, repo_root: Any = None) -> list[str]:
    """Path prefixes the Vite **preview** forwards to the backend.

    Parsed from the config rather than assumed, because this is the hop the
    containment detector misses and a hardcoded list here would repeat its
    mistake one file over.

    The `server` and `preview` blocks have different proxy tables, and only
    `preview` is what the tunnel reaches. A first version of this scanned the
    whole file for `"<prefix>": api` and reported `/health` as publicly proxied
    to the backend - it is in `server.proxy` only, and the config says so in a
    comment: "Stamped dist/health is the demo listener check; do not proxy to
    API." Over-reporting an exposure is still a wrong measurement, and this one
    would have shown up in a security matrix as a route that is not there.
    """
    root = Path(repo_root) if repo_root else Path(".")
    path = root / VITE_CONFIG
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return []

    def _keys(block: str) -> list[str]:
        return [
            match.group(1)
            for match in re.finditer(
                r"[\"']([/][A-Za-z0-9._/-]*)[\"']\s*:\s*api\b", block
            )
        ]

    # `const apiProxy = { "/v1": api, ... }` - the shared table.
    shared: list[str] = []
    shared_match = re.search(r"const\s+apiProxy\s*=\s*\{(.*?)\}", text, re.DOTALL)
    if shared_match:
        shared = _keys(shared_match.group(1))

    # The `preview:` block, up to the next top-level key. Only its proxy table
    # is reachable through the tunnel.
    preview_match = re.search(r"\n\s*preview\s*:\s*\{(.*?)\n\s{2}\},", text, re.DOTALL)
    prefixes: list[str] = []
    if preview_match:
        block = preview_match.group(1)
        if "...apiProxy" in block:
            prefixes.extend(shared)
        prefixes.extend(_keys(block))

    return sorted(set(prefixes))


def read_tunnel_backend_paths(*, detect_root: Any = None) -> list[str]:
    """Ingress path patterns any cloudflared config routes to the backend.

    Every config in the directory is read. Gate 130's detector named one file
    while the live tunnel ran another, and the rule that came out of that is
    that a detector reads all of them.
    """
    root = Path(detect_root) if detect_root else Path.home() / ".cloudflared"
    patterns: list[str] = []
    files: list[Path] = []
    for glob in CLOUDFLARED_GLOBS:
        try:
            files.extend(sorted(root.glob(glob)))
        except OSError:
            continue

    for path in files:
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        current_path: str | None = None
        for raw in text.splitlines():
            line = raw.strip()
            if line.startswith("- hostname:"):
                current_path = None
            elif line.startswith("path:"):
                current_path = line.split(":", 1)[1].strip()
            elif line.startswith("service:") and current_path:
                service = line.split(":", 1)[1].strip()
                if "8000" in service and current_path not in patterns:
                    patterns.append(current_path)
                current_path = None
    return sorted(patterns)


def _matches_ingress(path_root: str, patterns: list[str]) -> bool:
    for pattern in patterns:
        try:
            if re.match(pattern, path_root + "/"):
                return True
        except re.error:
            if path_root.startswith(pattern.strip("^").rstrip(".*")):
                return True
    return False


def build_dev_header_exposure_matrix(
    *,
    app: Any = None,
    repo_root: Any = None,
    detect_root: Any = None,
    behind_access: bool | None = None,
    ingress_patterns: list[str] | None = None,
) -> dict[str, Any]:
    """Every route module, what it consumes, and whether it is reachable.

    ``ingress_patterns`` is injectable because the cloudflared config lives in
    the operator's home directory, not in this repository. A committed artifact
    generated from it would differ on every machine and could not be
    regenerated, so artifact generation passes the patterns it measured, dated
    and labelled as a recording, while a live check reads the machine.

    The preview proxy is the other half and needs no such handling: its config
    is `frontend/vite.config.ts`, which is committed.
    """
    if app is None:
        from nativeforge.main import app as default_app

        app = default_app

    if ingress_patterns is None:
        ingress_patterns = read_tunnel_backend_paths(detect_root=detect_root)
    else:
        ingress_patterns = sorted(set(ingress_patterns))
    proxy_prefixes = read_preview_proxy_prefixes(repo_root=repo_root)

    modules: dict[str, dict[str, Any]] = {}
    for route in _api_routes(getattr(app, "routes", ())):
        module = route.endpoint.__module__.rsplit(".", 1)[-1]
        names = _dependency_names(route.dependant)
        root = "/" + route.path.lstrip("/").split("/")[0]
        entry = modules.setdefault(
            module,
            {
                "module": module,
                "path_root": root,
                "routes": 0,
                "dev": False,
                "auth": False,
            },
        )
        entry["routes"] += 1
        entry["dev"] = entry["dev"] or bool(names & DEV_HEADER_DEPENDENCIES)
        entry["auth"] = entry["auth"] or bool(names & AUTH_DEPENDENCIES)

    rows: list[dict[str, Any]] = []
    for module in sorted(modules):
        entry = modules[module]
        root = entry["path_root"]
        by_ingress = _matches_ingress(root, ingress_patterns)
        by_proxy = root in proxy_prefixes
        hops = []
        if by_ingress:
            hops.append("tunnel_ingress")
        if by_proxy:
            hops.append("preview_proxy")
        risk, note = CONVERSION_NOTES.get(module, ("unknown", "not classified"))
        rows.append(
            {
                "module": module,
                "path_root": root,
                "routes": entry["routes"],
                "consumes_dev_header": bool(entry["dev"]),
                "publicly_routed": bool(by_ingress or by_proxy),
                "exposure_hop": "+".join(hops) or "none",
                "behind_access": (
                    "unknown" if behind_access is None else str(bool(behind_access))
                ),
                "uses_organization_id_authority": True,
                "replacement_available": (
                    "converted" if entry["auth"] and not entry["dev"] else "available"
                ),
                "conversion_risk": risk if entry["dev"] else "none",
                "conversion_note": note if entry["dev"] else "not a consumer",
            }
        )

    dev_rows = [row for row in rows if row["consumes_dev_header"]]
    exposed = [row for row in dev_rows if row["publicly_routed"]]
    order = _recommended_order(dev_rows)
    for row in rows:
        row["recommended_order"] = order.get(row["module"], 0)

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "dev_header_name": DEV_HEADER_NAME,
            "route_total": sum(row["routes"] for row in rows),
            "dev_header_modules": [row["module"] for row in dev_rows],
            "dev_header_module_count": len(dev_rows),
            "dev_header_route_count": sum(row["routes"] for row in dev_rows),
            "converted_modules": [
                row["module"]
                for row in rows
                if row["replacement_available"] == "converted"
            ],
            "publicly_routed_dev_header_routes": sum(row["routes"] for row in exposed),
            "tunnel_backend_ingress_patterns": ingress_patterns,
            "preview_proxy_prefixes": proxy_prefixes,
            "exposure_hops_detected": sorted(
                {row["exposure_hop"] for row in exposed} - {"none"}
            ),
            # The finding this module exists for.
            "exposed_only_via_preview_proxy": sorted(
                {
                    row["module"]
                    for row in exposed
                    if row["exposure_hop"] == "preview_proxy"
                }
            ),
            "containment_detector_models_preview_proxy": False,
            "behind_access": (
                "unknown" if behind_access is None else str(bool(behind_access))
            ),
            "rows": rows,
        }
    )


def _recommended_order(dev_rows: list[dict[str, Any]]) -> dict[str, int]:
    """Least risky first, and within a risk band the smallest surface first."""
    bands = {"none": 0, "low": 1, "medium": 2, "high": 3, "highest": 4, "unknown": 5}
    ordered = sorted(
        dev_rows,
        key=lambda row: (bands.get(row["conversion_risk"], 5), row["routes"]),
    )
    return {row["module"]: index + 1 for index, row in enumerate(ordered)}


def matrix_to_csv(matrix: dict[str, Any]) -> str:
    """The matrix as CSV. Columns are declared, so a new key cannot slip in."""
    import csv
    import io

    buffer = io.StringIO()
    writer = csv.DictWriter(
        buffer,
        fieldnames=list(MATRIX_COLUMNS),
        extrasaction="ignore",
        lineterminator="\n",
    )
    writer.writeheader()
    for row in matrix["rows"]:
        writer.writerow({column: row.get(column, "") for column in MATRIX_COLUMNS})
    return buffer.getvalue()


def matrix_invariant_failures(matrix: dict[str, Any]) -> list[str]:
    fails: list[str] = []

    if not matrix.get("rows"):
        fails.append("matrix_has_no_rows")
    if matrix.get("route_total", 0) <= 0:
        fails.append("matrix_counted_no_routes")

    # A matrix that found no way in has almost certainly failed to read a
    # config, and reporting containment on an unreadable file is how Gate 130's
    # detector got it wrong.
    if not matrix.get("tunnel_backend_ingress_patterns") and not matrix.get(
        "preview_proxy_prefixes"
    ):
        fails.append("no_exposure_path_detected_so_nothing_was_read")

    for row in matrix.get("rows") or []:
        if row.get("consumes_dev_header") and row.get("conversion_risk") == "unknown":
            fails.append(f"unclassified_dev_header_module:{row['module']}")
        if row.get("consumes_dev_header") and row.get("replacement_available") == (
            "converted"
        ):
            fails.append(f"module_both_converted_and_consuming:{row['module']}")

    counted = sum(
        row["routes"] for row in matrix.get("rows") or [] if row["consumes_dev_header"]
    )
    if counted != matrix.get("dev_header_route_count"):
        fails.append("dev_header_route_count_disagrees_with_the_rows")

    return fails
