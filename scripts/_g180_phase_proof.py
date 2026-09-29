"""Gate 180 phase proof — lightweight launch reassessment JSON."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from nativeforge.services.controlled_launch_verifier_service import (  # noqa: E402
    build_launch_assessment,
)
from nativeforge.services.customer_auth_activation_gate_service import (  # noqa: E402
    build_customer_auth_activation_gate,
)

def main() -> None:
    auth = build_customer_auth_activation_gate()
    assessment = build_launch_assessment()
    feed_routes = (ROOT / "src/nativeforge/api/customer_opportunity_feed_routes.py").is_file()
    onboarding_routes = (
        ROOT / "src/nativeforge/api/customer_organization_onboarding_routes.py"
    ).is_file()
    assembler = (
        ROOT / "src/nativeforge/services/customer_canonical_feed_assembler_service.py"
    ).is_file()
    bridge = (
        ROOT / "src/nativeforge/services/early_signal_change_bridge_service.py"
    ).is_file()
    reconcile = (ROOT / "scripts/reconcile_grants_gov_spark_graph.py").read_text(
        encoding="utf-8"
    )
    bridge_wired = "project_recent_change_events_to_signals" in reconcile
    out = {
        "gate180_ready": bool(
            feed_routes and assembler and bridge and onboarding_routes and bridge_wired
        ),
        "customer_feed_api_wired": feed_routes and assembler,
        "gate177_onboarding_http_wired": onboarding_routes,
        "gate170_to_176_bridge_present": bridge,
        "gate176_bridge_in_operator_flow": bridge_wired,
        "customer_auth_live": auth.get("customer_auth_live"),
        "launch_verdict": assessment.get("verdict"),
        "escalation_owner": assessment.get("escalation_owner"),
        "rollback_owner": assessment.get("rollback_owner"),
    }
    print(json.dumps(out, sort_keys=True))


if __name__ == "__main__":
    main()
