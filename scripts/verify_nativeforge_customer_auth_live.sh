#!/usr/bin/env bash
# Gate 136D — is customer auth actually live right now?
#
# RESULT=PASS only when customer_auth_live is true. Anything else is
# RESULT=BLOCKED with the exact blocker named, because "not ready" without a
# reason is what this campaign has spent thirty gates removing.
#
# Every number here is read from the database or from the running backend. None
# of it is supplied to the gate, which is the whole point: Gate 135 found
# invite_binding_passed reading a parameter no caller passed.
#
# No secrets. No tokens. No cookies. No state. No PKCE verifier. No provider
# subject. No email addresses. Counts, booleans and blocker names only.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
cd "$ROOT"

BACKEND="${NF_BACKEND_OVERRIDE:-http://127.0.0.1:8000}"
TIMEOUT=20

BLOCKERS=""
FAILED=""

pass() { echo "check=$1 status=PASS ${2:-}"; }
fail() { echo "check=$1 status=FAIL ${2:-}"; [ -z "$FAILED" ] && FAILED="$1"; }
block() {
  echo "check=$1 status=BLOCKED ${2:-}"
  BLOCKERS="${BLOCKERS}${BLOCKERS:+,}$1"
}

echo "verify=customer_auth_live"

# ------------------------------------------------------------- 1. backend up
code="$(curl -s -o /dev/null -w '%{http_code}' --max-time "$TIMEOUT" \
  "$BACKEND/backend/health" 2>/dev/null || echo 000)"
if [ "$code" = "200" ]; then
  pass backend_running "http=$code"
else
  fail backend_running "http=$code"
  echo
  echo "RESULT=BLOCKED"
  echo "blocker=backend_not_running"
  exit 1
fi

# ------------------------------------------- 2. the gate, from the live route
SESSION_JSON="$(curl -s --max-time "$TIMEOUT" "$BACKEND/api/auth/session" 2>/dev/null || true)"
if [ -z "$SESSION_JSON" ]; then
  fail session_route_answered "empty"
  echo
  echo "RESULT=BLOCKED"
  echo "blocker=session_route_returned_nothing"
  exit 1
fi
pass session_route_answered

# ------------------------------------------------ 3. everything else, measured
#
# One Python process rather than a jq pipeline: the invite and membership counts
# come from the same services the gate itself reads, so a disagreement between
# this verifier and the gate is impossible by construction rather than by care.
MEASURED="$(
  NF_SESSION_JSON="$SESSION_JSON" .venv/bin/python - <<'PY' 2>/dev/null
import json
import os
import sys

sys.path.insert(0, "src")

session = json.loads(os.environ["NF_SESSION_JSON"])


def flag(name):
    if name in session:
        return session[name]
    return (session.get("activation_gate") or {}).get(name)


out = {
    "login_live": bool(flag("login_live")),
    "customer_auth_live": bool(flag("customer_auth_live")),
    "gate_blocked_reasons": list(flag("blocked_reasons") or []),
}

from nativeforge.db.session import engine
from nativeforge.services.customer_auth_owner_activation_decision_service import (
    APPROVED_ORGANIZATION_ID,
    build_customer_auth_activation_decision,
)
from nativeforge.services.dev_org_header_shutdown_readiness_service import (
    build_dev_header_shutdown_readiness,
)
from nativeforge.services.membership_invite_repository_service import (
    build_invite_binding_evidence,
)
from nativeforge.lib.settings import get_settings

readiness = build_dev_header_shutdown_readiness()
out["dev_header_route_consumers"] = int(readiness["dev_header_used_by_routes"])
out["dev_header_provider_modules"] = len(readiness["dev_header_provider_modules"])
out["nf_dev_org_headers"] = bool(get_settings().nf_dev_org_headers)

provider = (get_settings().oidc_issuer or "").strip()
decision = build_customer_auth_activation_decision(
    organization_id=APPROVED_ORGANIZATION_ID, provider=provider
)
out["owner_activation_recorded"] = bool(decision["decision_recorded"])
out["owner_activation_approves"] = bool(decision["approves_customer_auth_live"])
out["owner_activation_blocked"] = list(decision["blocked_reasons"])

with engine.connect() as connection:
    evidence = build_invite_binding_evidence(connection=connection)

for key in (
    "invite_rows",
    "approved_invite_rows",
    "accepted_invite_rows",
    "membership_rows",
    "memberships_from_a_completed_invite",
    "memberships_matching_an_accepter_by_identity_only",
):
    out[key] = int(evidence[key])
out["invite_binding_passed"] = bool(evidence["invite_binding_passed"])
out["invite_blocked_reasons"] = list(evidence["blocked_reasons"])

print(json.dumps(out))
PY
)"

if [ -z "$MEASURED" ]; then
  fail measurement_available "python_probe_failed"
  echo
  echo "RESULT=BLOCKED"
  echo "blocker=measurement_unavailable"
  exit 1
fi
pass measurement_available

get() { echo "$MEASURED" | .venv/bin/python -c "import json,sys;print(json.load(sys.stdin).get('$1'))"; }
getlist() {
  echo "$MEASURED" | .venv/bin/python -c \
    "import json,sys;print(' '.join(json.load(sys.stdin).get('$1') or []))"
}

LOGIN_LIVE="$(get login_live)"
CUSTOMER_AUTH_LIVE="$(get customer_auth_live)"
CONSUMERS="$(get dev_header_route_consumers)"
PROVIDERS="$(get dev_header_provider_modules)"
HEADERS_ON="$(get nf_dev_org_headers)"
OWNER_OK="$(get owner_activation_approves)"
INVITES="$(get invite_rows)"
APPROVED="$(get approved_invite_rows)"
ACCEPTED="$(get accepted_invite_rows)"
MEMBERSHIPS="$(get membership_rows)"
FROM_INVITE="$(get memberships_from_a_completed_invite)"
IDENTITY_ONLY="$(get memberships_matching_an_accepter_by_identity_only)"
BINDING="$(get invite_binding_passed)"

# ---------------------------------------------------------------- 4. the gates
[ "$LOGIN_LIVE" = "True" ] && pass login_live "true" || block login_live "false"

if [ "$CONSUMERS" = "0" ]; then
  pass dev_header_consumers_zero "n=0"
else
  block dev_header_consumers_zero "n=$CONSUMERS"
fi
pass dev_header_provider_modules "n=$PROVIDERS"

if [ "$HEADERS_ON" = "False" ]; then
  pass nf_dev_org_headers_false_safe "off"
else
  # Not a blocker for customer_auth_live on its own - the gate reads the
  # measured consumer count too - so it is reported rather than promoted.
  echo "check=nf_dev_org_headers_false_safe status=WARN on_but_no_route_reads_it"
fi

# ---------------------------------------------------------- 5. current-user
#
# Unauthenticated on purpose. A 401 is the route enforcing authentication,
# which is the fact worth checking without a session; driving it WITH one would
# need a cookie, and this script does not handle cookies.
cu_code="$(curl -s -o /dev/null -w '%{http_code}' --max-time "$TIMEOUT" \
  "$BACKEND/api/auth/current-user" 2>/dev/null || echo 000)"
case "$cu_code" in
  401) pass current_user_refuses_unauthenticated "http=401" ;;
  200) pass current_user_answered_a_session "http=200" ;;
  *)   fail current_user_route "http=$cu_code" ;;
esac

# ------------------------------------------------------------- 6. the invite
echo "count=invite_rows n=$INVITES"
echo "count=approved_invite_rows n=$APPROVED"
echo "count=accepted_invite_rows n=$ACCEPTED"
echo "count=membership_rows n=$MEMBERSHIPS"
echo "count=memberships_from_a_completed_invite n=$FROM_INVITE"
echo "count=memberships_matching_an_accepter_by_identity_only n=$IDENTITY_ONLY"

if [ "$BINDING" = "True" ]; then
  pass invite_binding_passed "true"
else
  block invite_binding_passed "$(getlist invite_blocked_reasons)"
fi

# ---------------------------------------------------------- 7. owner decision
if [ "$OWNER_OK" = "True" ]; then
  pass owner_activation_decision "approves_customer_auth_live"
else
  block owner_activation_decision "$(getlist owner_activation_blocked)"
fi

# ------------------------------------------------------------- 8. the answer
echo
if [ -n "$FAILED" ]; then
  echo "RESULT=BLOCKED"
  echo "blocker=check_failed:$FAILED"
  exit 1
fi

if [ "$CUSTOMER_AUTH_LIVE" = "True" ]; then
  if [ -n "$BLOCKERS" ]; then
    # The gate and the measurements disagree, which is worse news than a
    # blocker: one of them is wrong and this script will not pick.
    echo "RESULT=BLOCKED"
    echo "blocker=gate_says_live_while_measurements_say:$BLOCKERS"
    exit 1
  fi
  echo "RESULT=PASS"
  echo "customer_auth_live=true"
  echo "scope=controlled_dev_demo_org_only"
  echo "production_rollout=false"
  echo "controlled_customer_pilot=false"
  exit 0
fi

echo "RESULT=BLOCKED"
echo "customer_auth_live=false"
if [ -n "$BLOCKERS" ]; then
  echo "blocker=$BLOCKERS"
else
  echo "blocker=$(getlist gate_blocked_reasons)"
fi
echo "next=docs/operations/717_GATE136_SECOND_ACCOUNT_INVITE_EXECUTION.md"
exit 1
