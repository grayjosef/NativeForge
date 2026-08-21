# Auth0 Live Validation Runbook (Gate 19 / Block 43)

> Note: Doc number `223` (215–217 were already used by Gate 17).

## Purpose

Owner-executed Auth0/OIDC validation the moment out-of-band config exists.
Without config, login remains blocked.

## Mode A (no secrets)

1. Run preflight — expect `BLOCKED`, `validation_possible=false`.
2. Run live validation runner — expect `dry_run`.
3. Promotion gate — expect `login_live_claimed=false`.

```bash
source .venv/bin/activate
python -c "from nativeforge.services.auth0_preflight_service import run_auth0_preflight; import json; print(json.dumps(run_auth0_preflight(), indent=2))"
bash scripts/campaign_block43_smoke_verify.sh
```

## Mode B (owner sets OIDC_* out-of-band)

Set presence-only env vars outside git:

- `OIDC_ISSUER`
- `OIDC_CLIENT_ID`
- `OIDC_CLIENT_SECRET` (never commit / never print)
- `OIDC_CALLBACK_URL`
- optional: `OIDC_AUDIENCE`, `OIDC_LOGOUT_URL`, `OIDC_ALLOWED_ORIGIN`

Then re-run preflight → guarded live runner → promotion gate.
`login_live` unlocks only when every required gate passes.

## Hard rules

- Never print secrets.
- Dry-run is default.
- Missing invite/org/role/RBAC/tenant/audit blocks login live.
- Unverified email blocks customer context unless explicit policy allows it.
