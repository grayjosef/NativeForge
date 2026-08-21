"""Campaign Block 17 smoke — code health / invariants."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from nativeforge.services.code_health_inventory_service import (
    build_code_health_inventory,
    code_health_inventory_invariant_failures,
    write_code_health_inventory_report,
)
from nativeforge.services.critical_path_coverage_map_service import (
    build_critical_path_coverage_map,
    critical_path_coverage_map_invariant_failures,
    write_critical_path_coverage_report,
)
from nativeforge.services.no_fail_invariant_suite_service import (
    run_no_fail_invariant_suite,
)

SCHEMA_VERSION = "nf_campaign_block17_smoke_v1"
DEFAULT_OUT = Path("artifacts/campaign_block17_smoke")


def run_campaign_block17_smoke() -> dict[str, Any]:
    run_id = (
        f"nf_camp17_code_health_smoke_"
        f"{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}_{uuid.uuid4().hex[:8]}"
    )
    fails: list[str] = []
    inv = build_code_health_inventory()
    fails.extend(code_health_inventory_invariant_failures(inv))
    cov = build_critical_path_coverage_map()
    fails.extend(critical_path_coverage_map_invariant_failures(cov))
    suite = run_no_fail_invariant_suite()
    if suite.get("overall_status") != "PASS":
        fails.extend([f"invariant:{x}" for x in (suite.get("fails") or [])])
    write_code_health_inventory_report(inv)
    write_critical_path_coverage_report(cov)
    status = "PASS" if not fails else "FAIL"
    result = {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "overall_status": status,
        "campaign_block": 17,
        "fails": fails,
        "totals": inv.get("totals"),
        "full_suite_run": False,
        "full_suite_passed": False,
        "pen_test_passed_claimed": False,
    }
    DEFAULT_OUT.mkdir(parents=True, exist_ok=True)
    path = DEFAULT_OUT / f"{run_id}.json"
    path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    result["artifact"] = str(path)
    return result
