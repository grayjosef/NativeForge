# Gate 130 — what is blocking a real login

## Cleared

```text
demo stack restart policy   on-failure -> always on all three units
demo stack verifier         checks what a browser gets, refuses 1033
unit under version control  the tunnel unit actually serving the demo
provider configuration      7 of 7 keys present
public OAuth path           proven end to end in a browser
test suite hermeticity      the suite no longer reads the machine's .env
```

## The public path, proven

A real Google authorization request reached consent and redirected back:

```text
Google accepted the client id           yes
Google accepted the redirect URI        yes, no mismatch
S256 challenge accepted                 yes
consent rendered as mayhem-nc.dev       yes
redirect landed on the public callback  yes
NativeForge API answered                yes
```

Every hop works: Google, the hostname, the Access bypass, the `/api/*` tunnel
rule, the backend.

## Where it stops

```text
state_store_scope        contract_only
redirect_state_durable   False
stored_state_found       False
```

`/login` generates a real state and PKCE pair and stores neither. Table
`nf_auth_redirect_states` has existed since migration 0030 and the repository
can address it; the route writes nothing to it, by a Gate 119 decision made when
there was nowhere to send the browser.

Three boundaries remain, all deliberate and all in `api/auth.py`:

```text
1  state is not persisted        so no callback can validate one
2  the route refuses to redirect  authorization_redirect_issued is a constant
3  no token exchange or session minting on callback
```

## Gate 131

Cross those three, in that order. Each is security behaviour rather than
configuration: replay windows, state expiry, single-use consumption, open
redirect surface, and cookie policy on the minted session.

Then an identity exists and Gate 132 is org binding — a verified claim resolving
to an `organization_id` and a membership record.

## Not blocking, but worth naming

```text
WSL idle shutdown    the demo's actual cause. No repository change fixes it;
                     hold a process open before a demo (doc 692).
~15s recovery        even with Restart=always, re-registering four edge
                     connections takes time. The verifier detects it.
single connector     one host, one tunnel, no failover.
```
