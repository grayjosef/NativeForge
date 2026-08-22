#!/usr/bin/env bash
# Loopback (or NF_VERIFY_BASE_URL) deploy verifier. Prints RESULT=PASS|FAIL.
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
BASE="${1:-${NF_VERIFY_BASE_URL:-http://127.0.0.1:5175}}"
FAIL=0
BODY="/tmp/nf-gate36b-body"

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

if [[ "$FAIL" -eq 0 ]]; then
  echo "RESULT=PASS"
  exit 0
fi
echo "RESULT=FAIL"
exit 1
