# Customer auth live redirect readiness (Gate 119)

## The sentence to refuse

> "NativeForge can build an authorization URL, so login works."

It can build one when an issuer, a client id and a redirect URI are
supplied. None is. And a URL is a string — the browser visits it, and
11 of 16 activation gates remain
unsatisfied whether or not one is built.

## What moved

```text
signing key                 presence -> readiness, with a named source
authorization URL           nothing existed -> a builder that makes one
redirect state              contract-only -> a table, migration 0030
/login state and PKCE       constants False -> a generator that runs
session verification        one failure -> missing key vs bad signature
```

## What did not move

```text
signing_key_ready_actual_environment                false
authorization_url_available_actual_environment      false
redirect_state_rows_written                         false
production_sessions_created                         false
provider_contacted                                  false
network_calls_made                                  false
customer_auth_live                                  false
login_live                                          false
customer_persistence_live                           false
beta_onboarding_ready                               false
```

## The unsatisfied gates

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

## The fixture set

```text
cases                        10
keys fit to sign             1
authorization URLs built     1
state consumptions permitted 1
replays detected             1
sessions created             0
providers contacted          false
```

Nine of ten cases refuse. The tenth exists so the nine are
falsifiable — a contract that only says no is a constant.

## What the next gate needs

```text
1. NF_SESSION_SIGNING_KEY   from an environment or a secret manager,
                            supplied out-of-band. The fixture key
                            may never sign a production session.

2. OIDC_ISSUER              the three the URL builder asks for by
   OIDC_CLIENT_ID           name, plus a redirect URI
   a redirect URI

3. the database scope       /login must write a row and /callback
                            must read it. The table is empty.

4. network_call_allowed     raised deliberately, under review

5. signing key rotation     not implemented anywhere

6. owner authorization      NF_CUSTOMER_AUTH_ACTIVATION_APPROVAL
```
