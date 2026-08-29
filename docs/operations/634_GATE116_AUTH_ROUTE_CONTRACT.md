# 634 — Gate 116C/D: the auth route contract and the routes

```text
src/nativeforge/services/customer_auth_route_contract_service.py
src/nativeforge/api/auth.py
```

Five endpoints that authenticate nobody, and a contract stating exactly what
each is permitted to do.

## The routes

```text
GET  /api/auth/login          auth_not_configured
GET  /api/auth/callback       callback_validation_not_passed
POST /api/auth/logout         no_live_session, cookie cleared
GET  /api/auth/session        unauthenticated
GET  /api/auth/current-user   unauthenticated
```

The application now serves 183 routes, up from 178. Every auth response carries
`customer_auth_live` and `login_live` read from Gate 115's activation gate — both
false — plus that gate's own `blocked_reasons` and `next_required_actions`, so a
route can never disagree with the gate about why auth is unavailable.

## Why write a contract for routes that do nothing

A route that exists and does nothing is the easiest thing in a codebase to
quietly widen later. The contract states, per route and before the code, which of
five dangerous things each one may do:

```text
route          provider_call  session  state  pkce  org_resolution  membership
login          flow only      no       yes    yes   no              no
callback       flow only      ONLY     yes    yes   yes             yes
logout         no             no       no     no    no              no
session        no             no       no     no    no              no
current-user   no             no       no     no    yes             yes
```

Two rules are invariants rather than conventions:

**Only `callback` may ever mint a session**, and only once provider
configuration, callback validation, `organization_id` resolution and membership
verification have all passed. A forged contract row where any other route
creates a session fails with `non_callback_route_creates_a_session`.

**A provider call may only come from the redirect flow.** `login` and `callback`
may reach an identity provider once one is configured; nothing else in
NativeForge has a reason to.

## safe_without_provider

Every route can answer honestly with no configuration at all. That is what makes
registering them safe: a route that hung, crashed or half-completed when asked
would turn a contract gate into an outage.

`/login` returns a structured refusal rather than a redirect — redirecting to an
unconfigured issuer produces a browser error page with no explanation, and a 500
would suggest a bug rather than a missing configuration.

## Why `/logout` is different

It is the only route permitted to act while auth is not live. Clearing a cookie
is safe whether or not one exists, and refusing on the grounds that there is no
session would leave a stale cookie behind on exactly the path somebody uses to
get rid of one.

`POST` rather than `GET`, so a link or an image tag cannot log a user out.

## What these routes deliberately do not do

**They do not use the org context dependency.** Sixteen route modules obtain an
organization through `deps_db.get_org_context_with_db` and the `X-NF-Org-Id`
header. These five do not, and a test asserts it by reading the source: they are
what should eventually replace that header, and a replacement that depends on
the thing it replaces is not one.

**They set no RLS context.** `apply_org_rls_gucs` is never called from
`api/auth.py`.

**`/current-user` reports `organization_id: None`** and keeps reporting it until
Gate 112's resolution plus a verified membership say otherwise. A route
reporting an organization from an unverified claim would be the exact defect
Gates 110 through 113 exist to prevent.

## The security scheme is advertised, not applied

`install_auth_security_scheme` post-processes the generated OpenAPI document to
add a `securitySchemes` entry, and attaches it to **no operation**:

```text
securitySchemes declared     nf_session_cookie
routes declaring security    NONE
route_auth_enforced          false
```

This is deliberate, and it is the distinction the whole gate turns on. FastAPI
emits `securitySchemes` only for schemes an operation actually depends on, so
declaring one that nothing enforces requires post-processing. Attaching it to
the auth routes would have flipped Gate 115C's `route_auth_enforced` to true
while those routes still answered everyone identically.

**A scheme in a document is documentation. Enforcement is a refusal, and nothing
refuses yet.**

## Secrets

No auth response contains a secret value. A test plants one in the environment
and asserts it appears in none of the five responses, and the artifact writer
refuses to write if a configured value appears in any file.
