# 635 — Gate 116: auth route readiness delta

What changed, what did not, and the sentence to refuse.

## The sentence to refuse

> "NativeForge has login, logout, callback, session and current-user routes plus
> a security scheme, so customers can log in."

Every noun in the first clause is true. The conclusion is false. None of the five
routes authenticates anybody, the security scheme is attached to no operation,
and ten of fifteen activation gates remain unsatisfied.

This is the gate most likely to be misread as progress, because it is the first
one that adds something a person can visit.

## What moved

```text
                                     before   after   why
application routes                   178      183     five auth routes
login route                          absent   present
logout route                         absent   present
callback route                       absent   present
session route                        absent   present
current-user route                   absent   present
security scheme declared             none     nf_session_cookie
session cookie policy                none     defined, passes its invariants
activation gates satisfied           3 of 15  5 of 15
missing activation gates             12       10
```

Exactly two gates moved: `callback_route_available` and
`session_cookie_policy_available`. Those are the two a route spine can satisfy.

## What did not move

```text
customer_auth_live                   false
login_live                           false
provider_configured                  false
secret_present                       false
issuer_jwks_validated                false
callback_session_validated           false
org_binding_passed                   false
role_mapping_passed                  false
route_auth_enforced                  false    scheme declared, nothing secured
ready_for_live_login                 false
dev header production safe           false
dev header safe to disable           false
customer_persistence_live            false
operational_awarded_tracking_ready   false
operational_digest_ready             false
beta_onboarding_ready                false
source_monitoring_live               false
source_coverage_claimed              false
```

## One value split into two

Gate 115C derived enforcement from the presence of a security scheme:

```python
has_security = bool(security_schemes) and bool(globally_secured or secured_route_count)
```

That was correct while no scheme existed. Declaring one made the two facts
separable, so they are now separate:

```text
security_scheme_declared   a scheme appears in the OpenAPI document
has_security               some operation actually depends on one
```

An invariant fires if enforcement is ever reported with zero secured routes, and
another if the two scheme fields disagree. The state Gate 116 leaves the
application in is named rather than silent:
`security_scheme_declared_but_no_route_requires_it`.

## One field was measuring the wrong thing

`session_cookie_policy_available` in the activation gate read
`route_session_cookie_policy_enforced` — route *enforcement*. The field is named
"available", and under that reading a defined policy could never satisfy it: the
gate would have gone on reporting the policy missing after it existed.

It now reads whether a policy exists *and* passes its own invariants. A policy
failing them is not a policy anything should rely on, and reporting one as
available would be worse than reporting none.

## A detector was counting mentions as usage

`detect_dev_header_route_usage` searched for the bare dependency names, which
counted any module that mentioned them. Two modules were false positives:

```text
capability_guard.py   a docstring describing the header
api/auth.py           a docstring explaining why it deliberately does NOT use it
```

A module documenting its refusal was being reported as a dependant. The detector
now matches `Depends(name)`, which is what actually wires a dependency into a
route, and reports mention-only modules as their own field.

**The corrected count is 15, not 16.** Gate 115's figure included
`capability_guard.py` and was one too high — a reporting error, not a safety one.
The conclusion is unchanged: the header is load-bearing and cannot be removed.

## Auth routes existing is not a replacement

```text
auth_replacement_routes_available   true    the endpoints are registered
replacement_route_available         false   none of them authenticates anybody
auth_replacement_available          false
safe_to_disable_now                 false
must_disable_before_production_auth true
```

The first is new and true as of this gate. Reporting only it would let "the auth
routes are in" read as "the dev header can go". An invariant fires if
`safe_to_disable_now` is ever true while `replacement_route_available` is false.

**Cloudflare Access is not customer app auth**, unchanged.

## Two Gate 115 tests were updated rather than deleted

```text
test_the_application_has_no_customer_auth_routes
    -> test_the_applications_auth_routes_enforce_nothing

test_the_route_matrix_reports_no_route_and_no_enforcement
    -> test_the_route_matrix_reports_routes_without_enforcement
```

Both asserted a state this gate deliberately moved past. The assertion that
mattered in each — that readiness reflects reality, and that nothing is enforced
— is preserved and now carries more weight, because it holds with the routes
present rather than trivially with them absent.

## No migration, no provider call

Alembic head remains **0029**. `run_auth0_preflight` reads environment presence
only, the live validation runner reports `network_calls: False` under an
invariant, and `fetch_jwks` defaults `allow_network=False`.

No identity provider was contacted. No URL was fetched. No collector ran. No
source was monitored. No email was sent.

## Secrets

No secret was printed, stored, committed or echoed. Two tests plant a value in
the environment and assert it reaches neither any auth route response nor any
artifact file. The artifact writer reuses Gate 115's scanner and raises rather
than writing if a configured value appears.

## What the next gate needs

```text
1. enforcement                 a dependency that refuses an unauthenticated
                               caller, and the security scheme attached to the
                               operations that use it. This is what turns
                               route_auth_enforced true.

2. the redirect flow           an authorization-url builder, state and PKCE
                               generation, and token exchange. None exists.

3. owner supplies OIDC_*       provider_configured, secret_present,
                               issuer_configured, audience_configured

4. validate a real flow        issuer_jwks_validated, callback_session_validated,
                               invite_binding, org_binding, role_mapping

5. replace the dev header      15 modules depend on it today

6. owner authorizes            NF_CUSTOMER_AUTH_ACTIVATION_APPROVAL
```

Step 1 is the honest next move, and it is where `/session` and `/current-user`
stop answering everyone identically.
