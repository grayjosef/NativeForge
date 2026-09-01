# 696 — Gate 131: login, callback, and session minting

## Login redirect status: working

`GET /api/auth/login` returns **302 to
`https://accounts.google.com/o/oauth2/v2/auth`**.

Two Gate 119 decisions were removed, both correct when there was nowhere to send
a browser:

```text
store_state(..., storage_scope="contract_only")   kept nothing
authorization_redirect_issued = False             hardcoded
```

Deny by default is preserved. The redirect happens only when every conjunct
holds, and any one missing returns the same structured refusal as before, named:

```text
provider_configured
authorization_url_available
state row actually written
can_sign_production_session
```

That last one is deliberately not `signing_key_present`. A key that exists but
is too short, or is the committed `local_dev_fixture`, must not start a flow
whose session it cannot legitimately sign.

The authorization URL carries the state, so it goes in a `Location` header and
nowhere else — never a response body, never a log.

The route takes a bare `get_db` session, not `deps_db.get_org_context_with_db`.
These routes replace the dev org header and must not consume the RLS context it
sets.

## Callback status: full flow, real provider

`GET /api/auth/callback` runs the real sequence and refuses by name at each
stage:

```text
provider error      -> no exchange attempted
state consumed      -> verifier recovered, or refuse
token exchange      -> tokens, or refuse
ID token verified   -> identity, or refuse
organization        -> where it stops
```

Measured against Google in a browser:

```text
state_validated             true
pkce_validated              true
state_replay_detected       false
token_exchange_attempted    true
token_exchange_succeeded    true
token_exchange_http_status  200
identity_validated          true
identity_verification_state verified
identity_email_domain       gmail.com
```

## Token exchange status: working, and narrow

`oidc_token_exchange_client_service` is the only place NativeForge posts an
authorization code. Registered at Gate 94's chokepoint alongside JWKS retrieval
and the discovery document.

```text
network             off unless a caller passes allow_network
endpoint            from the discovery document, not from a caller
scheme              https enforced before the request
return              (report, tokens) - two values, deliberately
```

Splitting the return is what makes "never log a token" a property of the type
rather than a rule somebody has to remember. The report is safe to log,
artifact and return; the tokens dict is for immediate use. Every branch was
exercised with an injected transport and **nothing leaked into any report** —
not the secret, code, verifier or ID token.

ID token validation is `oidc_token_verification_service`, which already existed
and does it properly with JWKS. Exchanging and verifying stay separate: a module
that did both could report a verified identity from a response it had not
checked.

## Session minting status: refused, and correctly

**No session was created, and none could be.**

`customer_session_format_service` refuses a session with no organization. With
every other field supplied — principal, subject, session id, issued-at,
expires-at, signature — that is the *only* blocked reason:

```text
session_cookie_valid   false
blocked_reasons        ['session_without_an_organization_id']
```

Not an omission. Gate 112's rule expressed in the session format: an
organization claim says which, membership says they belong — both, or no RLS.

A session with a null organization would be rejected by the verifier anyway
(`session_cookie_carries_no_organization_id`), so minting one would produce a
cookie in name only. The permitted branch is reachable and tested: supply an
organization and `session_cookie_valid` is true, `production_session` is true.

Even then the verifier still refuses RLS context with
`membership_not_verified_for_this_organization` — the second half of Gate 112's
rule, and Gate 132's work.

## Cookie policy

```text
HttpOnly     true
SameSite     lax
Secure       follows the environment
```

`lax`, not `strict`, and the reason is recorded in the policy service: strict is
not sent on the top-level navigation back from the identity provider, so the
callback would arrive without the cookie.

The session payload never carries the email. `email` is accepted by
`build_session` and deliberately discarded, and the cookie value was checked for
the address directly.

## What never left the process

The authorization code, the PKCE verifier, the ID token and the access token are
locals in the callback. No branch returns, logs or stores any of them. The
response carries booleans, named reasons, and `identity_email_domain` — the
domain half of the verified address and nothing more.

No route set a `Set-Cookie` header at any point in the flow.
