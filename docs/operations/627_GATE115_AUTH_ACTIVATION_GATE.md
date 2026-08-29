# 627 — Gate 115B: the customer auth activation gate

`src/nativeforge/services/customer_auth_activation_gate_service.py`

Fifteen gates, twelve missing, one answer.

## Why this is not the Gate 19 service

`login_live_promotion_gate_service` reports the same family of gates and cannot
ever say yes:

```python
login_live_claimed = False
if all_passed and preflight.get("validation_possible"):
    login_live_claimed = False        # assigned False, then False again
```

with invariants that fail the result if any of its three claims is `True`. Read
as code that branch is dead; read as policy it is Gate 19 deliberately building
a **modelling** gate.

That service is untouched. This one is the activation gate: `customer_auth_live`
is derived, so it moves when the world does. A test forges every input and
asserts the permitted branch is reachable — without that, twelve refusals would
be indistinguishable from a constant.

## The fifteen gates

```text
provider_configured                    false   seven OIDC env vars absent
secret_present                         false   presence boolean
issuer_configured                      false
audience_configured                    false
issuer_jwks_validated                  false   unvalidated, not failed
callback_route_available               false   zero auth routes in 178
callback_session_validated             false
session_cookie_policy_available        false   no securityScheme anywhere
invite_binding_passed                  false
org_binding_passed                     false
role_mapping_passed                    false
organization_id_resolution_available   TRUE    Gate 112
membership_verification_available      TRUE    Gate 112
rls_claim_guard_available              TRUE    Gate 111
dev_header_disabled_for_production     false   16 route modules depend on it
```

Three satisfied of fifteen, and all three are contracts this campaign built.

## Two rollups, deliberately different

```python
customer_auth_live = all(REQUIRED_AUTH_GATES) and owner_approval
login_live         = all(REQUIRED_LOGIN_GATES) and owner_approval
```

`REQUIRED_LOGIN_GATES` omits `dev_header_disabled_for_production` and the three
contract-availability gates. A login flow can run before the dev header is gone;
**customer auth is not live while an unauthenticated header can still set
`app.current_org_id`.**

The demo fixture set makes the difference concrete: `all_gates_pass` and
`dev_header_still_enabled` differ in exactly one input, and the second reports
`login_live: true` with `customer_auth_live: false`.

## Owner approval is a gate

`activation_allowed` requires an explicit token supplied out-of-band, compared
and never reported. Configuration arriving in an environment is not somebody
deciding to expose a login page to real Tribes. Every measured gate passing is
necessary and not sufficient.

## Unvalidated is not failed

`preflight.jwks_reachable` is `None`, not `False`, because
`jwks_network_check_enabled` defaults to `False` and no check runs. The gate
reports `issuer_jwks_network_check_performed: false` alongside
`issuer_jwks_validated: false`, and an invariant fires if validation is ever
claimed without a check having happened.

Fabricating "checked and failed" from "not checked" would be inventing a
measurement.

## Secrets

`secret_present` is a boolean. Three independent leak scans run in the chain:

```text
auth0_preflight_service   scans its own serialised output
this gate                 scans the assembled result
the artifact service      scans every file before anything reaches disk
```

Each searches for any configured `OIDC_*` value of length ≥ 8. A hit sets
`secret_value_emitted`, forces every claim false, and — in the artifact service
— raises rather than writing. Tests plant a value in the environment and assert
it reaches neither the gate output nor any artifact.

A committed artifact is the worst place for a client secret, because it survives
in history after the file is deleted.

## No network, no provider

`run_auth0_preflight` reads environment presence only. The live validation
runner reports `network_calls: False` under an invariant that fails if it is
ever true. No identity provider was contacted while building or running this
gate.
