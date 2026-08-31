# 687 — Gate 129: secret-safe auth settings

## The defect this closes

Gate 128 found that `.env` reaches the pydantic `Settings` object and never
reaches `os.environ`, while the auth preflight read `os.environ`. So auth keys
written into `.env` were invisible, silently.

Gate 129A found the worse half. The backend systemd unit carries:

```text
EnvironmentFile=-/home/josefgray/projects/nativeforge/.env
```

systemd parses that file into the **process** environment, so under the service
those same keys *do* reach `os.environ`. Ad-hoc `python -c`, `pytest` and a
hand-run `uvicorn` do not.

Two mechanisms, opposite answers, depending on how the process was started. That
is worse than one mechanism that plainly does not work, because it works often
enough to be trusted.

## What changed

Seven keys are now `Settings` fields:

```text
OIDC_ISSUER               str
OIDC_CLIENT_ID            str
OIDC_AUDIENCE             str
OIDC_CALLBACK_URL         str        optional, derived when unset
NF_PUBLIC_ORIGIN          str
OIDC_CLIENT_SECRET        SecretStr  secret
NF_SESSION_SIGNING_KEY    SecretStr  secret
```

And one resolution order serves every auth detector:

```text
os.environ wins, Settings fills the gaps.
```

`os.environ` keeps priority so an operator can override the file for a single
process, and so every existing test that sets an env var keeps working. A blank
value is unset rather than configured — the same rule the object-store detector
uses, because a field existing says nothing about an environment.

```python
auth_environment_overlay(environ=None, *, settings=None) -> dict[str, str]
auth_environment_presence(environ=None, *, settings=None) -> dict[str, bool]
```

## Callers moved onto it

```text
customer_auth_environment_preflight_service   build_environment_preflight
customer_auth_provider_readiness_service      build_provider_readiness
customer_session_format_service               signing-key presence and read
```

Three detectors, one order. Two answers to "is the issuer configured" is the
defect this campaign keeps finding.

## Secret handling

Both secrets are `SecretStr`, so `repr()`, `str()` and `model_dump_json()` all
render `**********`. A settings object reaching a log line or a traceback
carries no credential. A test asserts all three.

`.get_secret_value()` is called in exactly one place — `auth_environment_overlay`
— and the reason is worth stating, because the object-store secret's docstring
says nothing in NativeForge calls it and that remains true of *that* key.

The auth detectors answer "is a secret present" by reading an environment
mapping. The value has to enter that mapping to be counted. It is an in-memory
dict holding what `os.environ` already holds; what protects the value is that
every auth service redacts on the way out — Gate 121's `SECRET_VALUE_KEYS`, and
a Gate 129 test asserting no artifact carries an environment value.

## What did not change

Configuration is still not activation. Setting all seven keys makes
`provider_configured` true and nothing else. `customer_auth_live` needs a real
callback, a signed session, a resolved organization and a verified membership —
and separately, owner approval, which is Mayhem's decision alone.

## Where the values go

`.env` in the repository root now works, and is gitignored (`.gitignore:19`).
An exported environment variable works. An `EnvironmentFile` on the unit works.
All three now agree.

Edit the file in an editor rather than appending from the shell — an append puts
the secret in shell history. Do not use `env`, `printenv`, `set -x` or `cat` to
verify; use the presence helper, which returns booleans:

```bash
cd /home/josefgray/projects/nativeforge && .venv/bin/python -c "from nativeforge.lib.settings import auth_environment_presence as p;[print(f'{k:26s}{v}') for k,v in p().items()]"
```
