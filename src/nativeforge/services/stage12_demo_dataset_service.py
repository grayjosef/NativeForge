"""Sprint 244-245: isolated Stage 12 demo dataset loader with namespace guards."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Final

from nativeforge.lib.demo_isolation import require_explicit_demo_seed_context

STAGE12_NAMESPACE: Final[str] = "nf_stage12"
SCHEMA_VERSION: Final[str] = "nf_stage12_demo_dataset_v1"

_FIXTURES_ROOT = (
    Path(__file__).resolve().parents[3] / "fixtures" / "stage12_demo_path"
)


def _load_json(name: str) -> Any:
    path = _FIXTURES_ROOT / name
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def _assert_namespaced(row: dict[str, Any], *, kind: str) -> None:
    fk = str(row.get("fixture_key") or "")
    if not fk.startswith(f"{STAGE12_NAMESPACE}_"):
        raise ValueError(f"stage12 {kind} fixture_key must be namespaced: {fk!r}")
    ns = row.get("demo_namespace")
    if ns != STAGE12_NAMESPACE:
        raise ValueError(f"stage12 {kind} demo_namespace mismatch: {ns!r}")
    if row.get("fictional_only") is not True:
        raise ValueError(f"stage12 {kind} must be fictional_only=true")


def load_stage12_manifest() -> dict[str, Any]:
    doc = _load_json("manifest.json")
    if doc.get("demo_namespace") != STAGE12_NAMESPACE:
        raise ValueError("stage12 manifest namespace mismatch")
    return doc


def load_stage12_sources(*, explicit_demo_context: bool = True) -> list[dict[str, Any]]:
    require_explicit_demo_seed_context(
        is_demo_content=True,
        explicit_demo_context=explicit_demo_context,
    )
    rows = _load_json("sources.json")
    for row in rows:
        _assert_namespaced(row, kind="source")
    return rows


def load_stage12_profile(*, explicit_demo_context: bool = True) -> dict[str, Any]:
    require_explicit_demo_seed_context(
        is_demo_content=True,
        explicit_demo_context=explicit_demo_context,
    )
    rows = _load_json("profile.json")
    if len(rows) != 1:
        raise ValueError("stage12 profile fixture must contain exactly one record")
    row = rows[0]
    _assert_namespaced(row, kind="profile")
    return row


def load_stage12_opportunities(
    *, explicit_demo_context: bool = True
) -> list[dict[str, Any]]:
    require_explicit_demo_seed_context(
        is_demo_content=True,
        explicit_demo_context=explicit_demo_context,
    )
    rows = _load_json("opportunities.json")
    archetypes = {str(r.get("demo_archetype")) for r in rows}
    required = {
        "native_specific_tribal_government",
        "broadly_eligible_potentially_relevant",
        "weak_uncertain",
        "stale_expired",
    }
    if archetypes != required:
        missing = required - archetypes
        raise ValueError(f"stage12 opportunities missing archetypes: {missing}")
    for row in rows:
        _assert_namespaced(row, kind="opportunity")
    return rows


def load_stage12_dataset_bundle() -> dict[str, Any]:
    """Full isolated demo dataset for Stage 12 guided path."""
    manifest = load_stage12_manifest()
    sources = load_stage12_sources()
    profile = load_stage12_profile()
    opportunities = load_stage12_opportunities()
    return {
        "schema_version": SCHEMA_VERSION,
        "manifest": manifest,
        "sources": sources,
        "profile": profile,
        "opportunities": opportunities,
        "isolated": True,
        "fictional_only": True,
        "no_contamination": True,
        "preview_only": True,
        "no_live_ingestion": True,
    }
