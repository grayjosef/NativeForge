# Customer session and state readiness (Gate 118)

NativeForge now has a session format, a verifier and a redirect state store contract. **No production session exists, customer auth is not live, and login is not live.** No signing key is configured, so no cookie can verify.

## A contract is not a session

```text
session format contract                true
session verifier contract              true
redirect state store                   true
signing key configured                 false
any cookie verifies today              false
state store is production              false
customer auth live                     false
login live                             false
```

The first three are true and the rest are false. Gate 117's verifier reported `session_cookie_valid: false` because nothing could be checked; it now reports false because the check runs and fails - there is no key to check against.

## The state store is contract-only

Scope is `contract_only`: nothing is stored anywhere. An `in_memory_test` scope exists for tests and is a dict that dies with the process, which disqualifies it for a deployment with more than one worker. `database` is the only production scope and no table was added - it would be a table nothing writes to.

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

A session format moved none of them. Not one is a session-format fact.

## No credential reaches this directory

No session cookie, state value, PKCE verifier or signing key is committed. The writer refuses on three independent checks: nested field names, fixture values by content, and every configured `OIDC_*` environment value.

## What is true

```text
redirect_state_store_contract_available          true
session_format_contract_available                true
session_verifier_contract_available              true
```

## Claims this gate does not make

```text
beta_onboarding_ready                            false
customer_auth_live                               false
customer_persistence_live                        false
login_live                                       false
production_sessions_created                      false
real_secrets_exposed                             false
real_users_created                               false
session_cookie_valid_actual_environment          false
state_store_production                           false
```

No identity provider was contacted, no network call was made, no user or production session was created, no database table was added, no URL was fetched, no collector ran and no source was monitored.

