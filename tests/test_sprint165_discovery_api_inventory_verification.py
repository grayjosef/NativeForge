"""Sprint 165: discovery API inventory verification manifest."""

from __future__ import annotations

import json

from nativeforge.services.discovery_api_inventory_verification_service import (
    DEMO_PREFIX,
    REAL_PREFIX,
    SCHEMA_VERSION,
    build_discovery_api_inventory_manifest,
    render_discovery_api_inventory_manifest_markdown,
)


def test_manifest_schema_version() -> None:
    m = build_discovery_api_inventory_manifest()
    assert m["schema_version"] == SCHEMA_VERSION


def test_manifest_demo_real_parity() -> None:
    m = build_discovery_api_inventory_manifest()
    assert m["demo_real_parity"] is True
    assert m["demo_only_suffixes"] == []
    assert m["real_only_suffixes"] == []
    assert m["discovery_route_count"] >= 10


def test_manifest_includes_core_discovery_families() -> None:
    m = build_discovery_api_inventory_manifest()
    suffixes = set(m["shared_route_suffixes"])
    for fragment in (
        "/discovery/sources",
        "/discovery/review-items",
        "/discovery/operator-workbench",
        "/discovery/coverage-gap-intelligence",
    ):
        assert any(fragment in s for s in suffixes), fragment


def test_manifest_route_rows_have_methods() -> None:
    m = build_discovery_api_inventory_manifest()
    rows = m["routes"]
    assert rows
    assert all(row.get("methods") for row in rows)
    assert all(row.get("parity") is True for row in rows)


def test_manifest_deterministic() -> None:
    a = build_discovery_api_inventory_manifest()
    b = build_discovery_api_inventory_manifest()
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


def test_markdown_renderer() -> None:
    m = build_discovery_api_inventory_manifest()
    md = render_discovery_api_inventory_manifest_markdown(m)
    assert md.startswith("# NativeForge Discovery API Inventory Manifest")
    assert SCHEMA_VERSION in md
    assert "/discovery/sources" in md


def test_plane_prefixes_documented() -> None:
    m = build_discovery_api_inventory_manifest()
    for row in m["routes"][:3]:
        assert str(row["demo_full_path"]).startswith(DEMO_PREFIX)
        assert str(row["real_full_path"]).startswith(REAL_PREFIX)
