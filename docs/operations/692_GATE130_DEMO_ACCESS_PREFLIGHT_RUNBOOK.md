# 692 — Gate 130: demo access and preflight runbook

Operational. Run these, do not read theory.

## The demo URL

```text
https://nf-dev.mayhem-nc.dev/?view=sc_customer_demo
```

It sits behind Cloudflare Access. You sign in; a stranger does not.

## 10-minute pre-demo checklist

**T-10. Hold WSL open.** This is the one that bit during the demo. Windows shuts
the WSL VM down when it is idle and every service goes with it. Open a terminal
and leave it alone:

```bash
wsl.exe -d Ubuntu -e bash -lc 'while true; do sleep 60; done'
```

**T-8. Run the verifier.** One command, one word of output:

```bash
cd /home/josefgray/projects/nativeforge && ./scripts/verify_nativeforge_demo_live_stack.sh
```

`RESULT=PASS` and you are done. `RESULT=FAIL` prints `failed_check=<name>` —
go to the table at the bottom.

**T-5. Open the demo yourself** in the browser you will present from, and sign
in through Access. Do it now, not in front of anyone. The Access session lasts
the meeting.

**T-2. Leave the tab open.** Do not restart anything after this point.

## If something is wrong

Restart the stack:

```bash
systemctl --user restart nativeforge-demo-preview.service nativeforge-backend.service nativeforge-mayhem-tunnel.service
```

Then wait 20 seconds and re-run the verifier. Re-registering four edge
connections is not instant.

**Do not restart during a demo.** A restart drops the tunnel for ~15 seconds,
which is the same failure you are trying to fix. If the page fails mid-demo,
wait 30 seconds and reload first — the stack recovers on its own.

## Access screen vs 1033 — how to tell them apart

This matters, because they look like "the demo is broken" and only one of them
is.

```text
Access screen   a Cloudflare login page, your email, "Sign in with Google"
                or a one-time PIN box. The URL becomes
                josefgray.cloudflareaccess.com.
                MEANING: everything works. Sign in.

Error 1033      a Cloudflare error page saying "Argo Tunnel error" with 1033
                in the corner. The URL stays nf-dev.mayhem-nc.dev.
                MEANING: no connector is reachable. The tunnel is down or
                still starting.
```

The short version: **if you can sign in, it is fine.** If you see a number, it
is not.

## Adding a demo viewer to Cloudflare Access

Do this the day before, not in the meeting.

```text
1  Cloudflare dashboard -> Zero Trust -> Access -> Applications
2  Open the application covering nf-dev.mayhem-nc.dev
3  Open its policy, add the viewer's email address to the Include rule
4  Save. The viewer gets a one-time PIN by email on first visit.
```

Add individual email addresses. Do not switch the policy to "Everyone", and do
not add an email-domain rule for a domain you do not control — either makes the
demo public.

## Preserving the /api/auth/callback bypass

There is a Bypass policy scoped to exactly `/api/auth/callback`. It exists so a
browser arriving from Google can reach the API — that browser carries no Access
session, so without the bypass OAuth cannot complete.

```text
Leave it alone.
Do not widen it to /api/* — that exposes every API route publicly.
Do not delete it — that breaks login.
```

Check it is still narrow:

```bash
curl -s -o /dev/null -w '%{http_code}\n' https://nf-dev.mayhem-nc.dev/api/auth/callback
```

```bash
curl -s -o /dev/null -w '%{http_code}\n' https://nf-dev.mayhem-nc.dev/api/auth/current-user
```

Expect `200` then `302`. If the second returns 200, the bypass is too wide.

## What not to expose

```text
127.0.0.1:8000     the backend. Loopback only. Reaches the public internet
                   solely through the /api/* tunnel rule.
127.0.0.1:5175     the preview. Loopback only.
.env               gitignored, holds the Google client secret and the session
                   signing key. Never open it on a shared screen.
the Cloudflare     never on screen.
  dashboard
```

Before sharing your screen, close the terminal tab where you edited `.env`.

## Verifier failures, and what each means

```text
service_active:*              that unit is down. Restart the stack.
local_frontend                preview not serving. Restart preview.
local_backend_health          API down. Restart backend.
local_callback_controlled     API up but the auth route is wrong. Not an
                              operational fix - stop and get it looked at.
public_demo_not_1033          no connector. Restart the tunnel, wait 20s.
public_demo_reachable         edge cannot reach the origin. Restart tunnel.
public_callback_reaches_api   Access is intercepting the callback, or the
                              tunnel /api rule is gone. Check the bypass is
                              still scoped to /api/auth/callback.
tunnel_edge_connections       zero registered connectors. This is 1033 about
                              to happen. Restart the tunnel.
```

## What to say if it breaks anyway

Do not debug in front of the audience. Say the dev tunnel dropped, that it is a
demo-host issue rather than the product, and move to the talk track. The
operating shell and its numbers are the same whether or not the page loads.
