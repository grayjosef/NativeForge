# 688 — Gate 129: API runtime and tunnel

## The API needed starting, not writing

Everything was already built. `api/auth.py` defines five routes under
`/api/auth`, `main.py:128` includes the router, and a complete systemd unit had
been sitting at `~/.config/systemd/user/nativeforge-backend.service` since Gate
101 — written as a template, deliberately never installed, with a header saying
installing it is a host decision.

No `nativeforge-api.service` was created. A second unit for the same process
would be two names for one capability, which is the shape Gates 114 and 127 each
spent effort collapsing.

```text
unit     nativeforge-backend.service
bind     127.0.0.1:8000, loopback only, asserted by a test parsing the unit
env      EnvironmentFile=-<repo>/.env   (optional, gitignored)
started  yes
enabled  no
```

**Started, not enabled.** The unit reserves installation as a host decision, so
it does not survive a reboot without a deliberate second step:

```bash
systemctl --user enable nativeforge-backend.service
```

## Measured responses

```text
GET /backend/health          200  status ok, git_sha, source_dirty false
GET /api/auth/current-user   401  unauthenticated
GET /api/auth/callback       200  callback_validation_not_passed
GET /api/auth/session        200  authenticated false
GET /api/auth/login          200  auth_not_configured
```

`/callback` answering 200-with-a-refusal rather than 404 is the point: the route
exists and names why it will not mint a session. A 404 would mean an OAuth
redirect lands nowhere.

`/backend/health` is deliberately not `/health` — the Vite preview on :5175
serves a static `/health` that answers `ok` whether or not the API runs, and one
question must not have two answers.

## The tunnel

Before:

```yaml
ingress:
  - hostname: nf-dev.mayhem-nc.dev
    service: http://127.0.0.1:5175
  - service: http_status:404
```

After:

```yaml
ingress:
  - hostname: nf-dev.mayhem-nc.dev
    path: ^/api/.*
    service: http://127.0.0.1:8000
  - hostname: nf-dev.mayhem-nc.dev
    service: http://127.0.0.1:5175
  - service: http_status:404
```

Order matters: the path rule must precede the hostname catch-all, or the static
server answers `/api/auth/callback` with a 404.

```text
validated    cloudflared ingress validate -> OK
backup       ~/.cloudflared/nativeforge-mayhem.yml.gate129.bak
verifier     verify_nativeforge_demo_deployment.sh --strict-public -> RESULT=PASS
```

The file is outside the repository, so the change is not in this commit. The
backup makes it reversible.

## Cloudflare Access, and a correction

Cloudflare Access protects the hostname. Measured, with the backend running and
the `/api/*` ingress rule in place:

```text
/                        302 -> josefgray.cloudflareaccess.com
/backend/health          302 -> josefgray.cloudflareaccess.com
/api/does-not-exist      302 -> josefgray.cloudflareaccess.com
/api/auth/login          302 -> josefgray.cloudflareaccess.com
/api/auth/session        302 -> josefgray.cloudflareaccess.com
/api/auth/current-user   302 -> josefgray.cloudflareaccess.com
/api/auth/callback       200    API JSON, callback_validation_not_passed
```

**Exactly one path is exempt, and it is the callback.** That surgical an
exception is an Access bypass policy already scoped to `/api/auth/callback`.
This gate did not add it, and it is exactly what a provider redirect needs: a
browser arriving from Google carries no Access session for this host, so without
the bypass the redirect would land on a login page instead of the API.

An earlier measurement in this gate reported the callback as also 302, and that
was wrong. It was taken seconds after a tunnel restart with the backend briefly
down, so `/api/*` had not yet resolved to the API and the request fell through
to the Access-protected static origin. The reading above is stable across
repeats with cache-busting query strings.

The mistake is worth recording because the wrong version was the more
believable one — "the edge blocks the callback" explains a failed OAuth flow
neatly, and would have sent Gate 130 to a Cloudflare dashboard to fix something
that was never broken.

## Reachability, stated plainly

```text
/api/auth/callback reachable locally                    yes, 200
/api/auth/callback reachable publicly, unauthenticated  yes, 200
every other path publicly, unauthenticated              Access 302
OAuth callback can reach the API today                  yes
OAuth flow can complete today                           no - no provider configured
```

The last two lines are different questions. The path is open; there is simply no
identity provider on the other end of it yet.

Keep the bypass as narrow as it is. Widening it to `/api/*` would expose every
API route on the dev domain to the open internet.
