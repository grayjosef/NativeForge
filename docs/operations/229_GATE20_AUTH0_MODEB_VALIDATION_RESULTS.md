# Gate 20 Auth0 Mode B Validation Results

> Doc `229` (requested `226` was already Gate 19 Block 43 spec).

## Mode detected (this run)

**Mode A** — owner Auth0 secrets / invite/org/role / live flag absent.

| Check | Result |
|-------|--------|
| Auth0 config present | false |
| Secret present | false |
| Live validation possible | false |
| Live validation attempted | false |
| Provider validated | false |
| Callback/session validated | false |
| Login live claim | false |
| Production auth claim | false |
| Controlled pilot auth ready | false |

## Mode B rerun path

```bash
# Out-of-band only — never commit secrets
export OIDC_ISSUER=...
export OIDC_CLIENT_ID=...
export OIDC_CLIENT_SECRET=...
export OIDC_CALLBACK_URL=...
export NF_AUTH0_LIVE_VALIDATION_ENABLED=1
# Also configure invite/org/role bindings in operator path
source .venv/bin/activate
bash scripts/campaign_block45_smoke_verify.sh
```

## Exact owner actions

1. Set OIDC_* env vars outside git.
2. Configure invite allowlist + org/role mapping.
3. Enable `NF_AUTH0_LIVE_VALIDATION_ENABLED=1`.
4. Re-run Block 45 smoke; unlock login_live only if every gate passes.
