# 632 — Gate 116A: customer auth route survey

Written before any implementation. Every claim was reproduced by reading
`src/nativeforge/api/`, `src/nativeforge/main.py`, the OIDC services and the
existing tests.

**No secret value appears in this document, and none was printed while
producing it.**

## Router registration pattern

Uniform and simple, across all 26 modules in `src/nativeforge/api/`:

```python
router = APIRouter(prefix="/v1/isolation", tags=["demo-isolation"])

@router.get("/demo-only")
def demo_only_ping(...) -> dict[str, str]:
    ...
```

`main.py::create_app()` imports each module's router and calls
`app.include_router(...)` — thirty-one calls, no dynamic discovery, no plugin
mechanism. Most product modules export a `demo_*` / `real_*` pair; the simplest
(`health.py`) exports a single `router` and takes no dependency at all.

**Auth routes can be added without touching a single product route.** A new
module plus one `include_router` line is the whole change.

## OpenAPI and security schemes

```text
securitySchemes declared    NONE
global security             NONE
routes declaring security   NONE
app.openapi() overridden    no
```

FastAPI generates `securitySchemes` only from actual security dependencies, so
declaring a scheme *without* applying it requires post-processing the generated
schema. That is a small, contained function — and it is the right shape for this
gate, because the scheme should be advertised while nothing is yet secured by it.

The one file in `api/` matching "security" is `capability_guard.py`, and the hit
is an import of `security_audit_sink_service`. Not a security scheme.

## The org context dependency

One path, unchanged since Gate 112 recorded it:

```text
deps_db.get_org_context_with_db
  requires header X-NF-Org-Id, refuses unless settings.nf_dev_org_headers
  parses as UUID, looks it up in `organizations`
  then apply_org_rls_gucs(session, org_id, org_type)
```

Sixteen route modules depend on it. The auth routes added by this gate **must
not** use it: they are the eventual replacement for it, and having them consume
it would make the replacement depend on the thing it replaces.

## What the OIDC services already provide

Four services, and all four are validators or mappers rather than flow drivers:

```text
oidc_config_schema_service          build_oidc_config_schema
oidc_token_verification_service     verify_oidc_token, fetch_jwks
oidc_callback_validation_harness    run_oidc_callback_validation_harness
oidc_identity_mapper_service        map_oidc_claims_to_auth_context
```

### What they do not provide

Searched every service module:

```text
pkce               0 occurrences
code_verifier      0
code_challenge     0
authorization_url  0
token_exchange     0
exchange_code      0
```

**There is no authorization-URL builder, no token exchange, and no PKCE
anywhere in this repository.** The `state` and `authorize` matches are all from
unrelated domains — activation state, human authorization packets.

This settles a question the brief leaves open: `pkce_required` must be a
requirement this gate *introduces*, not something the existing flow proves. The
existing flow does not exist.

### Two safety properties worth recording

```python
# oidc_config_schema_service
"client_secret_value": None,  # never populated
# and its invariant:
if cfg.get("client_secret_value") is not None:
    fails.append("secret_value_leaked")
```

A deliberate tripwire field, not a leak.

```python
# oidc_token_verification_service
def fetch_jwks(*, jwks_url, allow_network: bool = False, timeout_seconds: float = 5.0):
    if not allow_network:
        return {..., "reason": "network_disabled", "network_access_attempted": False}
```

Network off by default, fails closed. The callback harness reports
`network_calls: False` and `real_secrets_used: False`.

So callback validation **can** be implemented contract-only: the harness already
models the eight cases without contacting anything.

## Session cookie policy

```text
cookie / set_cookie in api/     0 occurrences
same_site / http_only anywhere  0 occurrences
Response imported in api/       0 occurrences
```

No cookie is set anywhere in NativeForge today. The policy is entirely new, and
no existing behaviour constrains it.

## Will the route readiness detector see new routes?

Yes, without modification. Gate 115C's patterns matched against the intended
paths:

```text
login_route_available          /api/auth/login
logout_route_available         /api/auth/logout
callback_route_available       /api/auth/callback
session_route_available        /api/auth/session
current_user_route_available   /api/auth/current-user
```

Framework routes are excluded by prefix (`/docs`, `/redoc`, `/openapi.json`), so
`/docs/oauth2-redirect` still will not count as a callback.

### But the enforcement derivation needs strengthening

Gate 115C currently derives:

```python
has_security = bool(security_schemes) and bool(globally_secured or secured_route_count)
route_auth_enforced = has_security and session_route_available
```

If this gate declared a security scheme *and* attached it to the auth routes,
`route_auth_enforced` would flip to true — while the routes still returned
`authenticated: false` to everyone. That is the "existence is not enforcement"
defect one layer up: **a scheme declared in OpenAPI is documentation, not a
refusal.**

Two consequences for the design:

1. The scheme is declared in `components.securitySchemes` and referenced by **no
   operation**. `secured_route_count` stays 0, `has_security` stays false, and
   `route_auth_enforced` stays false — correct, and it works with Gate 115C's
   existing logic rather than against it.
2. `security_scheme_declared` becomes its own measured field, separate from
   enforcement, with an invariant that a declared scheme with zero secured
   routes may never report enforcement.

## Existing route test structure to reuse

```python
from fastapi.testclient import TestClient
from nativeforge.main import create_app

def test_health_returns_ok() -> None:
    client = TestClient(create_app())
    response = client.get("/health")
    assert response.status_code == 200
```

`tests/test_health.py` is the pattern: build the app, use `TestClient`, assert on
the JSON body. Six test modules already use `TestClient`. Gate 116's route tests
follow it.

## Answers to the specific questions

```text
router registration pattern         APIRouter + include_router in create_app
OpenAPI / security scheme setup     none; requires overriding app.openapi()
org context dependency              deps_db.get_org_context_with_db (dev header)
auth routes without touching        yes - one new module, one include_router line
  product routes?
callback/session contract-only?     yes - the harness already models it offline
authorization URL / token exchange  none exist
  / state / PKCE contracts?
route test structure to reuse       tests/test_health.py, TestClient
route readiness detects new routes? yes, unmodified; enforcement needs
                                    strengthening so a declared scheme is not
                                    mistaken for a refusal
session cookie policy exists?       no - zero cookie handling anywhere
```

## What this gate must not do

```text
create a real session       no cookie is set with a real session value
create a user               no row, anywhere
contact a provider          the harness is offline; fetch_jwks stays off
set app.current_org_id      these routes must not touch the RLS context
secure product routes       the scheme is advertised, applied to nothing
claim auth or login live    twelve activation gates are unsatisfied; this gate
                            can satisfy at most two of them
```
