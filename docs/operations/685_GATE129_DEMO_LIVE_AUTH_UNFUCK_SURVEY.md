# 685 — Gate 129: demo live + auth runtime survey

Measured before anything was implemented.

## The short answer

Most of what this gate needs already existed and was not switched on.

```text
API app with auth routes      built, wired into main.py, no process running
backend systemd unit          written as a template, never installed
/api/auth/* locally           404 before this gate, correct responses after
/api/auth/* publicly          no /api ingress rule at survey time; after the
                              rule was added, /api/auth/callback returns the
                              API's 200 publicly and every other path is
                              Access-gated (see 688 for the measurement and for
                              a wrong reading corrected inside this gate)
demo page                     3982 lines, 291 test ids, live at the dev URL
```

Nothing in the API needed writing. It needed starting.

## What Mayhem can show today

```text
demo URL     https://nf-dev.mayhem-nc.dev/?view=sc_customer_demo
served by    cloudflared -> 127.0.0.1:5175
5175 is      vite preview of frontend/dist (static, stamped build)
```

The page is real and already covers eligibility, pursuit, readiness and audit
surfaces. What it does not have is a single operating shell that tells the
product story end to end, or visible truth labels saying which parts are not
live. That is 129B.

## The API

```text
app                nativeforge.main:app
auth router        api/auth.py, prefix /api/auth, included at main.py:128
routes             GET /login, GET /callback, POST /logout,
                   GET /session, GET /current-user
unit               ~/.config/systemd/user/nativeforge-backend.service
bind               127.0.0.1:8000, loopback only, asserted by a test
health             /backend/health  (deliberately not /health - the vite
                   preview serves a static /health that answers ok whether or
                   not the API runs, and one question must not have two answers)
```

The unit header says installing it is a host decision and that nothing in the
repository installs it. This gate **starts** it; it does not `enable` it, so it
does not survive a reboot without a deliberate second decision.

### Measured responses, once running

```text
GET /backend/health          200  status ok, git_sha 334169a, source_dirty false
GET /api/auth/current-user   401  unauthenticated
GET /api/auth/callback       200  callback_validation_not_passed
GET /api/auth/session        200  authenticated false, no_session_cookie_was_sent
GET /api/auth/login          200  auth_not_configured
```

Every one of those is the controlled refusal Gate 116 designed. `/callback`
returning 200-with-a-refusal rather than 404 is the point: the route exists and
names why it will not mint a session.

No new `nativeforge-api.service` was created. A second unit for the same process
would be two names for one capability, which is the shape Gates 114 and 127 each
spent effort collapsing.

## The tunnel

```yaml
ingress:
  - hostname: nf-dev.mayhem-nc.dev
    service: http://127.0.0.1:5175
  - service: http_status:404
```

One hostname, one backend, no path rules. So `/api/auth/callback` from the
public internet reaches the static file server and 404s.

Routing `/api/*` to the API needs a path-matched rule ahead of the catch-all.
The file lives at `~/.cloudflared/nativeforge-mayhem.yml`, outside the
repository.

## The configuration layer

```text
Settings          src/nativeforge/lib/settings.py, pydantic-settings
env_file          (".env",)
auth keys declared as Settings fields   NONE
auth preflight reads from               os.environ
```

Gate 128 found this: `.env` reaches the `Settings` object and never reaches
`os.environ`, so auth keys written into `.env` are invisible to the preflight.

One nuance Gate 128 did not record. The backend unit carries:

```text
EnvironmentFile=-/home/josefgray/projects/nativeforge/.env
```

systemd parses that file and puts the values into the **process** environment,
so under the service `.env` does reach `os.environ`. Ad-hoc `python -c`,
`pytest` and a hand-run `uvicorn` do not. Two mechanisms, opposite answers,
depending on how the process was started — which is worse than one mechanism
that plainly does not work, because it works often enough to be trusted.

129C makes the Settings path authoritative so both routes agree.

## Callback and origin values

```text
public origin          https://nf-dev.mayhem-nc.dev
callback URL           https://nf-dev.mayhem-nc.dev/api/auth/callback
allowed origin         https://nf-dev.mayhem-nc.dev
allowed redirect URI   https://nf-dev.mayhem-nc.dev/api/auth/callback
logout URL             not applicable for Google - see below
```

`CALLBACK_ROUTE_PATH` is `/api/auth/callback`, defined once in
`customer_auth_environment_preflight_service` and imported by everything that
needs it since Gate 128C.

Google's OIDC discovery document publishes no `end_session_endpoint`, so there
is no RP-initiated logout to register a post-logout redirect against. Logout is
local session clearing through `POST /api/auth/logout`. `OIDC_LOGOUT_URL` stays
unset rather than being given a value no provider will honour.

## Environment key names

```text
OIDC_ISSUER               https://accounts.google.com   for Google
OIDC_CLIENT_ID            from the Google Cloud console
OIDC_CLIENT_SECRET        secret
OIDC_AUDIENCE             for Google this is the client id
OIDC_CALLBACK_URL         optional - derived from NF_PUBLIC_ORIGIN if unset
NF_PUBLIC_ORIGIN          https://nf-dev.mayhem-nc.dev
NF_SESSION_SIGNING_KEY    secret
```

## Blockers, split by who can clear them

Code or runtime — this gate:

```text
no API process running              start the existing unit
auth keys not Settings-backed       declare them, secret-safe
no operating shell in the demo      build one
no truth labels in the demo         add them
/api/* not routed publicly          tunnel path rule
no ready-to-paste OAuth setup       write it
```

Operator or provider — not this gate, and no code can move them:

```text
OIDC_ISSUER / CLIENT_ID / SECRET / AUDIENCE     Google Cloud console
NF_SESSION_SIGNING_KEY                          generated, stored out of repo
NF_CUSTOMER_AUTH_ACTIVATION_APPROVAL            Mayhem's decision alone
dev header replacement across 14 route modules  a code change, its own gate
```

## What this gate will not claim

Auth is not live and login is not live at the end of this gate, because no
provider is configured and no browser has completed a callback. Starting a
process that returns honest refusals is not authentication. The gate makes the
refusals reachable, which is what Gate 130 needs in order to stop being
blocked.
