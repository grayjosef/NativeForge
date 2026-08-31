# Gate 129 — demo live summary

## The demo

```text
url            https://nf-dev.mayhem-nc.dev/?view=sc_customer_demo
served by      cloudflared -> 127.0.0.1:5175 (stamped Vite preview)
public edge    Cloudflare Access on every path
visible today  yes, to anyone who can pass Access
```

## What is on it now

An operating shell with 10 sections and
6 active truth labels, all computed rather
than typed. Sections operational: 0. Rows
written to any customer table: 0.

## The API

```text
service        nativeforge-backend.service (existing unit, started not enabled)
bind           127.0.0.1:8000, loopback only
/backend/health            200
/api/auth/current-user     401 unauthenticated
/api/auth/callback         200 controlled refusal, not 404
```

The tunnel now routes `/api/*` to the API ahead of the static catch-all, so the
callback path resolves to something that can consume a callback.

## The public edge, measured

```text
/                        302 -> cloudflareaccess.com
/backend/health          302 -> cloudflareaccess.com
/api/does-not-exist      302 -> cloudflareaccess.com
/api/auth/login          302 -> cloudflareaccess.com
/api/auth/session        302 -> cloudflareaccess.com
/api/auth/current-user   302 -> cloudflareaccess.com
/api/auth/callback       200    API JSON, callback_validation_not_passed
```

Exactly one path is exempt from Cloudflare Access, and it is the callback. An
Access bypass scoped to `/api/auth/callback` already exists — this gate did not
add it.

That exemption is what makes OAuth possible: a browser arriving from a provider
carries no Access session for this host, so without it the redirect would land
on a login page instead of the API.

Nothing here is blocked on Cloudflare. Gate 130 needs a provider and its seven
env values.

## Status

```text
customer_auth_live        False
login_live                False
provider_ready            False
object store configured   False
live source monitoring    False
email delivery            False
```

Auth env keys configured: 0 of 7. Names
only; no value is recorded in any artifact.
