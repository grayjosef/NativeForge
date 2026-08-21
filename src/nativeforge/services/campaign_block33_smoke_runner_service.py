"""Campaign Block 33 smoke."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from nativeforge.services.authority_claim_resolver_service import (
    authority_claim_resolver_invariant_failures,
    resolve_authority_claims,
)
from nativeforge.services.federal_live_authority_spike_service import (
    federal_live_authority_spike_invariant_failures,
    run_federal_live_authority_spike,
)
from nativeforge.services.live_authority_spike_assembler_service import (
    build_live_authority_spike_demo_surface,
    live_authority_spike_demo_surface_invariant_failures,
)
from nativeforge.services.sc_monday_demo_bridge_service import (
    bridge_payload_invariant_failures,
    build_sc_customer_demo_bridge_payload,
)

SCHEMA_VERSION = "nf_campaign_block33_smoke_v1"
DEFAULT_OUT = Path("artifacts/campaign_block33_smoke")


def run_campaign_block33_smoke() -> dict[str, Any]:
    run_id = (
        f"nf_camp33_authority_spike_smoke_"
        f"{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}_{uuid.uuid4().hex[:8]}"
    )
    fails: list[str] = []
    surface = build_live_authority_spike_demo_surface()
    fails.extend(live_authority_spike_demo_surface_invariant_failures(surface))
    fed = run_federal_live_authority_spike(self_attested_only=True)
    fails.extend(federal_live_authority_spike_invariant_failures(fed))
    if fed.get("federal_submission_authority_claimed"):
        fails.append("self_attest_submission")
    resolved = resolve_authority_claims(self_attested_only=True)
    fails.extend(authority_claim_resolver_invariant_failures(resolved))
    bridge = build_sc_customer_demo_bridge_payload()
    fails.extend(bridge_payload_invariant_failures(bridge))
    if not bridge.get("live_authority_spike"):
        fails.append("bridge_missing_live_authority_spike")
    status = "PASS" if not fails else "FAIL"
    result = {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "overall_status": status,
        "campaign_block": 33,
        "fails": fails,
        "sam_uei_verified_claimed": False,
        "submit_authority": False,
        "demo_route_path": "/?view=sc_customer_demo",
    }
    DEFAULT_OUT.mkdir(parents=True, exist_ok=True)
    path = DEFAULT_OUT / f"{run_id}.json"
    path.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    result["artifact"] = str(path)
    return result
