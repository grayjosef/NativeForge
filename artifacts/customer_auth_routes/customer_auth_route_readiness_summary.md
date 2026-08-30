# Customer auth route readiness (Gate 116)

NativeForge now has five customer auth routes and a session cookie policy. **Customer auth is not live and login is not live.** Nothing on these routes authenticates anybody, and no session has been created.

## The routes

```text
login_route_available                true
callback_route_available             true
session_route_available              true
current_user_route_available         true
logout_route_available               true

application routes                   183
```

## Declared is not enforced

```text
security_scheme_declared             true
secured_route_count                  1
route_auth_enforced                  true
ready_for_live_login                 false
```

A security scheme is advertised in the OpenAPI document and attached to no operation. That is deliberate: a scheme in a document is documentation, and enforcement is a refusal. Nothing refuses yet.

## The session cookie policy

```text
cookie_name              'nf_session'
http_only                True
secure                   False
same_site                'lax'
path                     '/'
max_age_seconds          28800
csrf_required            True
state_required           True
pkce_required            True
rotation_required        True
logout_clears_cookie     True
production_safe          False
```

`secure` follows the environment, so a local development policy is honestly not production-safe rather than pretending to be. PKCE is required because nothing in this repository proves it unnecessary - there is no authorization-url builder, no token exchange and no code verifier anywhere, and an absent flow is not evidence.

## What still blocks activation

```text
provider_configured
secret_present
issuer_configured
issuer_jwks_validated
audience_configured
callback_session_validated
invite_binding_passed
org_binding_passed
role_mapping_passed
dev_header_disabled_for_production
session_signing_key_ready
```

This gate satisfied the two gates a route spine can satisfy. The remainder are provider configuration, secrets, validation of a real flow, and removing the dev org header - none of which a route supplies.

## The dev org header

```text
route modules using it               14
safe to disable now                  false
must disable before production auth  true
```

The auth routes existing does not make the header removable. A replacement is a route that can actually authenticate somebody, and none of these can yet. **Cloudflare Access is not customer app auth.**

## What is true

```text
auth_routes_contract_available           true
session_cookie_policy_available          true
```

## Claims this gate does not make

```text
beta_onboarding_ready                    false
customer_auth_live                       false
customer_persistence_live                false
login_live                               false
provider_called                          false
real_sessions_created                    false
real_users_created                       false
```

No identity provider was contacted, no network call was made, no user or session was created, no cookie carrying a session value was set, no URL was fetched, no collector ran and no source was monitored.

