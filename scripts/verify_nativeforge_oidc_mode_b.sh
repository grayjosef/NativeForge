#!/usr/bin/env bash
# OIDC Mode B readiness verifier. Prints RESULT=PASS|FAIL.
#
#   (default)  missing OIDC config is a STATE, not a failure. The demo runs
#              without OIDC and must keep running.
#   --strict   live-readiness gate: missing config FAILS CLOSED.
#
# Never prints an env var value. Presence booleans only.
# Performs no network I/O and does not fetch JWKS.
#
# Canonical env names are OIDC_* (repo convention). NATIVEFORGE_OIDC_* is
# accepted as an alias. See docs/operations/374_GATE59_OIDC_MODE_B_READINESS.md
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

STRICT=0
for arg in "$@"; do
  case "$arg" in
    --strict) STRICT=1 ;;
    -*) echo "unknown flag: $arg" >&2; exit 2 ;;
  esac
done
if [[ "${NF_OIDC_STRICT:-0}" == "1" ]]; then
  STRICT=1
fi

# shellcheck disable=SC1091
source .venv/bin/activate 2>/dev/null || true

STRICT_FLAG="False"
[[ "$STRICT" -eq 1 ]] && STRICT_FLAG="True"

python3 - "$STRICT_FLAG" <<'PY'
import sys

from nativeforge.services.oidc_readiness_service import (
    build_oidc_readiness,
    oidc_readiness_invariant_failures,
)

strict = sys.argv[1] == "True"
r = build_oidc_readiness(strict=strict)

print(f"mode={r['mode']}")
print(f"readiness_state={r['readiness_state']}")

# Presence booleans only. No values are read or printed.
for key, present in sorted(r["config_present"].items()):
    print(f"check=config_present_{key} status={'PASS' if present else 'ABSENT'}")

print(f"check=config_complete status={'PASS' if r['config_complete'] else 'NO'}")
print(f"check=token_verification_implemented status={'YES' if r['token_verification_implemented'] else 'NO'}")
print(f"check=local_token_verification_passed status={'YES' if r['local_token_verification_passed'] else 'NO'}")
print(f"check=live_auth0_token_proven status={'YES' if r['live_auth0_token_proven'] else 'NO'}")
print(f"check=verification_possible status={'PASS' if r['verification_possible'] else 'NO'}")
print(f"check=network_access_attempted status={'NO' if not r['network_access_attempted'] else 'YES'}")
print(f"check=jwks_fetched status={'NO' if not r['jwks_fetched'] else 'YES'}")
print("check=login_live_claimed status=FALSE")
print("check=customer_login_live_claimed status=FALSE")
print("check=secret_values_read status=FALSE")

for reason in r["blocked_reasons"]:
    print(f"blocked_reason={reason}")

fails = oidc_readiness_invariant_failures(r)
if fails:
    for f in fails:
        print(f"check=invariant status=FAIL detail={f}")
    print("RESULT=FAIL")
    raise SystemExit(1)
print("check=invariants status=PASS")

print("note=cloudflare_access_is_not_customer_login")
print("note=config_presence_is_not_verification")
print("note=local_keypair_tests_prove_the_code_not_the_integration")

if strict and not r["ok"]:
    print("RESULT=FAIL")
    raise SystemExit(1)

print("RESULT=PASS")
raise SystemExit(0)
PY
RC=$?
exit "$RC"
