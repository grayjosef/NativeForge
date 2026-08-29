# 644 — Gate 118C/E: the session verifier

```text
src/nativeforge/services/customer_session_verifier_service.py
src/nativeforge/services/customer_auth_dependency_contract_service.py
src/nativeforge/api/auth.py
```

## What Gate 117 left behind

```python
# api/auth.py, Gate 117
# No session format exists, so no cookie can be valid. Stated as a
# derivation rather than a constant so it moves when one does.
valid = False
principal_resolved = False
```

Gate 117 wrote that comment expecting this gate. The cookie is now verified
rather than assumed invalid — and it still comes out invalid, because no signing
key is configured.

**That is a different fact from before.** Gate 117 reported false because
nothing could be checked; Gate 118 reports false because the check runs and
fails.

## Six things that can be wrong

```text
cookie_present      nothing was sent
cookie_parseable    three parts, known version, decodable base64 JSON
signature_valid     the payload was not altered, and we signed it
session_expired     the value carries its own expiry and it has passed
organization_id     UUID-shaped, because every RLS policy casts to ::uuid
membership          a record backs the organization the session names
```

The order matters for what is reported, not for safety — every one is required.
But a caller who gets "malformed" learns something different from one who gets
"expired", and `/api/auth/session` now returns those booleans so a caller can
tell which.

## Three separate outputs

```text
session_cookie_valid            the value is genuine and unexpired
auth_dependency_can_authorize   ...and a principal came out of it
rls_context_allowed             ...and an organization resolved and a
                                membership was verified
```

Gate 112's rule at the verifier: **a valid session is not an organization.** A
signed cookie proves somebody held a credential we issued. It does not prove the
organization named inside it is one they still belong to — memberships get
revoked, and a session outlives the revocation until it expires.

So `membership_required` is always true and `membership_verified` is an input
this service will not invent. `/api/auth/session` passes `False` deliberately
rather than omitting it: a membership record is a database question that route
does not ask.

## A valid session does not make customer auth live

A fixture session can be perfectly valid under a fixture key while nobody in the
world can authenticate. `customer_auth_live` is measured from Gate 115's
activation gate and reported alongside, so the two cannot be confused.

The fixture set has a row for exactly this: `valid_session_with_membership`
reaches `rls_context_allowed: True` with `customer_auth_live: False`.

## The dependency reads the verification, not the caller

`evaluate_auth_dependency` gained a `session_verification` parameter. When one
is supplied it overrides the individual booleans, because a verifier that looked
at the cookie is a better source than a caller asserting what it would have
found. A caller passing `principal_resolved=True` alongside a verification that
found no principal is the shape of a bug, and the verification wins.

The individual parameters remain for tests isolating a single conjunct.

## Nothing echoes a cookie

The value goes into the verifier and no further. An invariant refuses any result
carrying `session_cookie_value`, `cookie`, `cookie_value`, `signing_key` or
`signature`, and a test plants a cookie value and asserts none of the five auth
routes returns it. A session value in a response body is a session anybody can
replay.
