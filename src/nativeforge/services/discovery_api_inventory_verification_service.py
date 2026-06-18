"""Sprint 165: discovery API inventory verification manifest (read-only)."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.main import create_app

SCHEMA_VERSION = "nf_discovery_api_inventory_manifest_v1"
DEMO_PREFIX = "/v1/nf/demo/orgs/{org_id}"
REAL_PREFIX = "/v1/nf/real/orgs/{org_id}"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _discovery_paths_from_openapi() -> list[str]:
    app = create_app()
    paths = sorted(app.openapi()["paths"].keys())
    return [p for p in paths if "/discovery/" in p]


def _plane_paths(paths: list[str], prefix: str) -> list[str]:
    out: list[str] = []
    for p in paths:
        if p.startswith(prefix):
            out.append(p[len(prefix) :])
    return sorted(out)


def build_discovery_api_inventory_manifest() -> dict[str, Any]:
    """Deterministic discovery route manifest for demo/real planes."""
    all_paths = _discovery_paths_from_openapi()
    demo_suffixes = _plane_paths(all_paths, DEMO_PREFIX)
    real_suffixes = _plane_paths(all_paths, REAL_PREFIX)
    demo_set = set(demo_suffixes)
    real_set = set(real_suffixes)
    only_demo = sorted(demo_set - real_set)
    only_real = sorted(real_set - demo_set)
    shared = sorted(demo_set & real_set)

    route_rows = [
        {
            "relative_path": suffix,
            "demo_full_path": f"{DEMO_PREFIX}{suffix}",
            "real_full_path": f"{REAL_PREFIX}{suffix}",
            "methods": _methods_for_suffix(suffix, all_paths),
            "parity": suffix in shared,
        }
        for suffix in shared
    ]

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "discovery_route_count": len(shared),
            "demo_discovery_route_count": len(demo_suffixes),
            "real_discovery_route_count": len(real_suffixes),
            "demo_real_parity": demo_set == real_set,
            "demo_only_suffixes": only_demo,
            "real_only_suffixes": only_real,
            "shared_route_suffixes": shared,
            "routes": route_rows,
            "verification_notes": (
                "Manifest is generated from FastAPI OpenAPI paths at build time; "
                "no live HTTP calls. Demo and real planes should remain symmetric."
            ),
        }
    )


def _methods_for_suffix(suffix: str, all_paths: list[str]) -> list[str]:
    app = create_app()
    openapi = app.openapi()["paths"]
    methods: set[str] = set()
    for prefix in (DEMO_PREFIX, REAL_PREFIX):
        full = f"{prefix}{suffix}"
        if full in openapi:
            for m in openapi[full]:
                if m in {"get", "post", "put", "patch", "delete"}:
                    methods.add(m.upper())
    return sorted(methods)


def render_discovery_api_inventory_manifest_markdown(
    manifest: dict[str, Any] | None = None,
) -> str:
    """Render operator markdown for the discovery API inventory manifest."""
    m = manifest if isinstance(manifest, dict) else build_discovery_api_inventory_manifest()
    lines = [
        "# NativeForge Discovery API Inventory Manifest",
        "",
        f"Schema version: `{m.get('schema_version')}`",
        "",
        "## Summary",
        "",
        f"- Shared discovery routes: **{m.get('discovery_route_count')}**",
        f"- Demo/real parity: **{m.get('demo_real_parity')}**",
        "",
        "## Shared routes",
        "",
    ]
    for row in m.get("routes") or []:
        if not isinstance(row, dict):
            continue
        rel = row.get("relative_path")
        meth = ", ".join(row.get("methods") or [])
        if isinstance(rel, str):
            lines.append(f"- `{meth}` `{rel}`")
    lines.extend(
        [
            "",
            "## Verification notes",
            "",
            str(m.get("verification_notes") or ""),
            "",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"
