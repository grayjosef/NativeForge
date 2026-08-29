# 633 — Gate 116B: the session cookie policy

`src/nativeforge/services/customer_session_cookie_policy_service.py`

What a NativeForge session cookie must be, decided before any session exists.

## A policy is not a session

This service defines attributes. It sets no cookie, mints no session value and
knows nothing about any user. `sessions_live` is a constant `False` with an
invariant behind it, because "we have a session cookie policy" is one short step
from "we have sessions" and the two are unrelated.

Gate 116A found **zero cookie handling anywhere in NativeForge** — no
`set_cookie`, no `SameSite`, no `Response` import in the whole `api/` package.
Nothing constrained this policy, which is also why nothing excused getting it
wrong.

## The policy

```text
cookie_name           nf_session
http_only             true
secure                follows the environment; false in local dev
same_site             lax
path                  /
domain                none (host-only)
max_age_seconds       28800  (8 hours, ceiling 604800)
csrf_required         true
state_required        true
pkce_required         true
rotation_required     true
logout_clears_cookie  true
production_safe       false in local dev, true in production
```

## Why `lax` rather than `strict`

The browser arrives at `/api/auth/callback` from the identity provider's origin.
`strict` would not send the cookie on that navigation and the callback would
arrive without it. `lax` sends cookies on top-level GET navigations, which is
exactly what a callback is.

`none` is absent from the vocabulary entirely: it requires `Secure` and permits
the cookie on cross-site subrequests, which is the property CSRF depends on. A
policy asking for it is refused with a named reason.

## Why PKCE is required

The brief permits `pkce_required: false` if the existing OIDC flow proves it
unnecessary. Gate 116A searched every service module:

```text
pkce  0    code_verifier  0    code_challenge  0
authorization_url  0    token_exchange  0
```

There is no existing flow. An absent flow proves nothing, and "no evidence
against" is not evidence for. PKCE stays required, and the reasoning travels
with the policy in a `pkce_rationale` field rather than living only here.

## production_safe is derived, and currently false

```python
production_safe = (
    http_only and secure and same_site in {"lax", "strict"}
    and csrf_required and state_required and pkce_required
    and rotation_required and logout_clears_cookie
    and 0 < max_age_seconds <= MAX_SESSION_SECONDS
)
```

`secure` follows `settings.app_env`, so the local-development policy is honestly
not production-safe rather than pretending to be — with the reason named:
`cookie_not_marked_secure_so_not_production_safe`.

A test forces `app_env="production"` and asserts `production_safe` becomes true.
Without that, today's `false` would be indistinguishable from a constant.

## What logout actually does

`/api/auth/logout` calls `Response.delete_cookie` with the policy's own name,
path, domain, `HttpOnly`, `Secure` and `SameSite`. The header it emits carries an
expiry and an empty value:

```text
nf_session=""; expires=...; HttpOnly; Max-Age=0; Path=/; SameSite=lax
```

A value is never written — only an expiry.
