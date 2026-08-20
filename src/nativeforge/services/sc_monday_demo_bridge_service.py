"""Bridge SC Monday demo artifact → frontend static JSON (read-only)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from nativeforge.services.nofo_showcase_demo_surface_service import (
    build_nofo_showcase_demo_surface,
    nofo_showcase_surface_invariant_failures,
)
from nativeforge.services.sc_monday_demo_assembler_service import (
    build_sc_monday_demo_artifact,
    demo_artifact_invariant_failures,
)

SCHEMA_VERSION = "nf_sc_monday_browser_demo_bridge_v1"
DEFAULT_FRONTEND_JSON = Path("frontend/src/demo/sc_customer_demo.json")
DEMO_ROUTE_PATH = "/?view=sc_customer_demo"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def build_sc_customer_demo_bridge_payload(
    *,
    artifact: dict[str, Any] | None = None,
) -> dict[str, Any]:
    art = artifact if artifact is not None else build_sc_monday_demo_artifact()
    fails = demo_artifact_invariant_failures(art)
    if fails:
        raise ValueError(f"SC Monday demo artifact invariants failed: {fails}")

    # Cap rows for static UI payload size while keeping both geographies.
    rows = list(art.get("rows") or [])
    sc = [r for r in rows if r.get("funding_geography") == "south_carolina"]
    fed = [r for r in rows if r.get("funding_geography") == "federal"]
    sample = sc[:40] + fed[:80]
    if len(sample) < 20:
        sample = rows[:120]

    nofo_surface = build_nofo_showcase_demo_surface(write_fixtures=False)
    nofo_fails = nofo_showcase_surface_invariant_failures(nofo_surface)
    if nofo_fails:
        raise ValueError(f"NOFO showcase surface invariants failed: {nofo_fails}")

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "title": art.get("title"),
            "demo_route_path": DEMO_ROUTE_PATH,
            "demo_dev_only": True,
            "offline_only": True,
            "read_only_advisory": True,
            "live_ingestion": False,
            "source_activation": False,
            "external_urls_used": False,
            "auth_required": False,
            "final_eligibility_claim_allowed": False,
            "pack_id": art.get("pack_id"),
            "capture_date": art.get("capture_date"),
            "content_digest": art.get("content_digest"),
            "claim_matrix": art.get("claim_matrix"),
            "profiles": art.get("profiles"),
            "opportunities": art.get("opportunities"),
            "classify_match": art.get("classify_match"),
            "combined_summary": art.get("combined_summary"),
            "missing_data_summary": art.get("missing_data_summary"),
            "provenance_evidence_summary": art.get("provenance_evidence_summary"),
            "what_nativeforge_did": art.get("what_nativeforge_did"),
            "what_requires_attention": art.get("what_requires_attention"),
            "next_actions": art.get("next_actions"),
            "rows": sample,
            "row_sample_note": (
                f"UI sample {len(sample)} of {len(rows)} profile×opportunity rows; "
                "full artifact available from assembler."
            ),
            "ui_flags": art.get("ui_flags"),
            "nofo_showcase": nofo_surface,
        }
    )


def write_sc_customer_demo_bridge_json(
    payload: dict[str, Any] | None = None,
    *,
    path: Path | None = None,
) -> Path:
    doc = payload if payload is not None else build_sc_customer_demo_bridge_payload()
    out = path or DEFAULT_FRONTEND_JSON
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return out


def bridge_payload_invariant_failures(payload: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    if payload.get("live_ingestion") is not False:
        fails.append("live_ingestion")
    if payload.get("source_activation") is not False:
        fails.append("source_activation")
    if payload.get("final_eligibility_claim_allowed") is not False:
        fails.append("final_claim")
    if not payload.get("rows"):
        fails.append("rows")
    opps = payload.get("opportunities") or {}
    if opps.get("south_carolina_count", 0) < 1:
        fails.append("sc_opps")
    if opps.get("federal_count", 0) < 1:
        fails.append("fed_opps")
    nofo = payload.get("nofo_showcase") or {}
    if not nofo:
        fails.append("nofo_showcase_missing")
    else:
        fails.extend(nofo_showcase_surface_invariant_failures(nofo))
    return fails
