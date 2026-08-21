# Gate 21 Auth0 Mode B Live Unlock Results

## Mode this run

**Mode A** — no OIDC_* owner config present out-of-band.

| Field | Value |
|-------|-------|
| Owner config present | false |
| Secret present flag | false |
| Live validation attempted | false |
| Provider validated | false |
| Callback/session validated | false |
| Login live claim | false |
| Production auth claim | false |
| Controlled pilot auth ready | false |

## Owner next actions

1. Set `OIDC_ISSUER`, `OIDC_CLIENT_ID`, `OIDC_CLIENT_SECRET`, `OIDC_CALLBACK_URL` out-of-band (never commit).
2. Configure invite allowlist + org/role mapping.
3. Set `NF_AUTH0_LIVE_VALIDATION_ENABLED=1`.
4. Re-run `bash scripts/campaign_block47_smoke_verify.sh`.

Login live unlocks only when every gate passes.
