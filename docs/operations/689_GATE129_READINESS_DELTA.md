# 689 — Gate 129: readiness delta

## Moved

```text
API process                          none            nativeforge-backend.service
/api/auth/* locally                  404             correct refusals
/api/* publicly routed               no rule         path rule ahead of catch-all
auth keys as Settings fields         0 of 7          7 of 7
auth secrets typed                   plain env read  SecretStr
auth env resolution paths            2 disagreeing   1 order
demo operating shell                 none            10 sections
demo truth labels                    none            6, all computed
demo shell service                   none            + invariants
demo-live artifacts                  none            6 files
OAuth setup handoff                  none            ready-to-paste prompt
```

## Not moved — and this is the honest part

```text
customer_auth_live                   False
login_live                           False
verified_operational_binding         False
customer_persistence_live            False
provider_ready                       False
object store configured              False
live source monitoring active        False
email delivery active                False
operational capability lanes         0 of 9
rows written to any customer table   0
users created                        0
sessions created                     0
activation blockers                   7
```

Gate 128 dropped blockers 8 → 7. Gate 129 dropped none, and that is the correct
outcome: every remaining blocker is a provider console, a secret manager, a
Cloudflare dashboard, or Mayhem's decision.

## What this gate actually bought

Not a cleared blocker — a cleared *class* of blocker. Before this gate, Gate 130
would have had to discover, in order:

```text
1  no process serves the callback     would have looked like a code bug
2  the tunnel has no /api rule        would have looked like a DNS problem
3  .env does not reach the preflight  would have looked like a typo
4  systemd .env does reach it         would have made 3 look intermittent
```

Every one of those presents as something else. Item 4 is the nastiest: it makes
item 3 intermittent, so the same configuration appears to work or not depending
on how the process was started.

All four are now measured, named and fixed.

## The public edge, and a correction made inside this gate

An earlier measurement here reported Cloudflare Access blocking
`/api/auth/callback`, and concluded that clearing it was Gate 130's first action.
**That was wrong.** Re-measured with the backend running and the ingress rule
live:

```text
/                        302 -> cloudflareaccess.com
/backend/health          302 -> cloudflareaccess.com
/api/does-not-exist      302 -> cloudflareaccess.com
/api/auth/login          302 -> cloudflareaccess.com
/api/auth/session        302 -> cloudflareaccess.com
/api/auth/current-user   302 -> cloudflareaccess.com
/api/auth/callback       200    API JSON
```

Exactly one path is exempt, and it is the callback. An Access bypass scoped to
`/api/auth/callback` already exists; this gate did not add it. It is precisely
what an OAuth redirect needs, since a browser arriving from a provider carries
no Access session for this host.

The bad reading came from measuring seconds after a tunnel restart while the
backend was briefly down — `/api/*` had not yet resolved to the API, so the
request fell through to the Access-protected static origin.

Recorded because the wrong version was the more believable one. "The edge blocks
the callback" is a tidy explanation for a failed OAuth flow, and it would have
sent Gate 130 to a dashboard to fix something that was never broken.

## Sequence for Gate 130

```text
1  Google OAuth client                  provider console
2  seven env values                     .env or EnvironmentFile
3  restart nativeforge-backend.service
4  browser completes a real callback
5  session signed, org resolved, membership verified
6  owner approval                       Mayhem, and only Mayhem
```

Steps 1 and 2 are operator work with exact values already written down in doc
690. Steps 4 and 5 are where `customer_auth_live` gets earned rather than
claimed.

No Cloudflare step. The path is already open.

## What the demo says today

Six truth labels, all active, all computed:

```text
CONTROLLED DEMO DATA
AUTH NOT LIVE
LIVE SOURCE MONITORING NOT ACTIVE
EMAIL DELIVERY NOT ACTIVE
OBJECT STORE NOT CONFIGURED
PROVIDER CONFIG REQUIRED FOR LOGIN
```

Ten sections, zero operational, zero rows. The compliance spine is built and
provably empty, and the page says so in the same words this document does.

## The sentence to refuse

> Gate 129 made auth work.

It did not. It made auth *reachable* and made every remaining obstacle visible
and named. A process that returns honest refusals is not authentication; it is
the thing that had to exist before authentication could be attempted.
