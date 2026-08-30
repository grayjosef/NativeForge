# 658 — Gate 121C: provider readiness

`src/nativeforge/services/customer_auth_provider_readiness_service.py`

## Configured, reachable, and validated are three different facts

```text
configured   a value is set here                        measurable offline
reachable    a browser could actually get to it         asserted, never tested
validated    we fetched the JWKS and it checked out     a network call
```

Only the first is measurable without leaving the process, and it is the only one
this service measures on its own.

`redirect_uri_publicly_reachable_claimed` carries `_claimed` in its name because
nothing here can verify it. Reachability is a question about DNS, TLS and a
tunnel; a service answering it from a config file would be guessing, and a
guess in a readiness field is worse than a gap.

## Ten gates, all measurable offline

```text
issuer_configured
client_id_configured
client_secret_present
authorization_endpoint_configured
token_endpoint_configured
jwks_uri_configured
audience_configured
redirect_uri_configured
callback_route_available
callback_route_matches_redirect_uri
```

The three endpoint gates are derived from the issuer rather than configured
separately. A deployment made to set four endpoint URLs by hand would get one of
them wrong, and the wrong one would be discovered at token exchange — after a
user had already been redirected.

## An unvalidated JWKS is not a failed one

```text
jwks_network_check_allowed     false by default; nothing here raises it
jwks_network_check_attempted   false unless allowed AND a result was supplied
jwks_validated                 false unless attempted AND it passed
```

"We never looked" and "we looked and it was wrong" call for completely different
operator actions. Gate 115 made this distinction for the activation gate and
this preserves it. An invariant refuses `jwks_validated` without
`jwks_network_check_attempted`, and a test forges exactly that.

## provider_ready is independent of the network check, deliberately

A deployment that has configured everything correctly is *provider ready*
whether or not anybody has run a JWKS fetch. Folding the fetch in would make
`provider_ready: True` unreachable without a network call this gate refuses to
make — the untestable-conjunct pattern, arriving for the fifth time.

So `provider_ready` can be true while `blocked_reasons` still names the
unvalidated JWKS. That reads oddly for a moment and is the honest shape: the
configuration is complete, and one assurance has not been run.

## The redirect URI has to match a route

This is the gate that catches Gate 121A's finding.
`callback_route_matches_redirect_uri` compares the path of the configured
redirect URI against the route that would consume it, and it is false today.

A test supplies a redirect URI pointing at the frontend path and asserts
`provider_ready` stays false with that gate named; another supplies the API path
and asserts `provider_ready` reaches true with no missing gates.

## No secret, no value, no call

`client_secret_present` is a boolean and there is no field for a value. The
issuer and the endpoints are public identifiers — every browser sees them — and
are still reduced to scheme, host and path before they reach a result, so an
artifact can carry them.

A test hands the service a redirect URI carrying `?code=abc#frag` and asserts
the published form has neither.

```text
provider_called   false, a constant
network_calls     false, a constant
```

## What it says about the actual environment

```text
provider_ready                       false
missing gates                        8 of 10
issuer_redacted                      "" - nothing configured
redirect_uri_redacted                http://localhost:5173/auth/callback
callback_route_path                  /api/auth/callback
callback_route_matches_redirect_uri  false
jwks_validated                       false, and never checked
```
