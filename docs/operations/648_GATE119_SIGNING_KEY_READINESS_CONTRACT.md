# 648 — Gate 119B: the signing key readiness contract

`src/nativeforge/services/customer_auth_signing_key_readiness_service.py`

## What Gate 118 could not tell you

Gate 118B answered one question about the signing key: is there one?

```python
def signing_key_present() -> bool:
    return bool((os.environ.get(SIGNING_KEY_ENV) or "").strip())
```

That boolean cannot distinguish a key from a secret manager from the committed
fixture key printed in this repository's own source. Both are "present". One of
them is held by everyone who has ever cloned the repo.

A session layer that cannot tell them apart will eventually sign a production
session with a demo secret, and nothing will fail loudly when it does.

## Five sources, two of which may sign

```text
environment        NF_SESSION_SIGNING_KEY is set and is not the fixture
secret_manager     supplied by a managed store, asserted by the caller
local_dev_fixture  the committed fake
missing            nothing is set
unknown            a source name this service does not recognise
```

`environment` and `secret_manager` may sign a production session.
`local_dev_fixture` may not, ever — an invariant refuses any result that says
otherwise, and the fixture set has a case for exactly that.

Naming the source rather than returning a boolean is the whole design. "There
is a key" and "there is a key we would stake a customer's session on" are
different claims, and one field cannot carry both.

## Length is a floor, and entropy is not scored

HMAC-SHA256 accepts a key of any length and produces the same output size. A
one-character key produces a perfectly well-formed signature. Nothing fails; the
signature just becomes guessable.

```text
MIN_KEY_LENGTH             32   the digest size. Shorter buys nothing.
MIN_DISTINCT_CHARACTERS     8   "ababab..." is long and is not a key
```

Entropy is deliberately **not** estimated. A high estimate on a short string and
a low one on a passphrase are both misleading, and a service that scored keys
would be manufacturing confidence it does not have. What is checked is length,
character variety, and whether the value is the known fixture.

## Derived beats declared

`declared_source` exists so a caller can say where it thinks a key came from. It
is honoured only when it agrees with detection:

```text
declared: environment
detected: local_dev_fixture
result:   local_dev_fixture, plus a blocked reason naming the contradiction
```

That is this campaign's recurring defect class, addressed at the point where it
would do the most damage. A caller asserting `environment` over the committed
fixture is the shape of a bug, and detection wins.

## Rotation is false, and reported

Rotation is implemented nowhere in NativeForge. This service says so rather than
omitting the field:

```text
signing_key_rotation_supported   false
next_required_actions            implement_signing_key_rotation
```

It is **not** a blocked reason. A key without rotation still signs. But Gate
118B established that a signed session cannot be revoked before it expires —
rotation is how a leaked key gets answered, and its absence is a real gap. A
reported gap is worth more than a missing field.

## The value never leaves, and it is checked

There is no field for the key. `secret_value_exposed` is a self-check: the
result is serialised and searched for the material it was handed, and an
invariant fails if it is ever true.

Material shorter than eight characters is not searched for — a two-character key
would match by coincidence inside a schema version and report a leak that did
not happen.

A test plants a key and asserts it appears nowhere in the output.

## Sign and verify cannot diverge

```python
can_verify = bool(can_sign)
```

Written as a derivation rather than a duplicated conjunction, with an invariant
that fires if the two ever disagree. One symmetric key does both jobs today. If
an asymmetric format is introduced later, that invariant is the thing that
should notice — a verify-only key would be legitimate then, and is a bug now.

## What it reports in the actual environment

```text
signing_key_present              false
signing_key_source               missing
signing_key_length_ok            false
signing_key_rotation_supported   false
can_sign_production_session      false
can_verify_production_session    false
secret_value_exposed             false
blocked_reasons                  no_signing_key_configured
next_required_actions            set_NF_SESSION_SIGNING_KEY_out_of_band_...
```

This is now the sixteenth activation gate, and it is in both
`REQUIRED_AUTH_GATES` and `REQUIRED_LOGIN_GATES`: login *is* the act of issuing
a session, so it needs the key that signs one.
