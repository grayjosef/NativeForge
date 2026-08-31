# Customer auth activation — execution summary

Gate 128 attempted the Gate 121 runbook against the live runtime. This records
what was executed, what was refused, and what is still absent.

## Result

```text
customer_auth_live          False
login_live                  False
activation_allowed          False
provider_contacted          False
browser_callback_smoke      not attempted
verified_binding created    no
```

One blocker cleared. Seven remain, and none of the seven is a code change.

Two defects were found and fixed, and they are the same defect pointed in
opposite directions:

```text
the callback URL    a value nobody configured, reported as configured
migration_applied   a database nobody read, reported as unapplied
```

Both were constants wearing the shape of a measurement.

## What was executed

### The runtime database — applied

The database was in a state no revision described: `alembic_version` read
`0024` while two of migration 0025's three columns already existed. A plain
`alembic upgrade head` failed at 0025 with `duplicate column name: display_name`.

Sequence, with every destructive step rehearsed on a copy first:

```text
1  read the runtime DB read-only, recorded revision and shape
2  ran alembic upgrade against a COPY          -> failed, as above
3  ran alembic upgrade against a FRESH db      -> succeeded to 0035
4  repaired a COPY, upgraded it                -> succeeded to 0035
5  re-read the runtime DB                      -> confirmed unchanged
6  backed up, then applied the same repair to the runtime DB
```

Step 3 mattered. The obvious reading of step 2 is that migration 0025 is
unrunnable on SQLite — it adds a `NOT NULL` column with a `now()` default,
which SQLite rejects through `ALTER TABLE`. A fresh database migrates cleanly,
because there the column arrives with the table. The migration is fine; a
previous run was interrupted. The wrong diagnosis would have led to editing a
working migration.

Outcome:

```text
revision            0024  ->  0035
tables              26    ->  35
organization rows   2     ->  2      (preserved)
backup              ~/nativeforge-backups/nativeforge.local.db.gate128.bak
```

All seven required tables verified present.

### The blocker that did not clear when the database moved

Applying the migrations did not clear `database_not_at_revision_0030`. The
database read `0035` and the preflight still called it unapplied.

`_detect_database_revision()` asked Gate 113's decision service for
`migration_applied`. That function takes `database_revision: str | None = None`,
and no caller anywhere ever supplied it — so it answered `False` for every
database that has ever existed. The blocker was unclearable by construction.

Gate 113 split `migration_defined` from `migration_applied` precisely because a
single constant "would have become a lie the moment revision 0029 landed". The
split was right; the second half stayed a constant one indirection down.

The repair supplies the missing fact rather than forking a second detector. The
decision service keeps the rule and stays pure; the preflight, which already
probes the environment, reads the revision and passes it in. The read is
read-only and returns `""` on any failure — absent reports as absent, never as
ready. Both branches are asserted.

### The callback URL — corrected, and the correction is not the path

Gate 121 reported a configured callback of `http://localhost:5173/auth/callback`
against a route of `/api/auth/callback`, and called it a path mismatch.

The value was a frozen literal in `oidc_config_schema_service`. Not read from
the environment, not derived from the route, not configurable by anyone. The
port had never been right either — vite's default is 5173 and the preview runs
on 5175 — and no frontend route declares `/auth/callback` at all.

The defect is the third consequence, not the first two:

```text
redirect_uri_configured   reported TRUE, for a URL pointing at nothing
```

Fixing only the path would have produced a differently wrong literal that still
claimed to be configured. The derivation now:

```text
OIDC_CALLBACK_URL set        use it
else NF_PUBLIC_ORIGIN set    origin + CALLBACK_ROUTE_PATH
else                         None
```

`CALLBACK_ROUTE_PATH` is imported from the preflight service rather than
restated, so the derived callback cannot drift from the route the API serves.
With nothing configured, the callback is `None` and `allowed_redirect_uris` is
empty — an unset redirect URI reports as unset.

A new invariant fires when a callback is present whose path is not the route's.
It does not fire on absence. Six cases were exercised, including the old
literal, a correct explicit URL, an origin with a trailing slash, and
`force_unconfigured`.

## What was refused, and why

```text
provider metadata / JWKS fetch   no issuer configured; nothing to contact
token exchange                   requires a real callback code
browser callback smoke           no API process serves the callback route
verified binding                 no authenticated identity, no authorization
```

The browser smoke refusal is not caution. `ss -ltnp` shows two listeners: vite
on 5175 and cloudflared's metrics port. Nothing is bound to 8000. The tunnel
routes the public hostname to the static preview of `frontend/dist`, so
`/api/auth/login` and `/api/auth/callback` return 404 from outside. A login
attempt today reaches a file server. Driving a browser at it would have produced
a 404 and proved nothing about authentication.

## What is still absent

```text
OIDC_ISSUER                             missing
OIDC_CLIENT_ID                          missing
OIDC_CLIENT_SECRET                      missing
OIDC_AUDIENCE                           missing
NF_PUBLIC_ORIGIN                        missing
NF_SESSION_SIGNING_KEY                  missing
NF_CUSTOMER_AUTH_ACTIVATION_APPROVAL    missing
```

`.env` holds `DATABASE_URL` and `NF_DEV_ORG_HEADERS`. Neither is an auth key.
Nothing about the identity provider has ever been configured.

### `.env` is not where they go, and that fails silently

A third defect, found while writing the operator instructions — because the
first version of those instructions would have done nothing.

```text
os.environ has DATABASE_URL             False
settings.database_url is set            True
Settings fields declaring an auth key   NONE
preflight reads the auth keys from      os.environ
```

`.env` is read by pydantic-settings and never reaches `os.environ`.
`DATABASE_URL` works from `.env` only because `Settings` declares a field for
it. No `Settings` field declares any auth key, and the preflight reads all five
from `os.environ` — so writing them into `.env` leaves every key reported
missing with nothing explaining why.

They must be real environment variables in the API process's environment: an
`EnvironmentFile` on the systemd unit, or `set -a; . file; set +a` before
uvicorn. `operator_remaining_actions.md` gives the working form.

Documented rather than fixed: declaring the auth keys as `Settings` fields is
the better repair and the recommended next change, but it moves a client secret
into a settings object that gets repr'd and logged, which needs `SecretStr`
handling and its own gate.

Remaining activation blockers (7):

```text
provider_configuration_missing      provider console
secret_configuration_missing        secret manager
signing_key_not_fit_to_sign         secret manager
owner_authorization_absent          Mayhem
dev_header_still_in_place           14 route modules, a code change
role_mapping_not_validated          needs a provider to validate against
callback_url_does_not_match_a_route  no callback configured to match
```

`callback_url_does_not_match_route` changed character rather than clearing: with
nothing configured there is no callback to mismatch, and once `NF_PUBLIC_ORIGIN`
is set the derived value matches the route by construction.

## Counts

```text
rows written to customer tables     0
users created                       0
sessions created                    0
memberships created                 0
provider calls                      0
network calls                       0
secrets printed                     0
secrets committed                   0
```

## The sentence to refuse

> Customer authentication is ready to switch on.

The schema is ready, and that is what moved. The provider does not exist yet,
the signing key does not exist yet, and the process that would serve the
callback is not running. Three different kinds of absent, none of them a flag.

Operator steps are in `operator_remaining_actions.md`.
