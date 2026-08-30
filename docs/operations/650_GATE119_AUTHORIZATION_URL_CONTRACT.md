# 650 — Gate 119D: the authorization URL

`src/nativeforge/services/customer_auth_authorization_url_service.py`

## The first URL builder in the repository

Gate 119A searched for one and found nothing:

```text
authorization_endpoint      0 files
response_type               0 files
urlencode                   0 files
quote_plus                  0 files
/authorize                  0 files
urlparse                   11 files   all HTML scrapers
urljoin                     3 files   all HTML scrapers
```

The fourteen `urlparse`/`urljoin` hits are listing adapters resolving relative
hrefs on grant pages. None is auth code. That check has now been the fifth
substring-versus-meaning question this campaign has had to answer, and the first
to come back with a clean zero on the terms that mattered.

## Building a URL is not visiting one

This module performs string construction and nothing else. There is no HTTP
client, no import that could acquire one, and no code path that resolves a
hostname. `provider_called` is a constant `False` and an invariant refuses any
result claiming otherwise.

That distinction is why an authorization URL can exist while
`network_call_allowed` stays false: the **browser** visits the URL, and no
browser is involved in a test.

The authorize endpoint is derived as `{issuer}/authorize` — the conventional
path. Discovery would fetch it from the issuer's well-known document, which is a
network call this gate does not make.

## The client secret is never in the URL

An authorization request carries the client **id**, which is public by design —
it appears in every redirect a user's browser makes. It never carries the client
**secret**, which is presented once at token exchange over a back channel.

A secret in a query string is a secret in browser history, in the provider's
access logs, in every proxy between them, and in the `Referer` header of
whatever the callback page loads next.

No parameter of `build_authorization_url` accepts a secret, because no part of
an authorization URL takes one. `secret_exposed` is derived by scanning the
constructed URL for the configured secret value — a check that should be
unfalsifiable, and is run anyway, because "should be" is what an invariant
exists to stop being an assumption. A test plants a secret in the environment
and asserts it reaches no URL.

## State and PKCE are required, not optional

```text
no state    the callback cannot tell a genuine return from a forged one
no PKCE     an intercepted authorization code can be exchanged by whoever
            intercepted it
```

Both are omissible in the OAuth specification. Neither is omissible here. A URL
missing either is not built, and the reason is named.

`plain` as a challenge method is refused. It is legal in RFC 7636 and it defeats
the purpose of PKCE: the verifier and the challenge are the same string, so an
interceptor who sees one has both.

## Provider config gates the URL; it does not gate the state

This separation is what the gate turns on.

```text
/login can generate a state and a PKCE pair with no provider configured at all.
The generator is local - `secrets` and `hashlib`.

What provider configuration gates is whether those values can be placed
in a URL.
```

Keeping them apart is what lets `/login` report `state_issued: True` and
`authorization_url_available: False` in the same response — which is exactly the
state NativeForge is in, and which a single conflated boolean could not express.

## A defect found during the gate

`build_redirect_flow_contract` derived availability like this:

```python
authorization_url_available = bool(provider_configured)
```

A declared fact standing in for a derived one, and it never checked the redirect
URI at all. It now calls this service. But making that change alone made
`authorization_url_available: True` **unreachable**: a caller injecting
`provider_configured=True` got a builder reading an empty environment.

`issuer` and `client_id` are now parameters of the flow contract too. Supplying
provider configuration means supplying all of it. This is the third time in
three gates that adding a conjunct without making it injectable produced an
unreachable branch — Gate 117 and Gate 118 each learned it once.

## Only redacted URLs are published

```text
authorization_url            built, measured, never written to a file
authorization_url_redacted   state and challenge replaced by placeholders
```

The artifact writer gained a fourth scan for this. A URL is one string whose
field is called `authorization_url`; a field-name scan waves it straight
through while it carries a live state in a query parameter.

```python
_STATE_PARAM_RE = re.compile(r"[?&]state=([^&\s\"]+)")
_CHALLENGE_PARAM_RE = re.compile(r"[?&]code_challenge=([^&\s\"]+)")
```

Anything that is not the placeholder refuses the write. A test feeds the scanner
a live fixture URL and asserts it fires — a scanner that cannot fail proves
nothing about the files it passed.

That the fixture state is fake is beside the point. A rule that depended on
remembering which values were fake would eventually meet one that was not.

## What it reports in the actual environment

```text
provider_configured                 false
issuer                              (empty)
authorization_endpoint_configured   false
client_id_configured                false
redirect_uri_configured             false
scope                               openid profile email
state_bound                         false
pkce_bound                          false
authorization_url_available         false
authorization_url_returned          false
provider_called                     false
secret_exposed                      false

blocked_reasons
  no_issuer_configured_set_OIDC_ISSUER
  no_client_id_configured_set_OIDC_CLIENT_ID
  no_redirect_uri_supplied
  no_state_bound_to_the_authorization_request
  no_pkce_challenge_bound_to_the_authorization_request
```

Three named settings rather than one blanket "provider not configured". An
operator needs to know which one to supply.
