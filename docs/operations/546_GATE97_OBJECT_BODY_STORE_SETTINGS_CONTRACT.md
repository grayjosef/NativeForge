# 546 — Gate 97B: object body store settings contract

**A body-store implementation exists. No live object store was contacted, and
none is configured.** No collectors were activated, no live source coverage is
claimed, and secrets are never surfaced.

## Six settings

```text
RAW_PAYLOAD_OBJECT_STORE_ENDPOINT          required
RAW_PAYLOAD_OBJECT_STORE_BUCKET            required
RAW_PAYLOAD_OBJECT_STORE_REGION            required
RAW_PAYLOAD_OBJECT_STORE_ACCESS_KEY_ID     required
RAW_PAYLOAD_OBJECT_STORE_SECRET_ACCESS_KEY required, secret
RAW_PAYLOAD_OBJECT_STORE_FORCE_PATH_STYLE  optional
```

They follow the existing convention exactly — `Field(default=...,
validation_alias="ENV_NAME")` on the pydantic-settings `Settings` model, read
from the environment or `.env`, which is already gitignored.

Gate 96 named three, folding credentials into one opaque `..._CREDENTIAL`
field. That could not work: an access key id is safe to report present, a
secret key is not, and one field cannot carry two handling rules.

## Values, never fields

Gate 96's detector checked whether the **field existed on the model**:

```python
fields = set(getattr(Settings, "model_fields", {}) or {})
return [name for name in REQUIRED_SETTINGS if name in fields]
```

That was correct only while no such fields existed. Adding them with empty
defaults would have flipped a credential-free checkout to "fully configured" —
a check reading a declaration rather than the thing declared, which is the
failure this campaign keeps finding.

Detection now reads values:

```text
absent      -> unconfigured
blank       -> unconfigured
placeholder -> unconfigured
real, all five -> s3_compatible_configured
```

## A placeholder is not configuration

`AKIAIOSFODNN7EXAMPLE` is AWS's own documentation key and appears in a thousand
tutorials. A checkout that pasted it is not a production environment, and
treating it as one would mark a demo as production-configured.

Twenty known placeholder values are refused, plus any value containing
`example`, `changeme`, `placeholder`, `your-`, or angle brackets. Five are
parametrized into a test.

## The secret is a SecretStr

```text
repr(settings)                     -> no value
repr(settings.…secret_access_key)  -> SecretStr('**********')
str(settings.…secret_access_key)   -> **********
```

The value is reachable only through an explicit `.get_secret_value()`, which is
called in exactly one place — the body-store contract's detector, to measure
whether it is empty — and never returned from there.

Readiness output reports `credential_present: true/false`. **No value is
rendered anywhere, not even masked**: a masked value still leaks its length.

A test configures a synthetic credential and asserts it appears in none of the
body-store contract, the production readiness report, the client config, the
activation preflight, or the Phase 1 matrix. A second test writes the artifacts
*with a configured environment* and asserts none of the four files contains it —
which is the case that actually matters, since an unconfigured environment has
nothing to leak.

## A blank boolean must not crash the app

`RAW_PAYLOAD_OBJECT_STORE_FORCE_PATH_STYLE=` is an ordinary way to write "leave
this alone" in a `.env` file. Pydantic raises on it, and that exception takes
the whole `Settings` object — and therefore the app — down over an empty line in
a config file.

A `mode="before"` field validator maps blank to `False`. Found while writing the
tests, and fixed in the settings rather than worked around in the test.
