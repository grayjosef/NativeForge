# Customer auth activation preflight (Gate 121)

## The sentence to refuse

> "The preflight exists, so we know how to turn auth on."

The preflight says what is missing. Nothing in it configures anything,
and every remaining blocker is outside this repository:
11 of 16 activation gates are
unsatisfied and **not one of them can be satisfied by writing code**.

## What moved

```text
environment preflight       none      key names and booleans
provider readiness          none      10 gates, all measurable offline
operator runbook            none      28 items, 9 sections, 6 do-not-do
activation blockers         a list    named by who has to act
callback URL correctness    unchecked measured, and it is wrong
```

## What did not move

```text
customer_auth_live                          false
login_live                                  false
customer_persistence_live                   false
verified_binding_ready_actual               false
operator_authorization_present              false
beta_onboarding_ready                       false
production_rollout_ready                    false
provider_called                             false
network_calls_made                          false
source_monitoring_live                      false
source_coverage_claimed                     false
production_verified_bindings_created        0
real_customer_rows_written                  0
real_users_created                          0
production_sessions_created                 0
```

## The defect this gate found

```text
configured callback   http://localhost:5173/auth/callback
API callback route    /api/auth/callback
frontend route        none - the frontend declares no routes
```

The value an operator would copy into the provider console points at
a path that exists in neither the API nor the frontend. Registering
it and completing a login would land a browser on a 404 holding a
live authorization code, and the failure would look like a provider
problem rather than a configuration one.

## The eight named blockers

```text
callback_url_does_not_match_a_route
database_revision_not_applied
dev_header_still_in_place
owner_authorization_absent
provider_configuration_missing
role_mapping_not_validated
secret_configuration_missing
signing_key_not_fit_to_sign
```

## The unsatisfied activation gates

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

## The runbook

```text
items                    28
blocking activation      16
already done             0
prohibited (do not do)   6
commands secret-safe     true
```

## The fixture set

```text
cases                    8
disagreeing              0
any claiming auth live   false
```

Eight cases walk one hypothetical deployment from nothing configured
to everything configured. The last one has every preflight gate
green, carries the owner's signature, and auth is still off - three
of the sixteen gates need a real browser and nobody has run one.

## Next operator actions, in dependency order

```text
1  create the provider application
2  set OIDC_ISSUER, OIDC_CLIENT_ID, OIDC_CLIENT_SECRET, OIDC_AUDIENCE
3  set NF_SESSION_SIGNING_KEY from an environment or secret manager
4  fix the redirect URI so it matches a route, and register it
5  apply migrations to the runtime database, to head 0030
6  define provider roles and map them explicitly
7  run the callback smoke once, with a real browser
8  replace X-NF-Org-Id across 15 route modules, then disable it
9  set NF_CUSTOMER_AUTH_ACTIVATION_APPROVAL
```

Step 9 is last on purpose: the approval variable is an owner's
signature, not a switch, and signing before 1-8 would authorize an
activation that cannot happen.
