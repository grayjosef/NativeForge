# 691 — Gate 130: demo reliability and OAuth survey

The demo showed Cloudflare Error 1033 while every service on the host reported
active. This is what actually happened and what was wrong.

## Why 1033 happened

Determinable, from the tunnel journal.

```text
14:05:08  ERR no more connections active and exiting
14:05:08  INF Tunnel server stopped
14:05:08  systemd[235]: Stopped nativeforge-mayhem-tunnel.service
14:05:23  systemd[248]: Started nativeforge-mayhem-tunnel.service
14:05:24  INF Registered tunnel connection connIndex=0
14:05:26  INF Registered tunnel connection connIndex=3
```

Note the systemd PID: `systemd[235]` → `systemd[248]`. **The WSL systemd user
manager restarted.** WSL shuts the VM down when it goes idle and brings it back
on next access, taking every user service with it.

1033 means Cloudflare holds the hostname but cannot reach a connector. For
roughly fifteen seconds — 14:05:08 to 14:05:24 — there was no connector. A page
load in that window gets 1033. The stack recovered on its own and has served
since.

So the demo failure was a **window**, not a broken configuration.

## What was actually wrong

Three things, and only the first was visible.

### 1. `Restart=on-failure` cannot restart a clean exit

All three units carried it. systemd treats exit code 0 as success, so
`on-failure` does nothing when a process decides to stop.

cloudflared does exactly that: `no more connections active and exiting`. A
connector that gives up on its edge connections and exits zero stays down under
`on-failure`, and a hostname with no connector is 1033.

That the tunnel came back at all was down to being `enabled` — the user manager
restarted it as part of `default.target`, not because the restart policy did
anything.

### 2. Nothing could tell the operator the stack was servable

`systemctl is-active` reports that a process is running. It says nothing about
whether the connector is registered with Cloudflare's edge, and 1033 is only
visible from outside. Every check available before a demo answered a question
adjacent to the one that mattered.

### 3. The unit serving the demo was not in the repository

```text
ops/systemd/nativeforge-cloudflared.service      config.yml, metrics :20241
~/.config/systemd/user/nativeforge-mayhem-tunnel.service
                                                 nativeforge-mayhem.yml, :20242
```

Different config, different metrics port, different name. The repository tracked
a unit that is not the one serving `nf-dev.mayhem-nc.dev`, so reviewing the
tracked file told you nothing about production behaviour.

## State before this gate

```text
preview   active   enabled   Restart=on-failure   NRestarts=0
backend   active   enabled   Restart=on-failure   NRestarts=0
tunnel    active   enabled   Restart=on-failure   NRestarts=0
linger    yes
```

Enablement and linger were already correct — both were fixed during Gate 129/130
after the backend died twice for this same reason. The restart policy was not.

## State after

```text
preview   active   enabled   Restart=always   StartLimitBurst=5/300s
backend   active   enabled   Restart=always   StartLimitBurst=5/300s
tunnel    active   enabled   Restart=always   StartLimitBurst=5/300s
linger    yes
tunnel edge connections: 4
```

`always` covers both a crash and a clean exit. The rate limiter stops a
genuinely broken unit rather than letting it thrash silently.

## Public state, measured

```text
/                        302 -> cloudflareaccess.com     correct, demo is gated
/?view=sc_customer_demo  302 -> cloudflareaccess.com     correct
/api/auth/login          302 -> cloudflareaccess.com     gated
/api/auth/callback       200    NativeForge API JSON     bypass, as required
```

No 1033. The callback bypass predates this gate and was not touched.

## Reliability gaps that remain

```text
WSL idle shutdown       the root cause. Nothing inside the guest prevents the
                        host from stopping the VM. `linger` keeps the user
                        manager alive within a running VM; it does not keep the
                        VM running. Mitigation is to hold a process open on the
                        Windows side before a demo.

~15s recovery window    even with Restart=always, a VM restart takes time to
                        re-register four edge connections. A demo that loads in
                        that window still sees 1033. The verifier now detects
                        it; nothing can make it instantaneous.

single connector host   one machine, one tunnel. No failover.
```

The first is the one that bit, and it is a Windows-side operational habit rather
than a repository change. Doc 692 covers it.

## OAuth state

```text
OIDC_ISSUER              present     https://accounts.google.com
OIDC_CLIENT_ID           present
OIDC_CLIENT_SECRET       present
OIDC_AUDIENCE            present
OIDC_CALLBACK_URL        present     .../api/auth/callback, no trailing slash
NF_PUBLIC_ORIGIN         present
NF_SESSION_SIGNING_KEY   present     source: environment
```

Seven of seven. The Google client was created in project `native-forge` during
the previous gate, with one test user.

```text
provider_configured           True
authorization_url_available   True    no blockers
session_signing_key_ready     True
authorization_redirect_issued False
state_stored                  False
customer_auth_live            False
login_live                    False
```

## What the browser smoke proved

A real Google authorization request was driven end to end, stopping at consent.

```text
client_id accepted                      yes
redirect_uri accepted                   yes - no redirect_uri_mismatch
code_challenge accepted (S256)          yes
consent screen renders as mayhem-nc.dev yes
test-user gating in force               yes
Google redirected to the public callback yes
callback answered with the API envelope  yes
```

The redirect landed on
`https://nf-dev.mayhem-nc.dev/api/auth/callback?error=access_denied&...` and
NativeForge answered. That is the entire public path — Google, the hostname, the
Access bypass, the `/api/*` tunnel rule, the backend — proven in one request.

Consent was cancelled rather than granted. Completing it would have put a live
authorization code in the session transcript to prove something already known:
the callback refuses, because state is not persisted.

## Where it stops, exactly

```text
state_store_scope         contract_only
redirect_state_durable    False
stored_state_found        False
state_validated           False
pkce_verified             False
session_created           False
org_binding_passed        False
```

`nf_auth_redirect_states` exists as of migration 0030 and the repository can
address it. `/login` writes nothing to it, by a Gate 119 decision that was
correct when there was nowhere to send the browser.

There is somewhere to send the browser now. That is Gate 131.
