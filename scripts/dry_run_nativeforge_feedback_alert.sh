#!/usr/bin/env bash
# Dry-run a NativeForge feedback Slack payload. Does not print webhook values.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
export NATIVEFORGE_FEEDBACK_ALERT_MODE="${NATIVEFORGE_FEEDBACK_ALERT_MODE:-dry_run}"
# shellcheck disable=SC1091
source .venv/bin/activate
python3 - <<'PY'
from nativeforge.services.feedback_report_contract_service import build_feedback_report
from nativeforge.services.feedback_slack_alert_service import send_feedback_slack_alert

report = build_feedback_report(
    route="/?view=sc_customer_demo",
    page_id="sc_customer_demo",
    surface_id="operator_readiness",
    report_type="customer_feedback",
    severity="medium",
    user_message="Dry-run operator feedback alert test",
    client_context={"org_display_name": "demo-org", "contact_email": "ops@example.invalid"},
)
result = send_feedback_slack_alert(report, force_dry_run=True)
print(f"slack_alert_status={result['slack_alert_status']}")
print(f"sent={result['sent']}")
print(f"alert_mode={result.get('alert_mode')}")
print(f"webhook_configured={result['webhook_configured']}")
print("RESULT=PASS" if result["sent"] is False else "RESULT=FAIL")
PY
