# Customer auth route enforcement readiness (Gate 117)

`/api/auth/current-user` now returns **401** to an unauthenticated caller - the first refusal NativeForge has ever issued. **Customer auth is not live and login is not live.** The route refuses everybody, because nobody can authenticate.

## Enforcement is not liveness

```text
route_auth_enforced                  true
secured_route_count                  1
route_org_resolution_enforced        false
route_role_mapping_enforced          false
ready_for_live_login                 false
customer_auth_live                   false
```

A 401 proves the application can say no. It proves nothing about whether anyone could ever be told yes, and a 401 is not an organization - nothing resolves one, so organization-resolution and role-mapping enforcement stay false.

## The four contracts this gate added

```text
auth dependency        four modes: required, optional, forbid, unknown
redirect flow          nine steps, refusing at each one it cannot take
state and PKCE         real entropy, S256, constant-time comparison
token exchange         six conditions, one of them the network itself
```

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
```

Enforcement moved none of them. Not one is a route fact, which is exactly why this gate could add a refusal without moving a single activation gate.

## No credential reaches this directory

The state and PKCE artifact carries fixture values prefixed `nf-demo-fixture-`, short enough to fail their own entropy checks. No real state, verifier, token or secret is written. Token exchange is behind `network_call_allowed`, which defaults to false and which nothing in this repository raises.

## What is true

```text
auth_dependency_contract_available           true
redirect_flow_contract_available             true
state_pkce_contract_available                true
token_exchange_boundary_available            true
```

## Claims this gate does not make

```text
beta_onboarding_ready                        false
customer_auth_live                           false
customer_persistence_live                    false
login_live                                   false
provider_called                              false
real_sessions_created                        false
real_users_created                           false
secrets_exposed                              false
```

No identity provider was contacted, no network call was made, no user or session was created, no token was requested, no URL was fetched, no collector ran and no source was monitored.

