# 545 — Gate 97A: object body store survey

## Settings pattern

`src/nativeforge/lib/settings.py`, pydantic-settings:

```python
class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env",), env_file_encoding="utf-8", extra="ignore"
    )
    app_name: str = Field(default="NativeForge", validation_alias="NF_APP_NAME")
    database_url: str = Field(default="sqlite+...", validation_alias="DATABASE_URL")
```

Five fields today. Every one is `Field(default=..., validation_alias="ENV_NAME")`,
and `get_settings()` is `@lru_cache`d with `get_settings.cache_clear()` called by
an autouse conftest fixture — so a test can set an env var and get fresh
settings. Gate 97's six new fields follow that convention exactly.

`.env` exists and is **already gitignored** (`.gitignore:19`). Its contents were
not read.

## Storage clients: none, and none is being added

```text
grep -icE "boto3|botocore|minio|s3fs|aioboto3" uv.lock pyproject.toml
  uv.lock       0
  pyproject.toml 0
```

No object/blob abstraction exists anywhere in `src/nativeforge/`. There is no
`storage` package.

**A dependency is not required for this gate, and none is added.** The gate's
own instruction prefers it: *"prefer avoiding it in this gate by defining the
seam and using injected clients only."* The S3 service takes a client object and
calls `put_object` on it; a test injects a fake. `uv.lock` is untouched.

That is not a shortcut — it is the correct shape. A body store the tests can
exercise fully without a network, a credential or a vendor is a body store whose
logic is actually tested rather than mocked around.

## The Gate 96 detector has a defect this gate exposes

```python
def _configured_settings() -> list[str]:
    fields = set(getattr(Settings, "model_fields", {}) or {})
    return [name for name in REQUIRED_SETTINGS if name in fields]
```

It checks whether the **field exists on the model**, not whether it has a value.
That was harmless while no such fields existed — the answer was correctly "none
of them". The moment Gate 97 adds the six fields with empty defaults, this would
report all six *present* and flip `body_store_configured` to true on a checkout
with no credentials at all.

So the detection moves to **values**: present, non-blank, and non-placeholder.
This is exactly the failure mode this campaign keeps finding — a check that
reads a declaration rather than the thing declared.

## The client requirement moves, and why

Gate 96's `detect_body_store_mode` required an *installed* client:

```python
if clients and len(settings_present) == len(REQUIRED_SETTINGS):
```

With an injected-client seam that test is now the wrong one. The client arrives
at call time; requiring it to be importable would mean `body_store_configured`
could never be true no matter how correctly an operator configured their
environment.

So Gate 97 splits one fact into two, which is what the gate's artifact spec
already asks for:

```text
body_store_implementation_available   the service exists and exposes a writer
body_store_configured                 six settings, real values
```

Production availability requires **both**, plus the metadata table, the secret
scanner and the promotion gate — five components, up from Gate 96's four.
Splitting the fact does not loosen the verdict; it makes each half checkable.

## Setting names

```text
RAW_PAYLOAD_OBJECT_STORE_ENDPOINT
RAW_PAYLOAD_OBJECT_STORE_BUCKET
RAW_PAYLOAD_OBJECT_STORE_REGION
RAW_PAYLOAD_OBJECT_STORE_ACCESS_KEY_ID
RAW_PAYLOAD_OBJECT_STORE_SECRET_ACCESS_KEY
RAW_PAYLOAD_OBJECT_STORE_FORCE_PATH_STYLE
```

Gate 96 named three (`..._CREDENTIAL` as one field). Gate 97 replaces that with
the five S3 fields plus the path-style flag, because "credential" as a single
opaque field cannot express an access key and a secret that need different
handling — one is safe to report present, the other must never be rendered.

## Can production be marked configured without live proof?

**Configured, yes. Available, yes. Live, no.**

- `body_store_configured` is a statement about settings, and settings can be
  verified without contacting anything.
- `production_raw_payload_store_available` means every component exists. It still
  does not mean a write has ever succeeded.
- `production_storage_live` additionally requires an active collector, and there
  are none.

What no flag in this gate asserts is that the bucket exists, the credential is
valid, or a round-trip works. That needs a real connection and belongs in a gate
with an approved environment — the same distinction migration 0027 drew with
*"staging/dev proof first. No production customer claim."*

## Preventing secret leakage

```text
secret_access_key       pydantic SecretStr — repr is "**********", not the value
readiness output        credential_present: true/false, never a value
artifacts               no credential field at all; scanned by the Gate 95
                        scanner in a test
logs                    the body store logs nothing; the S3 service has no
                        logger and no print
.env                    already gitignored
placeholders            a value that looks like a placeholder is not
                        configuration
```

The last one matters more than it looks. `AKIAIOSFODNN7EXAMPLE` is AWS's own
documentation key and appears in a thousand tutorials; treating it as a real
credential would mark a demo environment production-configured. A placeholder
list is checked and a test asserts each entry is refused.
