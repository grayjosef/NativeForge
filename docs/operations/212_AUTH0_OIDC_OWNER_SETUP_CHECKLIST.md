# Auth0/OIDC Owner Setup Checklist (Gate 17 / Block 39)

## Warning

**Do not commit secrets. Do not paste client secrets into git, chat logs, or tickets.**

## Application type

* Regular Web Application (or SPA + confidential BFF — prefer BFF/server session)

## URLs to configure in Auth0

| Setting | Local/dev value |
|---------|-----------------|
| Allowed Callback URLs | `http://localhost:5173/auth/callback` |
| Allowed Logout URLs | `http://localhost:5173/auth/logout` |
| Allowed Web Origins | `http://localhost:5173` |
| Allowed Origins (CORS) | `http://localhost:5173` |

Staging/production URLs must be owner-approved before use.

## Scopes

`openid profile email`

## Audience / API

* Create API audience if using access tokens for `/api/*`
* Set `OIDC_AUDIENCE` only if required

## Environment variables (outside git)

```bash
export OIDC_ISSUER="https://YOUR_TENANT.auth0.com/"
export OIDC_CLIENT_ID="..."
export OIDC_CLIENT_SECRET="..."   # never commit
# optional:
export OIDC_AUDIENCE="..."
```

## Validation

1. Confirm env presence flags only (schema never stores secret values)
2. Run Block 39 smoke: `bash scripts/campaign_block39_smoke_verify.sh`
3. After real callback works, set validated only with owner sign-off
4. `login_live_claimed=true` only after callback + session + RBAC handoff proven

## Rollback

* Unset OIDC_* env vars
* Fall back to fixture/internal auth
* Keep invite status non-`sent`

## Login-live claim rules

* Missing secrets → login live **false**
* Configured but unvalidated → login live **false**
* Validated + callback green → owner may authorize login live claim
