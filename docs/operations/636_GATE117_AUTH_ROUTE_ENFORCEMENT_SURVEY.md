# 636 — Gate 117A: auth route enforcement and redirect-flow survey

Written before any implementation. Every claim was reproduced by reading
`src/nativeforge/api/`, the OIDC services, and the running application's own
route table.

**No secret or token value appears in this document, and none was printed while
producing it.**

## Current auth route behaviour

All five routes return `200` with a structured refusal:

```text
GET  /api/auth/login          200  auth_not_configured
GET  /api/auth/callback       200  callback_validation_not_passed
POST /api/auth/logout         200  no_live_session
GET  /api/auth/session        200  unauthenticated
GET  /api/auth/current-user   200  unauthenticated
```

**Nothing refuses anybody.** `/current-user` answers an anonymous caller exactly
as it would answer a signed-in one, because there is no such thing as a
signed-in one.

## OpenAPI security scheme behaviour

```text
routes in the schema        183
securitySchemes declared    nf_session_cookie
secured operations          NONE
```

Gate 116 declared the scheme and attached it to no operation deliberately: a
scheme referenced by an operation would have made `route_auth_enforced` report
true while the routes still answered everyone identically.

That decision is what this gate is now in a position to reverse honestly — but
only for an operation that actually refuses.

## Existing dependency style for protected routes

```text
require_demo_org_db        14 modules
require_real_org_db        14 modules
get_db_session             13 modules
get_org_context_with_db     1 module  (the shared implementation)
resolve_request_identity    1 module
```

The idiom is `Annotated[T, Depends(fn)]` where `fn` raises `HTTPException`. That
is the shape a customer-auth dependency should take.

### No customer-auth dependency exists

```text
status.HTTP_401 in api/    0 occurrences
"401" in api/              0 occurrences
Cookie( in api/            0
Security( in api/          0
APIKeyCookie in api/       0
OAuth2 in api/             0
```

`HTTPException` appears in 20 modules, and the statuses it raises are:

```text
201 CREATED  30    403 FORBIDDEN  8    409 CONFLICT  6
400 BAD REQUEST 5  422 UNPROCESSABLE 4  503 UNAVAILABLE 2  404 NOT FOUND 1
```

**NativeForge has never returned a 401.** It has no concept of "you are not
authenticated" because nothing can authenticate. This gate introduces the first
one.

Nothing reads a cookie anywhere in the application.

## Redirect-flow primitives

Searched every service module. The results need care, because two of them are
substring false positives:

```text
authorization_url    1  customer_session_cookie_policy_service.py   <- docstring
code_verifier        1  customer_session_cookie_policy_service.py   <- docstring
code_challenge       1  customer_session_cookie_policy_service.py   <- docstring
token_exchange       1  customer_session_cookie_policy_service.py   <- docstring
pkce                 3  Gate 116 contract/artifact/policy services  <- contracts
S256                 4  oidc_readiness, oidc_token_verification,... <- RS256
secrets.token_urlsafe 0
urandom              0
exchange_code        0
grant_type           0
authorization_code   0
create_session       0
mint_session         0
```

Two corrections to the naive reading:

* The `authorization_url`, `code_verifier`, `code_challenge` and
  `token_exchange` hits are all in **Gate 116B's own docstring**, in the passage
  explaining that none of them exists. A module documenting an absence was
  matching a search for the thing it says is absent — the same class of
  false positive Gate 116 found when `api/auth.py` was counted as a dev-header
  dependant for explaining why it does not use one.
* The `S256` hits are **RS256**, the JWT signing algorithm
  (`ALLOWED_ALGORITHMS = frozenset({"RS256"})`). PKCE's `S256` code-challenge
  method shares three characters with it and is a different thing entirely.

So, precisely:

```text
authorization URL builder     does not exist
state generation              does not exist
state validation              does not exist
PKCE generation               does not exist
PKCE validation               does not exist
token exchange                does not exist
session creation              does not exist
local entropy for auth        does not exist (no token_urlsafe, no urandom)
```

## What does exist

```python
# oidc_token_verification_service
verify_oidc_token(*, token, jwks, expected_issuer, expected_audience,
                  now=None, leeway_seconds=30)
fetch_jwks(*, jwks_url, allow_network=False, timeout_seconds=5.0)
ALLOWED_ALGORITHMS = frozenset({"RS256"})   # "none" and HMAC excluded
```

A verifier that takes a token and a JWKS document. It does not fetch, does not
exchange, and its network helper is off by default.

```python
# oidc_callback_validation_harness_service
cases: invalid_audience, invalid_issuer, invite_not_found, missing_config,
       mock_claims_not_live, org_mismatch, role_mismatch, unverified_email
network_calls: False    real_secrets_used: False
```

Eight callback failure modes, modelled offline. A callback validation *contract*
therefore already exists in the shape of a harness; what does not exist is
anything that runs the flow.

## Can enforcement be added without touching product routes?

**Yes.** The five auth routes are in one module with no product route importing
it. Attaching a dependency to `/api/auth/current-user` touches nothing else, and
the 30 product route modules keep their existing `require_*_org_db`
dependencies unchanged.

The brief forbids securing product routes broadly, and this survey finds no
reason to: each product route would need its own tested auth path, and none has
one.

## What still blocks login_live after enforcement

Enforcement moves **no activation gate**. The ten currently missing are:

```text
provider_configured           secret_present
issuer_configured             audience_configured
issuer_jwks_validated         callback_session_validated
invite_binding_passed         org_binding_passed
role_mapping_passed           dev_header_disabled_for_production
```

Not one of them is a route-enforcement fact. A 401 from `/current-user` proves
the application can refuse; it proves nothing about whether anybody could ever
succeed.

This is the finding that shapes the gate: **enforcement and activation are
independent**, and the readiness service must be able to report enforcement true
while `customer_auth_live` stays false.

## The derivation that must change

Gate 115C infers three enforcement facts from one:

```python
route_auth_enforced = has_security and session_route_available
route_org_resolution_enforced = route_auth_enforced and current_user_route_available
route_role_mapping_enforced = route_org_resolution_enforced
```

Securing `/current-user` would make all three true. The first would be honest —
the route really would refuse. The second and third would not: no route resolves
an organization or maps a role, and neither can until a principal exists.

So this gate separates them: auth enforcement is measured from a secured
operation whose dependency mode refuses, while organization-resolution and
role-mapping enforcement additionally require a principal that could carry them —
which requires `customer_auth_live`, which is false.

## Answers to the specific questions

```text
current auth route behavior        all five return 200, nothing refuses
OpenAPI security scheme behavior   declared, attached to zero operations
any operation secured?             no
dependency style                   Annotated[T, Depends(fn)] raising HTTPException
customer-auth dependency exists?   no; no 401 anywhere in the application
authorization URL builder?         no
state generation?                  no
state validation?                  no
PKCE generation?                   no
token exchange?                    no
callback validation contract?      yes - an offline harness with 8 cases
session creation contract?         no
enforcement without product routes? yes - one module, no product importer
what still blocks login_live       all ten activation gates; none is a route fact
```

## What this gate must not do

```text
call a provider              token exchange stays behind network_call_allowed
create a session             session_created stays false
create a user                no row, anywhere
secure product routes        each would need its own tested auth path
commit a state or verifier   fixtures only, labelled, and never real
claim auth or login live     ten gates unsatisfied, none of them a route fact
```
