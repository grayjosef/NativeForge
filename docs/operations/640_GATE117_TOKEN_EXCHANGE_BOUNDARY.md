# 640 — Gate 117E: the token exchange boundary

`src/nativeforge/services/customer_auth_token_exchange_boundary_service.py`

The one place in NativeForge that would ever send a client secret over the
network, and the reason it does not.

## Why a boundary rather than an implementation

Token exchange posts the client secret and an authorization code to the provider
and receives an identity in return. Everything about it is irreversible: a
leaked secret is leaked, a code redeemed by the wrong party is redeemed.

So this service decides *whether* an exchange may happen and never performs one.
`token_exchange_performed` is a constant `False`, and an invariant fires if any
result claims otherwise — including one that claims it while allowed.

## Six conditions, all required

```text
provider_configured    an issuer, client id and audience are present
secret_present         a client secret is present, as a boolean
callback_code_present  the provider actually returned a code
state_validated        the browser that started the flow finished it
pkce_validated         the client that started the flow is redeeming the code
network_call_allowed   somebody deliberately turned the network on
```

The first five decide whether an exchange *should* happen. The sixth decides
whether it *may*, and it is separate on purpose: a flow satisfying every
security condition must still not reach the internet by accident during a test
run or an artifact regeneration.

**It defaults to false and nothing in this repository raises it.** A test
satisfies the other five and asserts
`missing_conditions == ["network_call_allowed"]` — one thing left, and it is not
a security condition.

## Nothing here handles a secret or a token value

`secret_present` is a boolean from `auth0_preflight_service`, which reads
`os.environ` for presence only. This service never reads the value, never
receives one as a parameter, and never returns one. There is no code path here
that could print a secret, because there is no code path here that has one.

The same for tokens: `id_token_received` is a boolean. An invariant refuses any
result carrying a field named `id_token`, `access_token`, `refresh_token`,
`client_secret`, `code`, `authorization_code` or `token`, and the artifact
writer walks every nested structure looking for the same names before writing
anything to disk.

## Two ordering invariants

```text
id_token_received without token_exchange_performed   -> a token from no exchange
claims_verified without id_token_received            -> claims from no token
```

Both are impossible states that would indicate somebody had started filling
fields in optimistically, which is how a contract stops describing reality.
