#!/usr/bin/env bash
# Gate 37 restart/verifier drill. Does not start cloudflared or linger.
# Default: print steps. Pass --run to restart the user unit if installed.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "=== NativeForge demo restart / verifier drill ==="
echo "listener=127.0.0.1:5175"
echo "logs: journalctl --user -u nativeforge-demo-preview.service -n 80 --no-pager"
echo
echo "1. Verifier before restart"
echo "2. systemctl --user restart nativeforge-demo-preview.service (if enabled)"
echo "3. Verifier after restart"
echo "4. Fail-closed: unstamped dist / missing manifest / port collision must refuse serve"
echo "5. Do not bind public addresses. Do not start a public tunnel."
echo

if [[ "${1:-}" != "--run" ]]; then
  echo "docs-only (pass --run to execute restart if the user unit is installed)"
  exit 0
fi

VERIFY="$ROOT/scripts/verify_nativeforge_demo_deployment.sh"
echo "--- verifier before ---"
set +e
"$VERIFY"
BEFORE=$?
set -e
echo "before_exit=${BEFORE}"

if systemctl --user is-enabled nativeforge-demo-preview.service >/dev/null 2>&1; then
  systemctl --user restart nativeforge-demo-preview.service
  echo "restarted nativeforge-demo-preview.service"
  sleep 1
else
  echo "user unit not enabled; skip restart (install with scripts/install_nativeforge_demo_user_unit.sh)"
fi

echo "--- verifier after ---"
set +e
"$VERIFY"
AFTER=$?
set -e
echo "after_exit=${AFTER}"
if [[ "$AFTER" -ne 0 ]]; then
  echo "RESULT=FAIL"
  exit 1
fi
echo "RESULT=PASS"
