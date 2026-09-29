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
    assembler = (
        ROOT / "src/nativeforge/services/customer_canonical_feed_assembler_service.py"
    ).is_file()
    bridge = (
        ROOT / "src/nativeforge/services/early_signal_change_bridge_service.py"
    ).is_file()
    out = {
        "gate180_ready": bool(feed_routes and assembler and bridge),
        "customer_feed_api_wired": feed_routes and assembler,
        "gate170_to_176_bridge_present": bridge,
        "customer_auth_live": auth.get("customer_auth_live"),
        "launch_verdict": assessment.get("verdict"),
        "escalation_owner": assessment.get("escalation_owner"),
        "rollback_owner": assessment.get("rollback_owner"),
    }
    print(json.dumps(out, sort_keys=True))


if __name__ == "__main__":
    main()
