# 637 — Gate 117B/F: the customer auth dependency

```text
src/nativeforge/services/customer_auth_dependency_contract_service.py
src/nativeforge/api/auth.py
```

NativeForge returns its first 401 in this gate.

## Four modes

```text
required   refuses an unauthenticated caller with 401
optional   permits one, and reports authenticated false
forbid     refuses an authenticated caller
unknown    refuses everybody
```

`forbid` exists because there will be routes where an existing session is
wrong: starting a fresh authorization flow while holding one invites session
fixation, where an attacker completes a flow into a victims established cookie.

`unknown` refuses everybody, because a route whose auth mode nobody declared is
a route nobody thought about.

## Which route got which

```text
/login         optional   200, structured refusal
/callback      optional   200, refuses to mint a session
/logout        optional   200, clears the cookie
/session       optional   200, authenticated false
/current-user  required   401
```

`/session` is optional deliberately: a caller asking whether they have a session
should be told no, not refused for not having one. Gate 116 declared it
`security_required: True`, which read correctly before there was a dependency to
make the distinction, and is now false.

## Enforcement is not liveness

This is the distinction the gate turns on, and it is asserted in both directions:

```text
a dependency in required mode refuses unauthenticated callers   -> enforcement
nobody can authenticate, so everybody is refused                -> not liveness
```

A 401 proves the application can say no. It proves nothing about whether anyone
could ever be told yes, and `customer_auth_live` stays false.

## The RLS boundary

`sets_rls_context` is false unless **both** an `organization_id` was resolved
per Gate 112 *and* a membership was verified. A principal is neither, and each
half alone is insufficient - both branches are tested.

The branch where it is true is reachable in a test, so today false is a
measurement rather than a constant. In that same result `customer_auth_live` is
still false, because it is measured from the real environment rather than from
the forged inputs.

## No cookie value is read

The dependency receives the cookies *presence*, never its value. Nothing parses,
decodes or logs it - there is no session format to parse it against, and a value
that reached a log would be a session anybody could replay. A test plants a
value and asserts none of the five routes echoes it.

## The security scheme

Attached to `/current-user` and to nothing else, through `openapi_extra` rather
than a `Security(...)` dependency: the dependency reads a plain `Cookie` and
raises, which enforces correctly and tells FastAPIs schema generator nothing.

Only `required` mode advertises. A scheme on an optional route would tell a
reader a credential is needed when it is not.

Product routes remain unsecured. Each would need its own tested auth path and
none has one.
