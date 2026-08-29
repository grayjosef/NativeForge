# 626 — Gate 115A: customer auth activation survey

Written before any implementation. Every claim was reproduced by reading the
services, the settings, the migrations and the live FastAPI route table.

**No secret value appears in this document, and none was printed while producing
it.** The preflight service reports presence booleans only; the survey read
those booleans.

## Auth service inventory

Twenty-three modules, in three families:

```text
auth0_*   12   preflight, mode detection, validation runners, Mode B unlock,
               RBAC validation, and five assembler services over them
oidc_*     9   config schema, token verification, identity mapper, callback
               harness, readiness, organization_id resolution (Gate 112) and
               its artifact/fixture services
login_*    2   login_claim_resolver, login_live_promotion_gate
```

Plus the contracts Gate 111/112 added: `customer_auth_principal_contract`,
`verified_binder_authorization`, `rls_context_claim_guard`,
`customer_org_membership_verification`.

Every one of these is a **contract or a validator**. None of them authenticates
anybody.

## Login promotion gate inventory

`login_live_promotion_gate_service.evaluate_login_live_promotion` reports eleven
gates. Current state, measured:

```text
provider_configured          false   <- missing
secret_present               false   <- missing
issuer_jwks_validated        false   <- missing
callback_session_validated   false   <- missing
invite_binding_passed        false   <- missing
org_binding_passed           false   <- missing
role_mapping_passed          false   <- missing
rbac_handoff_passed          true
tenant_boundary_passed       true
audit_event_emitted          true
operator_approval            true    (not required outside production modelling)
```

Seven missing, exactly the seven Gate 111 recorded. Nothing has changed.

### This service can never say yes, by design

```python
login_live_claimed = False
if all_passed and preflight.get("validation_possible"):
    login_live_claimed = False        # assigned False, then False again
```

and its invariants pin the result:

```python
for key in ("login_live_claimed", "controlled_pilot_auth_ready",
            "production_auth_claimed"):
    if result.get(key) is True:
        fails.append(key)
```

That conditional branch cannot change the value it assigns. Read as code it is
dead; read as policy it is Gate 19 deliberately building a **modelling** gate
that models promotion without ever performing it.

The consequence matters for this gate: it is not an activation gate and cannot
become one. A separate service is required — one whose `customer_auth_live` is
*derived*, so it moves when the seven gates and an owner authorization do,
rather than being pinned by an invariant. That is Gate 115B, and it leaves the
Gate 19 service exactly as it is.

## Provider configuration and secret presence

`auth0_preflight_service` reads seven environment variables and reports
**presence booleans only**:

```text
OIDC_ISSUER  OIDC_CLIENT_ID  OIDC_CLIENT_SECRET  OIDC_AUDIENCE
OIDC_CALLBACK_URL  OIDC_LOGOUT_URL  OIDC_ALLOWED_ORIGIN
```

```python
def _presence(key: str) -> bool:
    val = os.environ.get(key)
    return bool(val and str(val).strip())
```

Current state: **all seven missing**, `validation_possible: false`,
`client_secret_present: false`.

It also self-checks for leakage — after serialising, it searches its own output
for any env value of length ≥ 8 and marks itself `UNSAFE` if one appears. That
check has never fired, and `secret_value_emitted` is false.

This is the safe local validator the brief permits, and Gate 115 builds on it
rather than reading the environment again.

## JWKS / issuer validation

```text
jwks_network_check_enabled   false
jwks_reachable               None
```

`None` rather than `False` is correct and worth preserving: nothing was checked,
which is a different fact from "checked and unreachable". No network call is made.

`auth0_live_validation_runner_service` reports `network_calls: false` and has an
invariant that fails if it is ever true. `issuer_jwks_validated` is therefore
false because it is unvalidated, not because validation failed.

## Callback, session, invite, org binding, role mapping

All false, from the live validation runner:

```text
provider_validated           false
callback_session_validated   false
invite_binding_passed        false
org_binding_passed           false
role_mapping_passed          false
rbac_handoff_passed          true
tenant_boundary_passed       true
```

## Customer-authenticated routes: there are none

Measured against the running application's OpenAPI schema, not by grepping:

```text
routes in the schema                178
auth-shaped routes                  NONE
securitySchemes declared            NONE
global security                     NONE
routes declaring security           NONE
```

`/docs/oauth2-redirect` appears in the raw route list. It is FastAPI's Swagger
UI helper, not a NativeForge callback, and it authenticates nobody.

So: **no login route, no logout route, no callback route, no session route, no
current-user route.** Not one of the 178 endpoints requires a credential.

## The app.current_org_id path

One path, and it is not authentication:

```text
deps_db.get_org_context_with_db
  requires header X-NF-Org-Id
  refuses entirely unless settings.nf_dev_org_headers is true
  parses the value as a UUID
  looks the row up in `organizations`
  then calls apply_org_rls_gucs(session, org_id, org_type)
```

`db/rls.py::apply_org_rls_gucs` is the only place `app.current_org_id` and
`app.current_org_is_demo` are set, and it is a no-op outside PostgreSQL.

Sixteen route modules depend on that org context. Every one of them therefore
depends on an unauthenticated header.

## Dev header state

```text
settings.nf_dev_org_headers default      true
dev_org_header_containment production_safe   false (constant, invariant-pinned)
dev_org_header_containment customer_auth_live false (constant, invariant-pinned)
must_disable_before_customer_auth            true
must_replace_with_auth_claim_guard           true
```

Gate 112 already recorded that the header is contained by deployment posture
(loopback-only backend behind Cloudflare Access), not that it is safe.

**Cloudflare Access is not customer app auth.** It gates who reaches the tunnel;
it establishes no NativeForge principal, no organization, and no role. A route
behind it is still a route with no credential requirement.

Note for implementation: `dev_org_header_containment_service` shells out to
`systemctl`, so its output depends on the machine. Gate 114 avoided depending on
it for that reason, and Gate 115 must do the same anywhere a committed artifact
is involved.

## Can customer auth be live today?

**No.** Nine independent reasons, each measured:

```text
1. no provider configured        all seven OIDC env vars absent
2. no client secret present      presence boolean false
3. issuer/JWKS unvalidated       no network check performed
4. no callback route             zero auth-shaped routes in 178
5. no session route or policy    no securitySchemes at all
6. callback/session unvalidated  runner reports false
7. no invite or org binding      runner reports false
8. no role mapping               runner reports false
9. dev header still the org path 16 route modules depend on it
```

Items 4 and 5 are the ones no amount of configuration fixes. Even with all seven
environment variables set and a validated issuer, there would be nowhere for a
customer to log in.

## What exactly still blocks live auth

Grouped by what would lift each:

```text
owner supplies configuration    provider_configured, secret_present
                                (out-of-band; this gate must never store them)

a network validation step       issuer_jwks_validated
                                (requires configuration first)

NativeForge builds routes       callback_route_available, session policy,
                                login/logout/current-user
                                (this is engineering work, not configuration)

validation of a real flow       callback_session_validated, invite_binding,
                                org_binding, role_mapping
                                (requires both of the above)

NativeForge removes the header  dev_header_disabled_for_production
                                (requires the auth replacement to exist first)
```

## Does this gate need a migration?

**No.** Every fact is observable from the environment presence flags, the route
table, the settings and the existing contracts. `nf_identities` and
`nf_org_memberships` already exist for when a real principal appears.

Alembic head remains 0029.

## What this gate must not do

```text
print or store a secret          presence booleans only, and a leak self-check
call a live provider             preflight is offline; the runner forbids network
create a user or a session       no row, no cookie, no token
add an auth route                that is the next gate's work, decided against
                                 this boundary rather than ahead of it
claim auth or login live         both stay false until every gate is measured
                                 true and an owner authorizes
```
