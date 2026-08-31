# Operator actions remaining — customer auth activation

Gate 128 moved everything that could be moved from inside the repository. What
is left needs a provider account, a secret manager, and a running process.

No value in this file is a secret, and no command below prints one.

---

## 1. Identity provider console

Create (or open) the application, then record these. Four are configuration and
one is a secret.

```text
issuer URL              https://<tenant>.<provider>.com/
client id               <application client id>
client secret           <application client secret>   -- secret
audience                <api identifier>
```

Register **this** callback, exactly:

```text
https://<your-public-origin>/api/auth/callback
```

Not `/auth/callback`. That path was a frozen literal in the repository until
this gate, it never matched any route, and the API has always served
`/api/auth/callback`. A provider registration that keeps the old path will fail
the exchange with a redirect-uri mismatch.

Also register, in the same console:

```text
allowed web origin      https://<your-public-origin>
allowed logout URL      https://<your-public-origin>/          (or a real page)
```

---

## 2. Environment values

### Read this first: `.env` will not work for these keys

Putting the auth keys in `.env` does nothing, and it fails silently. Measured:

```text
os.environ has DATABASE_URL          False
settings.database_url is set         True
Settings fields declaring an auth key NONE
preflight reads the auth keys from   os.environ
```

`.env` is read by pydantic-settings, which populates the `Settings` object and
**does not** put anything into `os.environ`. That works for `DATABASE_URL`
because `Settings` declares a field for it. No `Settings` field declares
`OIDC_ISSUER`, `OIDC_CLIENT_ID`, `OIDC_CLIENT_SECRET`, `OIDC_AUDIENCE`,
`NF_SESSION_SIGNING_KEY` or `NF_PUBLIC_ORIGIN`, and the auth preflight reads all
of them straight from `os.environ`.

So an operator who follows the Gate 121 runbook, writes the values into `.env`,
and re-runs the preflight sees every key still reported missing, with nothing
explaining why.

**These must be real environment variables in the API process's environment.**

### The mechanism that does work

Put them in a file the process loads into its environment — not `.env`:

```bash
# ~/nativeforge-auth.env  (outside the repo, chmod 600, never committed)
OIDC_ISSUER=
OIDC_CLIENT_ID=
OIDC_CLIENT_SECRET=
OIDC_AUDIENCE=
NF_PUBLIC_ORIGIN=
NF_SESSION_SIGNING_KEY=
```

```bash
chmod 600 ~/nativeforge-auth.env
```

Edit it in an editor rather than appending from the shell — an append puts the
secret in your shell history. The repository's own runbook refuses commands that
echo secret values for the same reason.

Then export it into the process that runs the API:

```bash
set -a && . ~/nativeforge-auth.env && set +a && uvicorn nativeforge.main:app --host 127.0.0.1 --port 8000
```

For a systemd unit, use `EnvironmentFile=%h/nativeforge-auth.env` instead —
that is the durable form, and it keeps the values out of any shell history.

`NF_PUBLIC_ORIGIN` is the origin only — scheme and host, no trailing slash, no
path. The callback URL is derived from it as
`NF_PUBLIC_ORIGIN + /api/auth/callback`, so setting the origin correctly means
the callback cannot drift from the route. Set `OIDC_CALLBACK_URL` only if you
need a callback that is *not* on the public origin.

Generate the signing key straight into the auth env file, without ever printing
it or putting it in shell history:

```bash
python -c "import secrets,pathlib;p=pathlib.Path.home()/'nativeforge-auth.env';p.open('a').write('NF_SESSION_SIGNING_KEY='+secrets.token_urlsafe(48)+'\n')"
```

It appends one line. Open the file afterwards to confirm the key is there and
appears once — but read it in an editor, not with `cat` in a shared terminal.

### Verify presence without revealing values

Run this **in the same shell that exported the file**, or it will report False
for everything and tell you nothing:

```bash
set -a && . ~/nativeforge-auth.env && set +a && python -c "import os;[print(f'{k:38s}{bool(os.environ.get(k))}') for k in ('OIDC_ISSUER','OIDC_CLIENT_ID','OIDC_CLIENT_SECRET','OIDC_AUDIENCE','NF_PUBLIC_ORIGIN','NF_SESSION_SIGNING_KEY')]"
```

Booleans only. Do not use `env`, `printenv`, `set -x`, or `cat` the file to
check this — all four print values.

---

## 3. Run an API process

This is the step with no configuration at all behind it, and it is currently the
hard blocker on any browser test.

Right now:

```text
nativeforge-demo-preview.service    vite preview of frontend/dist, 127.0.0.1:5175
nativeforge-mayhem-tunnel.service   cloudflared -> 127.0.0.1:5175
```

Nothing is bound to 8000. The public origin serves static files, so
`/api/auth/login` and `/api/auth/callback` return 404. A login attempt today
reaches a file server.

Start the API **with the auth environment loaded** — starting it without the
env file is the failure mode section 2 describes, and it looks identical to a
provider misconfiguration:

```bash
set -a && . ~/nativeforge-auth.env && set +a && uvicorn nativeforge.main:app --host 127.0.0.1 --port 8000
```

Confirm it is up:

```bash
curl -fsS http://127.0.0.1:8000/backend/health
```

---

## 4. Point the tunnel at something that can answer

`~/.cloudflared/nativeforge-mayhem.yml` currently routes the hostname to
`http://127.0.0.1:5175`. The callback route lives on the API, so the ingress
needs a rule sending `/api/*` to `http://127.0.0.1:8000` ahead of the catch-all
to the preview.

This file is outside the repository and is not managed by this campaign. Edit
it, then restart:

```bash
systemctl --user restart nativeforge-mayhem-tunnel.service
```

Verify from outside:

```bash
curl -fsS -o /dev/null -w '%{http_code}\n' https://<your-public-origin>/api/auth/login
```

A 4xx that is not 404 means the route is reachable and rejecting an
unconfigured request. A 404 means the ingress rule is not in effect.

---

## 5. Owner authorization

`NF_CUSTOMER_AUTH_ACTIVATION_APPROVAL` is absent, and
`owner_approval_present` is false. Nothing in this gate set it, and nothing
should set it on Mayhem's behalf.

Verified binding (128G) was not performed and must not be, until there is a real
authenticated identity **and** explicit authorization. Creating one before then
is a fabricated membership, which is the thing the whole boundary exists to
prevent.

---

## 6. The dev header

```text
NF_DEV_ORG_HEADERS   present in .env
route modules using it   14
```

It must be replaced across those modules and disabled before any production
auth. This is a code change, not configuration, and it is not part of this
gate.

---

## Order

```text
1  provider console          nothing works without the issuer
2  auth env file             NOT .env - see section 2, it fails silently
3  API process               started with that env loaded
4  tunnel ingress            a callback needs to be reachable
5  re-run the preflight      confirm blockers cleared, before touching a browser
6  owner authorization       last, and only Mayhem's to give
```

Re-run the preflight after step 4, in a shell with the env loaded:

```bash
set -a && . ~/nativeforge-auth.env && set +a && python -c "from nativeforge.services.customer_auth_environment_preflight_service import build_environment_preflight as b;p=b();[print(f'  {r}') for r in p['blocked_reasons']] or print('  no blockers')"
```

---

## Already done, for reference

```text
runtime database        0024 half-applied  ->  0035, 7 auth/award tables present
                        backup at ~/nativeforge-backups/ (outside the repo)
callback URL            frozen wrong literal -> derived from environment
database blocker        unclearable constant -> reads the actual database
```

The last one is why the database blocker stayed up through the migration: the
preflight asked a decision service whose `database_revision` argument nobody
ever supplied, so it answered "not applied" for every database that has ever
existed. If you see a blocker that will not clear after you have plainly cleared
it, that is the shape to look for.
