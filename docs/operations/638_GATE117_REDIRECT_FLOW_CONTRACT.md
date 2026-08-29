# 638 — Gate 117C: the redirect flow contract

`src/nativeforge/services/customer_auth_redirect_flow_service.py`

The OIDC authorization-code flow, expressed as a contract that refuses at every
step it cannot complete honestly.

## The flow, and where it stops

```text
1. /login builds an authorization URL       needs provider config
2. state and PKCE generated locally         works today, no provider needed
3. the browser goes to the provider         never happens; no URL is built
4. the provider redirects to /callback      never happens
5. state and PKCE validated                 works today, given inputs
6. the code is exchanged for tokens         blocked at the boundary
7. claims resolve to an organization_id     Gate 112 contract, unexercised
8. a membership is verified                 Gate 112 contract, unexercised
9. a session is created                     never
```

Steps 2 and 5 are real code that runs. Everything else is a contract saying what
would have to be true.

## Building a URL is not calling a provider

`authorization_url_available` requires provider configuration and nothing else.
Constructing a URL is local work — no socket is opened, and the browser would be
the thing that visits it.

The service does not return the URL. A URL carrying a client id and a redirect
URI in a committed artifact is a configuration disclosure nobody asked for, and
an invariant fails any result claiming it returned one.

## session_creation_allowed has five conjuncts

```python
session_creation_allowed = (
    token_exchange_allowed
    and callback_validation_passed
    and organization_id_resolved
    and membership_verified
    and role_mapping_available
)
```

The middle three are Gate 112's rule restated at the flow layer: a token proves
who somebody is; it does not prove which organization they act for, and a claim
about an organization is not a membership in one.

`session_created` is a separate constant `False`. Allowed is not done, and
nothing in this repository creates a session. A test reaches
`session_creation_allowed: True` with forged inputs and asserts `session_created`
stays false and `customer_auth_live` stays false.

## secret_present is threaded through, and it had to be

The first version let the token exchange boundary detect the secret itself. That
made `session_creation_allowed: True` unreachable in a test, which would have
left every refusal above it unfalsifiable. It is now a parameter.

## No provider call, by construction

The exchange lives behind `customer_auth_token_exchange_boundary_service`, whose
`network_call_allowed` defaults to `False` and is raised by nothing here.
`provider_contacted` and `network_calls` are constants with invariants behind
them.
