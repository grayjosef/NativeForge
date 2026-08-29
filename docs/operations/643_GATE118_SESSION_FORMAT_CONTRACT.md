# 643 — Gate 118B: the customer session format

`src/nativeforge/services/customer_session_format_service.py`

## The format

```text
nf1.<base64url(payload_json)>.<base64url(hmac_sha256(payload, key))>
```

Three parts, dot-separated, all URL-safe. The version prefix exists so a later
format can be introduced without a verifier having to guess which one it is
looking at — an unversioned credential format is one nobody can ever change.

## Why signed rather than opaque-and-looked-up

A signed value verifies without asking a database. That matters here
specifically: Gate 118A found no session table, and this gate deliberately adds
none.

The cost is stated rather than discovered later — **a signed session cannot be
revoked before it expires.** Logout clears the cookie; it cannot un-sign a value
already issued. That is why the lifetime is bounded at seven days, defaults to
eight hours, and why Gate 116B requires rotation.

## expires_at lives inside the value

Gate 116B set the cookie's `Max-Age`. A cookie lifetime is a *request to the
browser* — a browser that ignores it, or an attacker replaying a captured
cookie, is unaffected. So the payload carries its own `expires_at` and the
verifier checks it server-side.

## The payload carries no email

```text
v  sid  pid  sub  org  roles  iat  exp  src  email_omitted
```

An email in a cookie is personal data travelling on every request to every
route, readable by anything that can see the cookie jar. The subject and the
organization are what a route needs; the email is looked up when it is actually
wanted.

`build_session` accepts an `email` parameter and discards it. A test plants one
and asserts it appears neither in the result nor in the decoded payload, and an
invariant fails any result carrying an `email` field.

## organization_id must be UUID-shaped

Gates 110–113 at the session layer. A profile id is a real value from a real
column in the wrong identity space, and every RLS policy casts to `::uuid`.

The interesting case is in the fixture set: a session carrying a profile id,
**signed genuinely**, is still refused. Signing something does not make it an
RLS authority.

## Signing keys

`signing_key_present` is a boolean. The key is compared inside `hmac.digest` and
never returned, logged, or placed in a field — there is no field for one, and an
invariant refuses any result carrying `signing_key`, `secret` or `key`.

Gate 118A found no signing key configured anywhere in NativeForge, so
`production_session` is false for every session this service can build today.
The two "signing-ish" settings it found are S3 object-store credentials.

## Fixture sessions are not production sessions

`build_fixture_session` signs with `FIXTURE_SIGNING_KEY`, an obviously-fake
committed constant, and marks the result `demo_fixture: True`. Two invariants
guard the boundary: a fixture may never be production, and a production session
requires a configured key.

A fixture session is exactly as cryptographically valid as a real one *under its
own key*. The difference is which key, and whether anybody could have obtained
it — which is why the distinction is a field rather than a convention.
