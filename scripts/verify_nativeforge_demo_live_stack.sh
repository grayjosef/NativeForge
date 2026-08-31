#!/usr/bin/env bash
# Gate 130C — is the demo actually servable right now?
#
# Written after a demo showed Cloudflare Error 1033 while every service on the
# host reported active. `systemctl is-active` says a process is running; it says
# nothing about whether the connector is registered with Cloudflare's edge or
# whether the public hostname resolves to anything. This checks the thing that
# matters: what a browser gets.
#
# 1033 means Cloudflare has the hostname but cannot reach a connector. It is the
# one status this verifier treats as fatal on sight, because it is invisible
# from inside the host.
#
# No secrets. No values. Status codes and check names only.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
cd "$ROOT"

PUBLIC_ORIGIN="${NF_PUBLIC_ORIGIN_OVERRIDE:-https://nf-dev.mayhem-nc.dev}"
PREVIEW="http://127.0.0.1:5175"
BACKEND="http://127.0.0.1:8000"
CALLBACK_PATH="/api/auth/callback"
TIMEOUT=25

FAILED=""

pass() { echo "check=$1 status=PASS ${2:-}"; }
fail() { echo "check=$1 status=FAIL ${2:-}"; [ -z "$FAILED" ] && FAILED="$1"; }

code() { curl -s -o /dev/null -w "%{http_code}" --max-time "$TIMEOUT" "$1" 2>/dev/null || echo 000; }
body() { curl -s --max-time "$TIMEOUT" "$1" 2>/dev/null || true; }

echo "verify=demo_live_stack"

# ---------------------------------------------------------------- services
for svc in nativeforge-demo-preview nativeforge-backend nativeforge-mayhem-tunnel; do
  state="$(systemctl --user is-active "${svc}.service" 2>/dev/null || echo unknown)"
  if [ "$state" = "active" ]; then
    pass "service_active:${svc}" "$state"
  else
    fail "service_active:${svc}" "$state"
  fi
done

# ---------------------------------------------------------------- local
c="$(code "$PREVIEW/")"
[ "$c" = "200" ] && pass local_frontend "http=$c" || fail local_frontend "http=$c"

c="$(code "$BACKEND/backend/health")"
[ "$c" = "200" ] && pass local_backend_health "http=$c" || fail local_backend_health "http=$c"

# A controlled API answer, not a 404. 404 would mean an OAuth redirect lands
# nowhere; the route is supposed to exist and refuse with a named reason.
c="$(code "$BACKEND$CALLBACK_PATH")"
if [ "$c" = "200" ]; then
  if body "$BACKEND$CALLBACK_PATH" | grep -q '"route"'; then
    pass local_callback_controlled "http=$c"
  else
    fail local_callback_controlled "http=$c body_not_api_envelope"
  fi
else
  fail local_callback_controlled "http=$c"
fi

# ---------------------------------------------------------------- public
DEMO_URL="$PUBLIC_ORIGIN/?view=sc_customer_demo"
demo_code="$(code "$DEMO_URL")"
demo_body="$(body "$DEMO_URL")"

# 1033 is fatal wherever it appears. Cloudflare serves it with a 5xx status and
# names it in the body, so both are checked.
#
# Any 5xx fails, not a named list of them. An earlier version here enumerated
# 530/502/000 and let a 525 through as PASS while the origin was unreachable -
# a check that reported healthy for a broken edge, which is worse than no check.
# Cloudflare has a whole family of 52x origin errors and this must not depend on
# having listed the right ones.
if echo "$demo_body" | grep -qiE "error 1033|argo tunnel error|tunnel error"; then
  fail public_demo_not_1033 "http=$demo_code error_1033_in_body"
elif [ "$demo_code" = "000" ] || [ "${demo_code:0:1}" = "5" ]; then
  fail public_demo_not_1033 "http=$demo_code"
else
  pass public_demo_not_1033 "http=$demo_code"
fi

# An Access 302 is the correct unauthenticated answer for the demo surface. It
# is not an error, and it is not proof the page renders - only that the edge
# reached something.
if [ "$demo_code" = "302" ] || [ "$demo_code" = "303" ]; then
  pass public_demo_reachable "http=$demo_code access_redirect"
elif [ "$demo_code" = "200" ]; then
  pass public_demo_reachable "http=$demo_code"
else
  fail public_demo_reachable "http=$demo_code"
fi

# The callback must reach the API. Not Access, not 1033. A browser arriving from
# a provider carries no Access session, so an Access redirect here breaks OAuth.
CB_URL="$PUBLIC_ORIGIN$CALLBACK_PATH"
cb_code="$(code "$CB_URL")"
cb_body="$(body "$CB_URL")"

if echo "$cb_body" | grep -qiE "error 1033|argo tunnel error"; then
  fail public_callback_reaches_api "http=$cb_code error_1033"
elif [ "$cb_code" = "302" ] || [ "$cb_code" = "303" ]; then
  fail public_callback_reaches_api "http=$cb_code access_redirect_would_break_oauth"
elif [ "$cb_code" = "200" ] && echo "$cb_body" | grep -q '"route"'; then
  pass public_callback_reaches_api "http=$cb_code"
else
  fail public_callback_reaches_api "http=$cb_code"
fi

# ---------------------------------------------------------------- edge health
conns="$(curl -s --max-time 10 http://127.0.0.1:20242/metrics 2>/dev/null \
  | awk '/^cloudflared_tunnel_ha_connections/ {print $2}' | head -1)"
conns="${conns:-0}"
# A registered connector is what the hostname resolves to. Zero is 1033 waiting
# to happen, and it is only visible from here.
if [ "${conns%.*}" -ge 1 ] 2>/dev/null; then
  pass tunnel_edge_connections "n=${conns%.*}"
else
  fail tunnel_edge_connections "n=${conns%.*}"
fi

echo
if [ -z "$FAILED" ]; then
  echo "RESULT=PASS"
  exit 0
fi
echo "RESULT=FAIL"
echo "failed_check=$FAILED"
exit 1
