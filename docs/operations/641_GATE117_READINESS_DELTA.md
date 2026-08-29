# 641 — Gate 117: readiness delta

What changed, what did not, and the sentence to refuse.

## The sentence to refuse

> "NativeForge returns 401 to unauthenticated callers, so authentication works."

The first clause is true. The second does not follow and is false.
`/api/auth/current-user` refuses **everybody**, because nobody can authenticate.
A 401 proves the application can say no; it proves nothing about whether anyone
could ever be told yes.

Ten of fifteen activation gates remain unsatisfied, and this gate moved none of
them.

## What moved

```text
                                      before   after   why
routes returning 401                  0        1       /current-user
secured operations                    0        1       the one that refuses
route_auth_enforced                   false    true    measured from a refusal
route_session_cookie_policy_enforced  false    true    a route reads the cookie
auth dependency contract              none     4 modes
redirect flow contract                none     9 steps
state generation                      none     32 bytes, CSPRNG
PKCE generation                       none     S256, RFC 7636
token exchange boundary               none     6 conditions
```

## What did not move

```text
customer_auth_live                    false
login_live                            false
missing activation gates              10, unchanged
provider_configured                   false
secret_present                        false
route_org_resolution_enforced         false    a 401 is not an organization
route_role_mapping_enforced           false
ready_for_live_login                  false
token_exchange_performed              false    the network is off
session_created                       false
dev header safe to disable            false
dev header production safe            false
customer_persistence_live             false
operational_awarded_tracking_ready    false
operational_digest_ready              false
beta_onboarding_ready                 false
source_monitoring_live                false
source_coverage_claimed               false
```

## A 401 is not an organization

Gate 116 derived three enforcement facts from one:

```python
route_auth_enforced = has_security and session_route_available
route_org_resolution_enforced = route_auth_enforced and current_user_route_available
route_role_mapping_enforced = route_org_resolution_enforced
```

That was safe while `route_auth_enforced` was always false. Securing
`/current-user` would have made all three true at once — and while the 401 is
real, no route resolves an organization or maps a role, and neither can until a
principal exists.

Both now additionally require `customer_auth_live`, and two invariants fire if
either is reported while nobody can authenticate.

## A defect I introduced and fixed

The first version of that change made `ready_for_live_login: True` unreachable:
`customer_auth_live` was read only from the detector, so no test could reach the
branch, and every "not ready" claim above it became unfalsifiable.

`customer_auth_live` is now a parameter of `build_route_readiness`. A test forges
a fully-secured route table *and* a live world and asserts the branch is
reachable; another forges the same routes with auth not live and asserts it is
not.

## Two things Gate 116 stated that are now wrong, and were corrected

```text
/session security_required: True
    read correctly before there was a dependency to make the distinction. A
    caller asking whether they have a session should be told no, not refused
    for not having one. It is optional, and now false.

the route matrix rendered one enforcement value for all five rows
    accurate while the answer was "none of them". A single column repeating
    `true` five times would now say four things that are false. Enforcement is
    rendered per route, and an invariant fires if a row reports enforcement
    without requiring a credential.
```

## Auth routes that refuse are still not a replacement

```text
auth_replacement_routes_available     true
auth_routes_enforce_authentication    true    new this gate
replacement_route_available           false
safe_to_disable_now                   false
must_disable_before_production_auth   true
```

The dev header supplies an `organization_id`. A 401 supplies nothing. A
replacement must be able to say **yes** to somebody, and none of these can. An
invariant fires if `safe_to_disable_now` is ever true while the routes only
refuse.

The blocked reason changed to say so precisely:
`auth_routes_refuse_unauthenticated_callers_but_cannot_admit_anybody`.

## No provider call, no token, no session, no secret

```text
network_call_allowed        defaults false; nothing in this repository raises it
provider_contacted          constant false, invariant-backed
token_exchange_performed    constant false, invariant-backed
session_created             constant false, invariant-backed
```

Two tests plant a secret in the environment and assert it reaches neither an
auth route response nor an enforcement artifact. A third plants a cookie value
and asserts no route echoes it. The artifact writer walks every nested structure
for credential-shaped field names and raises rather than writing.

The state and PKCE values in the artifacts are the labelled `nf-demo-fixture-`
ones, which fail their own entropy checks by design.

## No migration

Alembic head remains **0029**.

## What the next gate needs

```text
1. a session format          something a cookie can carry and a dependency can
                             validate. `session_cookie_valid` is derived false
                             today because there is nothing to validate against.

2. the redirect flow, live   an authorization URL actually built and returned,
                             state and PKCE issued at /login and stored across
                             the redirect

3. owner supplies OIDC_*     provider_configured, secret_present,
                             issuer_configured, audience_configured

4. network_call_allowed      turned on deliberately, under review, so a token
                             exchange can happen at all

5. replace the dev header    15 modules depend on it

6. owner authorizes          NF_CUSTOMER_AUTH_ACTIVATION_APPROVAL
```

Step 1 is the honest next move. It is what turns `session_cookie_valid` from a
derived false into a real check, and it is the last thing standing between the
dependency contract and a working `/current-user`.
