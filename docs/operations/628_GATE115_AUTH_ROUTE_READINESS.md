# 628 — Gate 115C: auth route readiness

`src/nativeforge/services/customer_auth_route_readiness_service.py`

Does NativeForge have the routes a customer login flow needs, and do they
enforce anything?

## Measured, not grepped

Read from the running applications own OpenAPI schema:

```text
routes in the schema        178
auth-shaped routes          NONE
securitySchemes declared    NONE
routes declaring security   NONE
```

Not one of the 178 endpoints requires a credential.

A service that grepped for the string "login" would report a route a comment
mentions and miss one mounted under an unexpected prefix. This one reads the
route table the application actually serves.

## Existence is not enforcement

```text
route_available    is there an endpoint at all?
route_enforced     does reaching it require anything?
```

A route that exists and enforces nothing is worse than no route, because it
looks like progress. A test supplies five auth routes that declare no security
scheme and asserts `route_auth_enforced` stays false while every
`*_route_available` is true.

## Three things that are not customer app auth

Each is reported as its own constant so it can never be counted as one:

```text
cloudflare_access_is_customer_auth      false
frontend_preview_is_backend_login       false
dev_header_is_customer_auth             false
```

**Cloudflare Access** gates who reaches the tunnel. It establishes no
NativeForge principal, organization or role, and a route behind it is still a
route with no credential requirement. It is added to `blocked_reasons` as a
named refusal rather than omitted, so nobody reads its absence as coverage.

**The frontend preview** is a served page, not a backend session.

## One exclusion that would otherwise have lied

`/docs/oauth2-redirect` is in the raw route list. It is FastAPIs Swagger UI
helper, not a NativeForge callback, and matching it would have made
`callback_route_available` true today. Framework routes are excluded by prefix
and a test pins the behaviour.

## Reachability

The schema is injectable. A test supplies an application that does have five
auth routes and a declared security scheme, and asserts `ready_for_live_login`
becomes true — otherwise every `available: false` above would be unfalsifiable.
