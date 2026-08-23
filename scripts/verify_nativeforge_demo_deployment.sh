#!/usr/bin/env bash
# Loopback (or NF_VERIFY_BASE_URL) deploy verifier. Prints RESULT=PASS|FAIL.
#
# Modes:
#   (default)        loopback + artifact checks. Tunnel/config drift is reported
#                    as status=WARN but does not change PASS/FAIL.
#   --local-only     skip every tunnel/public check entirely.
#   --public         also probe the public edge; edge problems WARN.
#   --strict-public  demo-readiness gate: every tunnel, ingress and public-edge
#                    check becomes fail-affecting. Use this before a demo.
#
# Equivalent env: NF_VERIFY_STRICT_PUBLIC=1
#
# Gate 50. Rationale: on 2026-08-22 cloudflared held a stale ingress for ~5.5h
# and served HTTP 404 to every authenticated request, while this verifier
# reported RESULT=PASS the entire time. Loopback health plus an unauthenticated
# Access 302 does NOT prove the post-Access origin path.
#
# Never prints tunnel UUID, tunnel token, or credentials-file contents.
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

MODE="default"
BASE_ARG=""
for arg in "$@"; do
  case "$arg" in
    --local-only) MODE="local-only" ;;
    --public) MODE="public" ;;
    --strict-public) MODE="strict-public" ;;
    -*) echo "unknown flag: $arg" >&2; exit 2 ;;
    *) BASE_ARG="$arg" ;;
  esac
done
if [[ "${NF_VERIFY_STRICT_PUBLIC:-0}" == "1" ]]; then
  MODE="strict-public"
fi

BASE="${BASE_ARG:-${NF_VERIFY_BASE_URL:-http://127.0.0.1:5175}}"
PUBLIC_URL="${NF_PUBLIC_URL:-https://nf-dev.mayhem-nc.dev}"
EXPECT_HOSTNAME="${NF_EXPECT_HOSTNAME:-nf-dev.mayhem-nc.dev}"
EXPECT_ORIGIN="${NF_EXPECT_ORIGIN:-http://127.0.0.1:5175}"
CF_CONFIG="${HOME}/.cloudflared/config.yml"
# Pinned by ops/systemd/nativeforge-cloudflared.service (--metrics).
CF_METRICS="${NF_CF_METRICS:-127.0.0.1:20241}"

FAIL=0
BODY="/tmp/nf-gate36b-body"

STRICT=0
[[ "$MODE" == "strict-public" ]] && STRICT=1

# soft_check: FAIL in strict mode, WARN otherwise. Never silently passes.
soft_check() {
  local name="$1" ok="$2" detail="${3:-}"
  if [[ "$ok" == "1" ]]; then
    echo "check=${name} status=PASS ${detail}"
  elif [[ "$STRICT" -eq 1 ]]; then
    echo "check=${name} status=FAIL ${detail}"
    FAIL=1
  else
    echo "check=${name} status=WARN ${detail} (advisory; use --strict-public to enforce)"
  fi
}

check_http() {
  local name="$1"
  local url="$2"
  local code
  code="$(curl -sS -o "$BODY" -w '%{http_code}' "$url" 2>/dev/null || echo 000)"
  if [[ "$code" == "200" ]]; then
    echo "check=${name} status=PASS http=${code}"
  else
    echo "check=${name} status=FAIL http=${code}"
    FAIL=1
  fi
}

echo "verify_base=${BASE}"

HOME_HTML="/tmp/nf-gate36b-home.html"
check_http loopback_home_200 "${BASE}/"
cp -f "$BODY" "$HOME_HTML" 2>/dev/null || : > "$HOME_HTML"

check_http loopback_demo_route_200 "${BASE}/?view=sc_customer_demo"
check_http loopback_health_200 "${BASE}/health"
check_http loopback_version_200 "${BASE}/version"

# shellcheck disable=SC1091
source .venv/bin/activate
set +e
python3 - "$ROOT" "$HOME_HTML" <<'PY'
import sys
from pathlib import Path

from nativeforge.services.gate36b_dev_domain_deployment_machinery_service import (
    claim_boundary_preserved,
    count_build_sha_metas,
)

root = Path(sys.argv[1])
html_path = Path(sys.argv[2])
html = html_path.read_text(encoding="utf-8") if html_path.is_file() else ""
n = count_build_sha_metas(html)
ok = True
if n == 1:
    print("check=identity_meta_present status=PASS")
    print("check=identity_meta_single status=PASS")
elif n < 1:
    print("check=identity_meta_present status=FAIL")
    print("check=identity_meta_single status=FAIL")
    ok = False
else:
    print("check=identity_meta_present status=PASS")
    print("check=identity_meta_single status=FAIL")
    ok = False

manifest = root / "frontend" / "dist" / "build-manifest.json"
if manifest.is_file():
    print("check=manifest_present status=PASS")
else:
    print("check=manifest_present status=FAIL")
    ok = False

serve = (root / "scripts" / "serve_frontend_preview_5175.sh").read_text(
    encoding="utf-8"
)
unit = (root / "ops" / "systemd" / "nativeforge-demo-preview.service").read_text(
    encoding="utf-8"
)
loop_ok = (
    "127.0.0.1" in serve
    and "--host 127.0.0.1" in serve
    and "0.0.0.0" not in serve
    and "127.0.0.1:5175" in unit
)
if loop_ok:
    print("check=listener_loopback_documented status=PASS")
else:
    print("check=listener_loopback_documented status=FAIL")
    ok = False

if claim_boundary_preserved(html):
    print("check=claim_boundary_preserved status=PASS")
else:
    print("check=claim_boundary_preserved status=FAIL")
    ok = False

raise SystemExit(0 if ok else 1)
PY
PY_RC=$?
set -e
if [[ "$PY_RC" -ne 0 ]]; then
  FAIL=1
fi

# ─────────────── Gate 50: tunnel / ingress / public edge ───────────────
echo "verify_mode=${MODE}"

if [[ "$MODE" == "local-only" ]]; then
  echo "check=tunnel_checks status=SKIP (--local-only)"
else

  # Runtime loopback-only listener check. The pre-existing
  # listener_loopback_documented check only greps the scripts; this asserts the
  # actual running socket, and that 5175 is not exposed on a public interface.
  if command -v ss >/dev/null 2>&1; then
    LISTENERS="$(ss -ltn 2>/dev/null | grep ':5175 ' || true)"
    if [[ -z "$LISTENERS" ]]; then
      soft_check listener_5175_present 0 "no socket listening on 5175"
    elif echo "$LISTENERS" | grep -qE '0\.0\.0\.0:5175|\[::\]:5175'; then
      echo "check=listener_loopback_only status=FAIL 5175 bound to a public interface"
      FAIL=1
    else
      echo "check=listener_loopback_only status=PASS 127.0.0.1:5175"
    fi
  else
    soft_check listener_loopback_only 0 "ss unavailable"
  fi

  # cloudflared process present.
  if pgrep -x cloudflared >/dev/null 2>&1; then
    echo "check=cloudflared_process status=PASS"
  else
    soft_check cloudflared_process 0 "no cloudflared process"
  fi

  # Tracked user unit, if installed.
  if systemctl --user cat nativeforge-cloudflared.service >/dev/null 2>&1; then
    if systemctl --user is-active --quiet nativeforge-cloudflared.service; then
      echo "check=cloudflared_unit_active status=PASS"
    else
      soft_check cloudflared_unit_active 0 "unit installed but not active"
    fi
  else
    echo "check=cloudflared_unit_active status=SKIP (unit not installed)"
  fi

  # Tunnel readiness endpoint, when the metrics server is up.
  CF_READY="$(curl -sS --max-time 5 http://${CF_METRICS}/ready 2>/dev/null || true)"
  if [[ -n "$CF_READY" ]]; then
    READY_N="$(echo "$CF_READY" | grep -oE '"readyConnections":[0-9]+' | grep -oE '[0-9]+' || echo 0)"
    if [[ "${READY_N:-0}" -ge 1 ]]; then
      echo "check=cloudflared_ready_connections status=PASS n=${READY_N}"
    else
      soft_check cloudflared_ready_connections 0 "n=${READY_N:-0}"
    fi
  else
    echo "check=cloudflared_ready_connections status=SKIP (metrics endpoint unavailable)"
  fi

  # Ingress config: sanitized hostname/service assertions only.
  if [[ -f "$CF_CONFIG" ]]; then
    echo "check=cloudflared_config_present status=PASS"
    if grep -qE "^[[:space:]]*-?[[:space:]]*hostname:[[:space:]]*${EXPECT_HOSTNAME}[[:space:]]*$" "$CF_CONFIG"; then
      echo "check=ingress_hostname_present status=PASS ${EXPECT_HOSTNAME}"
    else
      soft_check ingress_hostname_present 0 "${EXPECT_HOSTNAME} not in config"
    fi
    if grep -qE "^[[:space:]]*service:[[:space:]]*${EXPECT_ORIGIN//\//\\/}[[:space:]]*$" "$CF_CONFIG"; then
      echo "check=ingress_origin_present status=PASS ${EXPECT_ORIGIN}"
    else
      soft_check ingress_origin_present 0 "${EXPECT_ORIGIN} not in config"
    fi

    # Drift: config edited after the running process started means the live
    # ingress is stale. This is the exact 2026-08-22 outage.
    CF_PID="$(pgrep -x cloudflared | head -1 || true)"
    if [[ -n "$CF_PID" ]]; then
      CFG_MTIME="$(stat -c %Y "$CF_CONFIG" 2>/dev/null || echo 0)"
      PROC_START="$(date -d "$(ps -o lstart= -p "$CF_PID" 2>/dev/null)" +%s 2>/dev/null || echo 0)"
      if [[ "$CFG_MTIME" -gt 0 && "$PROC_START" -gt 0 && "$CFG_MTIME" -gt "$PROC_START" ]]; then
        soft_check ingress_config_not_stale 0 \
          "config.yml modified $((CFG_MTIME - PROC_START))s AFTER cloudflared started — restart the tunnel"
      else
        echo "check=ingress_config_not_stale status=PASS"
      fi
    else
      echo "check=ingress_config_not_stale status=SKIP (no running process)"
    fi
  else
    soft_check cloudflared_config_present 0 "missing ${CF_CONFIG}"
  fi

  # Public edge. Unauthenticated must be an Access 302, never a Cloudflare
  # origin error. 502/503/504/521/522/523/525/530 (error 1033) all mean the
  # tunnel or origin path is broken.
  if [[ "$MODE" == "public" || "$MODE" == "strict-public" ]]; then
    PUB_HDR="/tmp/nf-gate50-public-hdr"
    PUB_CODE="$(curl -sS -o /dev/null -D "$PUB_HDR" -w '%{http_code}' \
      --max-redirs 0 --max-time 20 "${PUBLIC_URL}/?view=sc_customer_demo" 2>/dev/null || echo 000)"
    case "$PUB_CODE" in
      302|303)
        LOC_HOST="$(grep -i '^location:' "$PUB_HDR" 2>/dev/null | sed -E 's#^[Ll]ocation:[[:space:]]*(https?://[^/]+).*#\1#' | tr -d '\r')"
        if echo "$LOC_HOST" | grep -q 'cloudflareaccess\.com'; then
          echo "check=public_access_redirect status=PASS http=${PUB_CODE} host=${LOC_HOST}"
        else
          soft_check public_access_redirect 0 "http=${PUB_CODE} unexpected redirect host=${LOC_HOST}"
        fi
        ;;
      502|503|504|521|522|523|525|526|530)
        echo "check=public_edge_origin_error status=FAIL http=${PUB_CODE} (Cloudflare origin/tunnel error, e.g. 1033)"
        FAIL=1
        ;;
      404)
        echo "check=public_edge_origin_error status=FAIL http=404 (ingress not matching — likely stale tunnel config)"
        FAIL=1
        ;;
      000)
        soft_check public_edge_reachable 0 "no response from ${PUBLIC_URL}"
        ;;
      *)
        soft_check public_access_redirect 0 "http=${PUB_CODE} (expected 302 to Cloudflare Access)"
        ;;
    esac

    if grep -qi '^server:[[:space:]]*cloudflare' "$PUB_HDR" 2>/dev/null; then
      echo "check=public_cloudflare_header status=PASS"
    else
      soft_check public_cloudflare_header 0 "no cloudflare server header"
    fi
    rm -f "$PUB_HDR"
  else
    echo "check=public_edge status=SKIP (pass --public or --strict-public)"
  fi
fi

# NOTE: an unauthenticated 302 proves the edge and Access are up. It does NOT
# prove the post-Access origin path. Only a human with a valid Access session
# can confirm the demo actually renders.
echo "note=post_access_render_requires_human_confirmation"

if [[ "$FAIL" -eq 0 ]]; then
  echo "RESULT=PASS"
  exit 0
fi
echo "RESULT=FAIL"
exit 1
