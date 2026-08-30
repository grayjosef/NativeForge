# 657 — Gate 121B: the auth environment preflight

`src/nativeforge/services/customer_auth_environment_preflight_service.py`

## What it reports, and what it will not

```text
reported     the NAME of a missing key            OIDC_CLIENT_SECRET
             whether something is set             true / false
             where a signing key came from        secret_manager
             a redacted host and path             app.example.test/api/auth/callback

never        the value of any environment variable
             a secret, a token, a session, a state, a verifier
             a connection string
```

`secret_values_exposed` is a self-check rather than a promise: the assembled
result is serialised and searched for every configured secret value, and an
invariant fails if one appears. A test plants a value in three keys at once and
asserts none reaches the output.

## Missing keys are named; present ones are not

There is no `provider_env_present_keys`. A list of which variables a deployment
holds, combined with a process listing, is most of the way to a map of that
deployment. Absence is actionable; presence is only reassuring.

## A false positive the first run caught

The leak scanner originally checked every key the module inspects, including
`NF_PUBLIC_ORIGIN`. It fired immediately — because the redacted callback URL
*correctly* contains the public origin.

```text
OIDC_ISSUER      a public hostname every browser is sent to
OIDC_CLIENT_ID   public by design; it appears in every redirect
OIDC_AUDIENCE    a public API identifier
NF_PUBLIC_ORIGIN the thing the redacted callback is supposed to contain
```

The scan now covers `OIDC_CLIENT_SECRET`, `NF_SESSION_SIGNING_KEY`, the
approval token and `DATABASE_URL`. A leak detector that fires on intended output
trains people to ignore it, which is worse than not having one.

## The callback comparison, and the defect it found

Gate 121A found the configured callback URL points at a path that exists in
neither the API nor the frontend:

```text
configured      http://localhost:5173/auth/callback
API route       /api/auth/callback
frontend route  none - the frontend declares no routes at all
```

A boolean about "configured" cannot catch that, because the value *is*
configured. `callback_path_matches_route` compares the path and is false today.

Registering that value provider-side and completing a login would land a real
browser on a 404 holding a live authorization code. The code would then be
burned, and the failure would look like a provider problem rather than a
configuration one.

The origin comparison is three-valued on purpose:

```text
no public origin configured   we have not been told what to compare against
configured and different      the callback points somewhere else
configured and equal          they agree
```

Collapsing the first two would report a mismatch nobody could act on.

## The database is reported and is not a gate

```text
database_revision          "" - no runtime database has applied anything
required_database_revision 0030
database_revision_ready    false
```

A login that completes and then cannot write a redirect state row has failed in
a way no activation gate would have caught. It is reported beside the sixteen
gates rather than folded into them, because it fails differently and is fixed
differently.

Detection goes through Gate 113's decision service, which already answers this
and already refuses to open a connection it does not have. Duplicating the
detection here is how the two would come to disagree.

## Nothing is contacted

```text
network_validation_allowed     false, and nothing in this gate raises it
provider_validation_attempted  false unless allowed AND a result was supplied
provider_validation_passed     false unless attempted AND it passed
```

Three booleans rather than one. An invariant refuses any result claiming a
validation passed that was never attempted, and a test forges exactly that and
asserts the invariant fires.

## Every input is injectable, and the fully-ready branch is reachable

Eight parameters — environment, app env, callback, origin, database revision,
signing key readiness, cookie policy, dev header readiness. With all eight
supplied correctly the preflight reports **zero blocked reasons and zero next
required actions**, and `customer_auth_live` is still false.

That branch had to be made reachable during the gate: cookie policy and dev
header facts were initially read from the real environment only, which made
"fully ready" impossible to reach and every refusal above it unfalsifiable.
Gates 117 through 120 each shipped that same defect once.

Injecting a value does not make it true of this machine. With nothing supplied
the real environment is read, and it reports five missing keys.

## What it says about the actual environment

```text
environment_name                    local
provider_env_missing_keys           OIDC_AUDIENCE, OIDC_CLIENT_ID, OIDC_ISSUER
secret_env_missing_keys             NF_SESSION_SIGNING_KEY, OIDC_CLIENT_SECRET
signing_key_source                  missing
callback_path_matches_route         false
public_origin_configured            false
database_revision_ready             false
dev_header_production_blocker       true
customer_auth_live                  false
```
