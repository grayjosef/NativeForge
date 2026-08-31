# 684 — Gate 128: auth activation execution survey

Gate 121 built the runbook and measured what activation would need. This gate
tried to walk it. What follows is what the runtime said, not what the services
report about themselves.

## The short answer

Activation is blocked on operator configuration that does not exist yet, and on
a process that is not running. Three things moved, and all three were inside the
repository's reach:

```text
runtime database        0024, half-applied      ->  0035, all tables present
callback URL            frozen wrong literal    ->  derived from environment
database blocker        unclearable constant    ->  reads the actual database
```

Seven of the eight activation blockers remain, and none of them can be cleared
by code.

Three defects found. The first two are the same defect:

```text
the callback URL    a value nobody configured, reported as configured
migration_applied   a database nobody read, reported as unapplied
```

Both were constants wearing the shape of a measurement. One claimed more than
the world, the other less.

The third is a gap between two config mechanisms: `.env` reaches
pydantic-settings and never reaches `os.environ`, and the auth preflight reads
`os.environ`. Setting the auth keys the way the runbook implies would have
changed nothing, silently. Documented rather than fixed — see below for why.

## What is actually running

```text
nativeforge-demo-preview.service    active   vite preview, 127.0.0.1:5175
nativeforge-mayhem-tunnel.service   active   cloudflared -> 127.0.0.1:5175
```

`ss -ltnp` shows two listeners: node/vite on 5175 and cloudflared's metrics port
on 20242.

**There is no API process.** `nativeforge-demo-preview` serves `frontend/dist`
as static files. Nothing is bound to 8000. Nothing serves `/api/auth/login` or
`/api/auth/callback`, and the public origin returns 404 for them.

This is the fact that decides 128F. A browser callback smoke test needs a
process that can consume a callback, and there is not one. The tunnel is
pointed at a static file server.

## The database

Identity was never ambiguous, so `DB_TARGET_UNKNOWN` does not apply:

```text
scheme            sqlite+pysqlite
credentials       none
path              nativeforge.local.db      (gitignored, .gitignore:27)
```

It was, however, in a state no revision describes:

```text
alembic_version                   0024
organizations.display_name        present   <- added by 0025
organizations.seat_cap            present   <- added by 0025
organizations.created_at          ABSENT    <- added by 0025
```

Migration 0025 adds three columns. Two were applied and the third was not, while
the version table still read 0024. A plain `alembic upgrade head` failed against
a copy at the first statement of 0025:

```text
sqlite3.OperationalError: duplicate column name: display_name
```

The obvious hypothesis was that 0025 is unrunnable on SQLite — it adds a
`NOT NULL` column with a `now()` server default, which SQLite rejects through
`ALTER TABLE`. **That hypothesis was wrong.** A fresh SQLite database migrates
cleanly to 0035, because on a fresh build the column arrives with the table
rather than through an `ALTER`. The half-applied state came from an interrupted
run, not a defective migration. Worth recording because the wrong diagnosis
would have led to editing a migration that works.

Every step above ran against copies. The runtime file was opened read-only and
re-read afterwards to confirm it had not changed.

## The callback URL, and why it was never a typo

Gate 121 reported the configured callback as `http://localhost:5173/auth/callback`
against an API route of `/api/auth/callback` and called it a path mismatch. The
mismatch is real, but it is a symptom.

The value came from here:

```python
# oidc_config_schema_service.py, before
"callback_url": "http://localhost:5173/auth/callback",
"allowed_redirect_uris": ["http://localhost:5173/auth/callback"],
```

A frozen literal. Not read from the environment, not derived from the route,
not configurable. Three consequences, in increasing order of seriousness:

```text
1  the port was never right      5173 is vite's default; the preview runs 5175
2  the path was never right      no API route and no frontend route serves it
3  redirect_uri_configured       reported TRUE, for a URL pointing at nothing
```

The third is the defect. This campaign has a name for it: a constant frozen in
one gate becomes a lie in the next. Block 39 froze a local-dev checklist value,
and every gate since has read it as a description of the runtime. A redirect URI
nobody configured has been reporting as configured the entire time.

Correcting the path alone would have preserved the defect — it would have
produced a *differently* wrong literal that still claimed to be configured.

### What replaced it

```text
OIDC_CALLBACK_URL set        use it
else NF_PUBLIC_ORIGIN set    origin + CALLBACK_ROUTE_PATH
else                         None
```

`CALLBACK_ROUTE_PATH` is imported from the preflight service rather than
restated, so the derived callback cannot drift from the route the API serves.
When nothing is configured the answer is `None` and
`allowed_redirect_uris` is empty — an unset redirect URI now reports as unset.

`logout_url` stays unset unless an operator sets it. It is tempting to derive it
from the API's `/logout`, but that route is a POST and a provider's post-logout
redirect is a page a browser lands on. Deriving one from the other would name a
target no browser can follow.

`force_unconfigured=True` previously zeroed the three env flags and then
returned the frozen callback anyway. It now returns `None` as well.

### The new invariant

```python
if callback and route and urlsplit(callback).path != route:
    fails.append("callback_path_does_not_match_route")
```

It fires on exactly the literal that used to be hardcoded, and it does not fire
on absence — an unset callback is honestly unset, not a violation. Six cases
were run against it, including the old literal, a correct explicit URL, an
origin with a trailing slash, and `force_unconfigured`.

## Environment configuration: what an operator still has to supply

Names and presence only.

```text
OIDC_ISSUER                      missing
OIDC_CLIENT_ID                   missing
OIDC_CLIENT_SECRET               missing
OIDC_AUDIENCE                    missing
NF_SESSION_SIGNING_KEY           missing
NF_PUBLIC_ORIGIN                 missing
OIDC_CALLBACK_URL                missing
NF_CUSTOMER_AUTH_ACTIVATION_APPROVAL   missing
```

The `.env` file holds two keys, `DATABASE_URL` and `NF_DEV_ORG_HEADERS`, and
neither is an auth key. Nothing about the identity provider has been configured
at any point.

This is not a gap this gate can close. Every one of those values comes from a
provider console and a secret manager, and four of them are secrets.

### And `.env` is not where they go

The third defect, found while writing the operator instructions — because the
instructions I first wrote would have silently done nothing.

```text
os.environ has DATABASE_URL             False
settings.database_url is set            True
Settings fields declaring an auth key   NONE
preflight reads the auth keys from      os.environ
```

`.env` is read by pydantic-settings, which populates the `Settings` object and
does not put anything into `os.environ`. `DATABASE_URL` works from `.env`
because `Settings` declares a field for it — which is also why
`_read_runtime_database_revision` finds the database through `get_settings()`.

No `Settings` field declares any auth key, and the preflight reads all five
straight from `os.environ`. So an operator who follows the Gate 121 runbook,
writes the values into `.env`, and re-runs the preflight sees every key still
missing with nothing explaining why.

Two config mechanisms, one repository, and the runbook does not say which
applies. The values have to be real environment variables in the API process —
an `EnvironmentFile` on the unit, or `set -a; . file; set +a` before uvicorn.

Left as documentation rather than code. Declaring the auth keys as `Settings`
fields is the better fix and the recommended next change, but it moves a client
secret into a settings object that gets repr'd and logged, which needs
`SecretStr` handling and a gate of its own rather than a late edit to this one.

## The blocker that could not clear, whatever was applied

Applying the migrations did not clear `database_not_at_revision_0030`. The
database read `0035` and the preflight still reported it as unapplied, which is
how the second defect surfaced.

The chain:

```python
# preflight
decision = build_binding_store_decision()      # no arguments
if not decision.get("migration_applied"):
    return ""

# the decision service
def build_binding_store_decision(*, database_revision: str | None = None, ...)
```

`database_revision` defaults to `None`, and **no caller anywhere ever supplied
it**. So `migration_applied` was `False` for every database that has ever
existed, and the blocker was unclearable by construction rather than by fact.

Gate 113 introduced that parameter, and its own comment says why:

```text
migration_defined  the revision file exists in this repository
migration_applied  a database has actually run it
```

> Both were reported as the single constant `migration_applied: False`. That
> was accidentally correct while no migration existed and no database existed.
> It would have become a lie the moment revision 0029 landed.

The split was right. The second half was still a constant, one indirection
down — accidentally correct for the same reason, and a lie from 0029 onward.
Nothing detected it for fifteen gates because nothing had ever applied
migrations to a runtime database and then asked.

### The fix supplies the fact, not a second detector

The rule for what counts as applied stays in Gate 113's decision service, which
remains a pure function. The preflight — already an environment prober, already
reading `os.environ` — reads the revision and passes it in:

```python
live = _read_runtime_database_revision()
decision = build_binding_store_decision(database_revision=live or None)
```

The read is read-only, never migrates, and returns `""` on any failure — no
database, no table, no connection. Absent must report as absent and never as
ready.

Both branches are asserted now, so neither can quietly become a constant again.

## The activation gate, after the database moved

```text
activation_allowed                False
customer_auth_live                False
login_live                        False
provider_configured               False
secret_present                    False
session_signing_key_ready         False
owner_approval_present            False
```

Blockers before this gate: 8. Cleared: 1 (`database_revision_not_applied`),
and it only cleared once the detector could see the database at all.
Remaining:

```text
provider_configuration_missing      operator, provider console
secret_configuration_missing        operator, secret manager
signing_key_not_fit_to_sign         operator, secret manager
owner_authorization_absent          Mayhem
dev_header_still_in_place           14 route modules
role_mapping_not_validated          needs a provider to validate against
callback_url_does_not_match_route   now derivable; was frozen
```

The last one changes character rather than clearing: with nothing configured
there is no callback URL to mismatch, and once `NF_PUBLIC_ORIGIN` is set the
derived value matches the route by construction.

## What 128F would need

Not a permission — a system. In order:

```text
1  an identity provider configured, with four env values and a secret
2  a session signing key
3  an API process running and reachable
4  the tunnel pointed at that process rather than at the static preview
5  the derived callback registered in the provider console
6  owner authorization
```

Steps 1, 2 and 6 are operator actions. Step 3 is a process nobody has started.
Step 4 is a change to a cloudflared config outside this repository.

No browser smoke test was attempted, because attempting one against a static
file server would produce a 404 and prove nothing about auth.

## What was not done, and why

```text
verified binding smoke (128G)   no authenticated identity exists, and no
                                authorization was given. Creating a binding
                                without one would be a fabricated membership
provider metadata / JWKS        no issuer is configured; there is no provider
  fetch (128E)                  to contact and nothing to validate against
token exchange                  requires a real callback code
```

Rows written to any customer table: 0. Sessions created: 0. Users created: 0.
Provider calls: 0. Network calls: 0.

## The sentence to refuse

> Customer authentication is ready to switch on.

It is not. The schema is ready — that is what moved this gate, and it is real.
The provider does not exist yet, the signing key does not exist yet, and the
process that would serve the callback is not running. Those are three different
kinds of absent, and none of them is a flag.
