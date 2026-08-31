# 690 — Gate 129: Browser/Cloud Google OAuth setup prompt

Ready to paste. No secret value appears in this file and none should be added
to it.

---

## Read this first: the callback path is already open

Cloudflare Access protects `nf-dev.mayhem-nc.dev`, with exactly one exemption —
and it is the one OAuth needs. Measured:

```text
/                        302 -> cloudflareaccess.com
/backend/health          302 -> cloudflareaccess.com
/api/auth/login          302 -> cloudflareaccess.com
/api/auth/session        302 -> cloudflareaccess.com
/api/auth/current-user   302 -> cloudflareaccess.com
/api/auth/callback       200    API JSON
```

An Access bypass scoped to `/api/auth/callback` already exists. **No Cloudflare
change is needed.** A browser arriving from Google carries no Access session for
this host, and that bypass is what lets the redirect reach the API rather than a
login page.

Leave the bypass as narrow as it is. Widening it to `/api/*` would expose every
API route on the dev domain to the open internet.

---

## The prompt

> Set up Google OAuth (OIDC) for a FastAPI application on my Cloudflare-tunnelled
> dev host. Do not paste any secret value into chat, a file, or a repository —
> I will place secrets myself.
>
> **Google Cloud console steps**
>
> 1. Open the Google Cloud console, select or create a project for this app.
> 2. Configure the OAuth consent screen. External, Testing is fine for a dev
>    domain. Add my own Google account as a test user.
> 3. Create credentials → OAuth client ID → **Web application**.
> 4. Name it `NativeForge dev`.
> 5. Under **Authorised JavaScript origins**, add exactly:
>
>    ```
>    https://nf-dev.mayhem-nc.dev
>    ```
>
> 6. Under **Authorised redirect URIs**, add exactly:
>
>    ```
>    https://nf-dev.mayhem-nc.dev/api/auth/callback
>    ```
>
>    That path is `/api/auth/callback`, not `/auth/callback`. The API serves the
>    first and nothing serves the second.
>
> 7. Create it. Report back the **client ID**, and tell me the client secret is
>    ready without printing it.
>
> **Cloudflare — check only, do not change**
>
> 8. In Zero Trust → Access → Applications, on the application covering
>    `nf-dev.mayhem-nc.dev`, confirm the existing **Bypass** policy is scoped to
>    the path `/api/auth/callback` and no wider. Do not add, widen or remove any
>    policy. This path already returns the API's JSON publicly, which is what the
>    OAuth redirect needs.
>
> **Report back**
>
> - the client ID
> - confirmation the redirect URI and origin were saved exactly as written
> - confirmation the existing Access bypass is still limited to
>   `/api/auth/callback`
> - the issuer value Google publishes (expected `https://accounts.google.com`)
>
> Do not attempt to run the login flow yourself, and do not create test users
> beyond my own account.

---

## Values, for reference

```text
provider               Google OAuth 2.0 / OIDC
issuer                 https://accounts.google.com
public origin          https://nf-dev.mayhem-nc.dev
callback URL           https://nf-dev.mayhem-nc.dev/api/auth/callback
allowed origin         https://nf-dev.mayhem-nc.dev
allowed redirect URI   https://nf-dev.mayhem-nc.dev/api/auth/callback
logout URL             not applicable
```

Google's discovery document publishes no `end_session_endpoint`, so there is no
RP-initiated logout to register a post-logout redirect against. Logout is local
session clearing via `POST /api/auth/logout`. Leave `OIDC_LOGOUT_URL` unset
rather than giving it a value no provider will honour.

For Google, the audience is the client ID — the ID token's `aud` claim is the
OAuth client that requested it. Set `OIDC_AUDIENCE` to the same value as
`OIDC_CLIENT_ID`.

---

## Where the env values go

Seven keys. Two are secrets.

```text
OIDC_ISSUER              https://accounts.google.com
OIDC_CLIENT_ID           from the console
OIDC_CLIENT_SECRET       from the console          secret
OIDC_AUDIENCE            same as OIDC_CLIENT_ID
NF_PUBLIC_ORIGIN         https://nf-dev.mayhem-nc.dev
OIDC_CALLBACK_URL        optional - derived from NF_PUBLIC_ORIGIN if unset
NF_SESSION_SIGNING_KEY   generated locally          secret
```

Since Gate 129C these are `Settings` fields, so `.env` in the repository root
works and so does an exported environment variable. `os.environ` wins where both
are set. `.env` is gitignored (`.gitignore:19`) and the backend unit already
loads it:

```text
EnvironmentFile=-/home/josefgray/projects/nativeforge/.env
```

Edit `.env` in an editor rather than appending from the shell — an append puts
the secret in shell history.

Generate the signing key without printing it:

```bash
python -c "import secrets,pathlib;p=pathlib.Path('.env');p.open('a').write('NF_SESSION_SIGNING_KEY='+secrets.token_urlsafe(48)+'\n')"
```

---

## Restart, and verify without printing secrets

```bash
systemctl --user restart nativeforge-backend.service
```

```bash
systemctl --user restart nativeforge-demo-preview.service
```

Presence check — booleans only, never values:

```bash
cd /home/josefgray/projects/nativeforge && .venv/bin/python -c "from nativeforge.lib.settings import auth_environment_presence as p;[print(f'{k:26s}{v}') for k,v in p().items()]"
```

Remaining blockers, by name:

```bash
cd /home/josefgray/projects/nativeforge && .venv/bin/python -c "from nativeforge.services.customer_auth_environment_preflight_service import build_environment_preflight as b;[print(' ',r) for r in b()['blocked_reasons']] or print('  none')"
```

Do not use `env`, `printenv`, `set -x`, or `cat .env` to check any of this —
all four print values.

Local API smoke:

```bash
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8000/backend/health
```

```bash
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8000/api/auth/current-user
```

Expect `200` then `401`. A `401` on `current-user` is correct — it proves the
route refuses an unauthenticated caller rather than inventing a session.

---

## What still will not be true after this

Configuring the provider and setting the seven values makes a browser login
*possible*. It does not make `customer_auth_live` true. That flips only when a
real callback completes, a session is signed, an organization resolves and a
membership verifies — and separately, `NF_CUSTOMER_AUTH_ACTIVATION_APPROVAL` is
Mayhem's decision and nobody else's.

Gate 130 is where a browser completes the flow and the claim gets earned.
