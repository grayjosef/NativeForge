"""Campaign Blocks 83–86 smoke runners."""

from __future__ import annotations

import json
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from nativeforge.services.gate35_ingest_assembler_service import (
    auth0_ingest_demo_surface_invariant_failures,
    build_auth0_ingest_demo_surface,
    build_pentest_ingest_demo_surface,
    build_pilot_resolver_demo_surface,
    build_storage_ingest_demo_surface,
    pentest_ingest_demo_surface_invariant_failures,
    pilot_resolver_demo_surface_invariant_failures,
    storage_ingest_demo_surface_invariant_failures,
)
from nativeforge.services.sc_monday_demo_bridge_service import (
    bridge_payload_invariant_failures,
    build_sc_customer_demo_bridge_payload,
)


def _run(
    *,
    block: int,
    key: str,
    builder: Callable[[], dict[str, Any]],
    inv: Callable[[dict[str, Any]], list[str]],
    prefix: str,
) -> dict[str, Any]:
    run_id = f"{prefix}_{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}_{uuid.uuid4().hex[:8]}"
    fails: list[str] = []
    surface = builder()
    fails.extend(inv(surface))
    bridge = build_sc_customer_demo_bridge_payload()
    fails.extend(bridge_payload_invariant_failures(bridge))
    if not bridge.get(key):
        fails.append(f"bridge_missing_{key}")
    status = "PASS" if not fails else "FAIL"
    result = {
        "run_id": run_id,
        "overall_status": status,
        "campaign_block": block,
        "fails": fails,
        "demo_route_path": "/?view=sc_customer_demo",
    }
    out = Path(f"artifacts/campaign_block{block}_smoke")
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"{run_id}.json"
    path.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    result["artifact"] = str(path)
    return result


def run_campaign_block83_smoke() -> dict[str, Any]:
    return _run(
        block=83,
        key="auth0_ingest",
        builder=build_auth0_ingest_demo_surface,
        inv=auth0_ingest_demo_surface_invariant_failures,
        prefix="nf_camp83_auth_ingest_smoke",
    )


def run_campaign_block84_smoke() -> dict[str, Any]:
    return _run(
        block=84,
        key="storage_ingest",
        builder=build_storage_ingest_demo_surface,
        inv=storage_ingest_demo_surface_invariant_failures,
        prefix="nf_camp84_storage_ingest_smoke",
    )


def run_campaign_block85_smoke() -> dict[str, Any]:
    return _run(
        block=85,
        key="pentest_ingest",
        builder=build_pentest_ingest_demo_surface,
        inv=pentest_ingest_demo_surface_invariant_failures,
        prefix="nf_camp85_pentest_ingest_smoke",
    )


def run_campaign_block86_smoke() -> dict[str, Any]:
    return _run(
        block=86,
        key="pilot_resolver",
        builder=build_pilot_resolver_demo_surface,
        inv=pilot_resolver_demo_surface_invariant_failures,
        prefix="nf_camp86_pilot_resolver_smoke",
    )
