# Gate 133F — the dev-header kill plan

## Where it stands

```text
routes total                     217
routes reading X-NF-Org-Id       0
modules reading it               0
converted in Gate 133F           isolation_routes (2 routes)
publicly routed of those         0
behind Cloudflare Access         True
```

## How they are reachable, which was not what the detector said

```text
cloudflared ingress   ['^/api/.*']  -> 127.0.0.1:8000
cloudflared catch-all (hostname)   -> 127.0.0.1:5175   the Vite preview
vite preview proxy    ['/docs', '/openapi.json', '/redoc', '/v1']  -> 127.0.0.1:8000
```

Every dev-header route is under `/v1`, so **none is reached by the ingress rule
`dev_org_header_containment_service` inspects.** They are reached by the preview
proxy, one hop further in, which that detector does not model. Its conclusion
(`backend_publicly_exposed: true`) is right today because of the `/api/*` rule —
which covers the five auth routes and no dev-header route. Delete that ingress
line and it would report the backend contained while all
0 stayed exposed.

Third instance of this shape in three gates: Gate 130's detector read the wrong
cloudflared file, Gate 131's migration reader hardcoded one filename for a table
defined by two, this one models one hop of two.

## The order, least risky first

| # | module | routes | risk | why |
|---|---|---:|---|---|


Within a risk band the smaller surface goes first. The order is derived from the
risk classification and the measured route counts, not written out by hand.

## Why the rest cannot go in this gate

The demo shell sends `X-NF-Org-Id` and no cookie. Converting a module it calls
returns 401 to the demo, and the demo is what the deployment exists to show.
Exactly one identity has a membership, so a session exists for one person.

`isolation_routes` went first because it is the only module nothing calls — no
frontend code, no script, no e2e spec — and because it ran on the weaker
`isolation_deps` chain, which resolves `org_type` from the settings allowlist
rather than from the `organizations` row. That chain now has **zero route
consumers**, which makes deleting it a deletion rather than a rewrite.

## What each conversion has to do

```text
1  depend on deps_customer_auth.get_customer_org_context_required (or the
   demo/real guards beside it) instead of deps_db.get_org_context_with_db
2  return 401 when there is no verified session, rather than falling back to
   the header
3  keep organization_id as the authority: the membership row supplies it, and a
   cookie claiming a different organization gets nothing
```

Gate 133F made two upgrades that any conversion needs and that Gate 122 could
not make when it wrote the replacement:

```text
membership_verified   was hardcoded False; Gate 132 built the read path
org_type              was hardcoded "real"; it reads organizations.org_type now
```

## Then, and only then

`NF_DEV_ORG_HEADERS=false`, and `dev_header_disabled_for_production` becomes
true — the last `customer_auth_live` blocker that is engineering rather than a
decision. Flipping it before the conversions would 401
0 routes at once.
