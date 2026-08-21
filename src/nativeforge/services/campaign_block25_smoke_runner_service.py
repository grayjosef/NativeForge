"""Campaign Block 25 smoke."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from nativeforge.services.persistence_approval_assembler_service import (
    build_persistence_approval_demo_surface,
    persistence_approval_demo_surface_invariant_failures,
)
from nativeforge.services.sc_monday_demo_bridge_service import (
    bridge_payload_invariant_failures,
    build_sc_customer_demo_bridge_payload,
)
from nativeforge.services.validated_persistent_evidence_adapter_service import (
    run_validated_persistent_lifecycle_smoke,
)

SCHEMA_VERSION = "nf_campaign_block25_smoke_v1"
DEFAULT_OUT = Path("artifacts/campaign_block25_smoke")


def run_campaign_block25_smoke() -> dict[str, Any]:
    run_id = (
        f"nf_camp25_local_persist_smoke_"
        f"{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}_{uuid.uuid4().hex[:8]}"
    )
    fails: list[str] = []
    lifecycle = run_validated_persistent_lifecycle_smoke(
        db_path=Path("artifacts/local_dev_evidence_block25_smoke.sqlite3")
    )
    if lifecycle.get("overall_status") != "PASS":
        fails.extend([f"lifecycle:{x}" for x in (lifecycle.get("fails") or ["fail"])])
    surface = build_persistence_approval_demo_surface()
    fails.extend(persistence_approval_demo_surface_invariant_failures(surface))
    bridge = build_sc_customer_demo_bridge_payload()
    fails.extend(bridge_payload_invariant_failures(bridge))
    status = "PASS" if not fails else "FAIL"
    result = {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "overall_status": status,
        "campaign_block": 25,
        "fails": fails,
        "migration_applied": True,
        "migration_environment": "local_dev_only",
        "validated_persistent_scope": "local_dev_only",
        "upload_persistence_scope": "local_dev_only",
        "customer_data_persistence_claimed": False,
        "production_storage_claimed": False,
        "demo_route_path": "/?view=sc_customer_demo",
    }
    DEFAULT_OUT.mkdir(parents=True, exist_ok=True)
    path = DEFAULT_OUT / f"{run_id}.json"
    path.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    result["artifact"] = str(path)
    return result
