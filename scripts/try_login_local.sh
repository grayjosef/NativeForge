#!/usr/bin/env bash
# Prove a Google sign-in can START, without signing anybody in.
#
# The gate's preflight reads os.environ DIRECTLY - it deliberately does not go
# through the Settings/.env overlay - so a developer whose credentials live in
# `.env` sees `provider_configured: false` locally while the same deployment
# on Railway, where the variables are real environment variables, would pass.
# This script exports them so the local run answers the question production
# would answer.
#
# It prints the status line and the redirect target with every sensitive
# parameter replaced. No credential is echoed, and nothing is signed in: the
# point is whether NativeForge can hand a browser to Google, which is the last
# step before a human would have to type a password.
set -u

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT" || exit 1

PORT="${PORT:-8100}"

pkill -f "uvicorn nativeforge.main:app --host 127.0.0.1 --port ${PORT}" 2>/dev/null
sleep 1

set -a
# shellcheck disable=SC1091
. ./.env
set +a

export NF_SESSION_SIGNING_KEY="$(openssl rand -hex 32)"
export NF_OIDC_DISCOVERY_ENABLED=true
export OIDC_AUDIENCE="${OIDC_AUDIENCE:-$OIDC_CLIENT_ID}"
export NF_PUBLIC_ORIGIN="http://127.0.0.1:${PORT}"
export OIDC_CALLBACK_URL="${NF_PUBLIC_ORIGIN}/api/auth/callback/google"

mkdir -p logs
setsid nohup .venv/bin/python -m uvicorn nativeforge.main:app \
  --host 127.0.0.1 --port "${PORT}" \
  > "logs/dev_api_auth_${PORT}.log" 2>&1 < /dev/null &

sleep 9

echo "--- providers ---"
curl -s -m 20 "http://127.0.0.1:${PORT}/api/auth/providers" \
  | python3 -c 'import json,sys; d=json.load(sys.stdin); print({p["key"]: p["configured"] for p in d["providers"]})'

echo "--- login initiation ---"
curl -s -m 30 -D - -o /dev/null "http://127.0.0.1:${PORT}/api/auth/login?provider=google" \
  | grep -iE '^HTTP|^location' \
  | sed -E 's/(client_id=)[^&[:space:]]*/\1<redacted>/g; s/(state=)[^&[:space:]]*/\1<redacted>/g; s/(code_challenge=)[^&[:space:]]*/\1<redacted>/g'
