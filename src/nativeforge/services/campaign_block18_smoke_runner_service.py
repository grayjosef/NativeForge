"""Campaign Block 18 smoke — security / adversarial / pen-test readiness."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from nativeforge.services.adversarial_fixture_service import run_adversarial_suite
from nativeforge.services.data_isolation_bypass_suite_service import (
    run_data_isolation_and_bypass_suite,
)
from nativeforge.services.pen_test_readiness_report_service import (
    build_pen_test_readiness_report,
    write_pen_test_readiness_report,
)
from nativeforge.services.security_posture_inventory_service import (
    build_security_posture_inventory,
    security_posture_inventory_invariant_failures,
    write_security_posture_report,
)

SCHEMA_VERSION = "nf_campaign_block18_smoke_v1"
DEFAULT_OUT = Path("artifacts/campaign_block18_smoke")


def run_campaign_block18_smoke() -> dict[str, Any]:
    run_id = (
        f"nf_camp18_security_smoke_"
        f"{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}_{uuid.uuid4().hex[:8]}"
    )
    fails: list[str] = []
    posture = build_security_posture_inventory()
    fails.extend(security_posture_inventory_invariant_failures(posture))
    adv = run_adversarial_suite()
    if adv.get("overall_status") != "PASS":
        fails.extend([f"adv:{x}" for x in (adv.get("fails") or [])])
    iso = run_data_isolation_and_bypass_suite()
    if iso.get("overall_status") != "PASS":
        fails.extend([f"iso:{x}" for x in (iso.get("fails") or [])])
    report = build_pen_test_readiness_report()
    if report.get("pen_test_passed_claimed") is True:
        fails.append("pen_test_passed_claimed")
    write_security_posture_report(posture)
    write_pen_test_readiness_report(report)
    status = "PASS" if not fails else "FAIL"
    result = {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "overall_status": status,
        "campaign_block": 18,
        "fails": fails,
        "adversarial_cases": adv.get("case_count"),
        "pen_test_passed_claimed": False,
        "production_secure_claimed": False,
    }
    DEFAULT_OUT.mkdir(parents=True, exist_ok=True)
    path = DEFAULT_OUT / f"{run_id}.json"
    path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    result["artifact"] = str(path)
    return result
