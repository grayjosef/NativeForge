# Customer auth activation readiness (Gate 115)

A customer auth **activation boundary** exists. **Customer auth is not live and login is not live.** No route in this application requires a credential, no identity provider is configured, and nobody has authorized activation.

## The gates

```text
satisfied  5 of 15

missing    audience_configured
missing    callback_session_validated
missing    dev_header_disabled_for_production
missing    invite_binding_passed
missing    issuer_configured
missing    issuer_jwks_validated
missing    org_binding_passed
missing    provider_configured
missing    role_mapping_passed
missing    secret_present
```

## What lifts each one

```text
provider_configured
    owner sets the OIDC_* environment variables out-of-band; this gate never stores or receives them
secret_present
    owner supplies OIDC_CLIENT_SECRET out-of-band; presence is detected, the value is never read into any output
issuer_configured
    owner sets OIDC_ISSUER
issuer_jwks_validated
    run the existing live validation path once configuration exists; no network check happens before then, so this is unvalidated rather than failed
audience_configured
    owner sets OIDC_AUDIENCE
callback_session_validated
    validate a real callback and session once the route exists
invite_binding_passed
    validate invite binding against a real flow
org_binding_passed
    validate that a verified claim resolves to an organization_id and a membership record - Gate 112's contract, exercised for real
role_mapping_passed
    configure provider roles and map them explicitly; unknown roles grant nothing by design
dev_header_disabled_for_production
    replace X-NF-Org-Id with an authenticated claim, then disable it; 16 route modules depend on it today
owner_approval
    owner sets NF_CUSTOMER_AUTH_ACTIVATION_APPROVAL out-of-band. Every gate passing is necessary and not sufficient: configuration arriving in an environment is not a decision to expose a login page to real Tribes.
```

## Three things that are not customer app auth

```text
Cloudflare Access    gates who reaches the tunnel; establishes no NativeForge principal, organization or role
the frontend preview a served page is not a backend session
X-NF-Org-Id          UUID-validated and existence-checked, and it establishes nothing about who is asking
```

## The dev header

```text
enabled by default                    true
route modules depending on it         15
safe to disable now                   false
must disable before production auth   true
```

Those first two lines are why it cannot go yet, and the last is why it cannot stay. Removing it today would break the application without making anything safer; letting it reach production auth would leave an unauthenticated way to read another Tribe's data by typing a UUID.

## Secrets

No secret value appears in any file in this directory. Presence is reported as a boolean, and three independent checks scan for leakage: in the preflight service, in the activation gate, and here before anything is written.

## What is true

```text
customer_auth_activation_contract_available          true
dev_header_must_disable_before_production_auth       true
```

## Claims this gate does not make

```text
beta_onboarding_ready                                false
customer_auth_live                                   false
customer_persistence_live                            false
login_live                                           false
operational_awarded_tracking_ready                   false
operational_digest_ready                             false
callback_session_validated                           false
issuer_jwks_validated                                false
org_binding_passed                                   false
provider_configured                                  false
role_mapping_passed                                  false
secret_present                                       false
```

No identity provider was contacted, no network call was made, no user or session was created, no URL was fetched, no collector ran and no source was monitored.

