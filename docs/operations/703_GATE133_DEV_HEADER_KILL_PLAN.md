# 703 — Gate 133F: the dev-header kill plan

The generated copy of this, with the exposure matrix beside it, is
`artifacts/login_live_dev_header_kill/dev_header_kill_plan.md` and
`dev_header_exposure_matrix.csv`. Both regenerate from
`dev_header_exposure_matrix_service`, which walks the FastAPI app and parses the
two config files. This document is the operations narrative; the artifact is the
measurement, and a test asserts the artifact names every module.

## Where it stands

```text
routes total                        217
routes reading X-NF-Org-Id          207     (was 209)
modules reading it                   14     (was 15)
converted in Gate 133F              isolation_routes, 2 routes
publicly routed of those            207     all of them
behind Cloudflare Access            yes, and only that
```

## Derived from the app, not from grep

A route inherits the dev header through a dependency it never names:
`require_demo_org_db` depends on `get_org_context_with_db`, which declares the
header. Grepping the fifteen route modules for `X-NF-Org-Id` finds **none** of
them. The matrix walks each route's resolved dependency tree instead.

## How they are reachable, which is not what the detector says

```text
cloudflared ingress   ^/api/.*     -> 127.0.0.1:8000    the backend
cloudflared catch-all (hostname)   -> 127.0.0.1:5175    the Vite preview
vite preview proxy    /v1 /docs /openapi.json /redoc -> 127.0.0.1:8000
```

Every dev-header route is under `/v1`, so **none is reached by the ingress rule
`dev_org_header_containment_service` inspects.** They are reached by the preview
proxy, one hop further in, which that detector does not model.

Its conclusion — `backend_publicly_exposed: true` — is right today because of
the `/api/*` rule, which covers the five auth routes and no dev-header route.
Delete that ingress line and it would report the backend contained while all 207
stayed exposed.

Third instance of this shape in three gates:

```text
Gate 130   the detector read ~/.cloudflared/config.yml while the live tunnel ran
           nativeforge-mayhem.yml
Gate 131   a migration reader hardcoded one filename for a table defined by 0030
           plus 0036
Gate 133   a detector models one hop of two
```

The new service reads **every** config in the cloudflared directory and parses
the preview proxy table out of `frontend/vite.config.ts`. It also refuses to
report containment it did not measure: a matrix that found no exposure path at
all fires an invariant, because the likeliest cause is a config it could not
read.

One correction worth recording: the first version of the proxy parser scanned
the whole file for `"<prefix>": api` and reported `/health` as publicly proxied
to the backend. `/health` is in `server.proxy` only — the config says so in a
comment — and over-reporting an exposure is still a wrong measurement.

## Access is a boundary, and not this one

Access decides who reaches the app. It does nothing about which organization a
header names once somebody is through. Anybody inside the Access policy can set
`X-NF-Org-Id` to any organization id and read that organization's rows. That is
why `dev_header_disabled_for_production` is a `customer_auth_live` blocker
rather than a tidiness item.

## The order, least risky first

| # | module | routes | risk | why |
|---|---|---:|---|---|
| 1 | `stage12_guided_demo_routes` | 4 | low | guided demo surface, served from a committed payload; the frontend reads the payload rather than these routes |
| 2 | `trust_routes` | 8 | low | read-only trust manifest; the demo shell calls it and would need a session first |
| 3 | `activation_routes` | 6 | medium | workspace activation flags; writes durable state, so a wrong organization here persists |
| 4 | `form_package_routes` | 6 | medium | review-gated packages; writes |
| 5 | `nofo_extraction_routes` | 6 | medium | extraction runs; writes |
| 6 | `pursuit_brief_routes` | 6 | medium | derived briefs; writes |
| 7 | `spark_scoring_routes` | 6 | medium | deterministic scores; writes |
| 8 | `tribal_profile_routes` | 8 | medium | customer-owned profile data. A wrong organization writes a Tribe's facts into another Tribe's row |
| 9 | `operator_workbench_advisory_routes` | 8 | high | operator advisory surface; the demo shell reads it |
| 10 | `grant_spark_routes` | 9 | high | the discovery surface the demo shell reads |
| 11 | `sprint0_routes` | 10 | high | foundational org routes other modules assume |
| 12 | `pursuit_routes` | 20 | high | pursuit workflow, 20 routes, writes throughout |
| 13 | `source_ingestion_routes` | 26 | high | 26 routes; touches the collector boundary, which must stay off |
| 14 | `opportunity_discovery_routes` | 84 | highest | 84 routes, the largest surface in the application and the one the demo depends on most |

Route counts are measured. Risk is a judgement, recorded in
`CONVERSION_NOTES` so it sits next to the number it qualifies. Within a band the
smaller surface goes first, and an invariant asserts the order is a permutation
of 1..14 with no module left unclassified.

## Why `isolation_routes` went first, and alone

It is the only dev-header module that is not part of the demo product. Nothing
calls it: no frontend code, no script, no e2e spec. Its entire purpose is proving
demo/real separation, and proving that through an authenticated session is a
better proof than proving it through a header anybody can set.

It was also on the *other* chain — `isolation_deps`, which resolves `org_type`
from the `NF_DEMO_ORG_IDS` allowlist rather than from the `organizations` row.
Gate 132 found that chain classifying the demo organization as `real` because
the allowlist was empty, so `/v1/isolation/demo-only` refused the demo
organization and `/v1/isolation/real-only` admitted it. Exactly backwards.

That chain now has **zero route consumers**, asserted by a test. Deleting it is
a deletion rather than a rewrite.

## Two upgrades any conversion needs

Gate 122 wrote the replacement dependency and could not finish it, because
neither of these existed yet:

```text
membership_verified   was hardcoded False, with the reason recorded: "a
                      membership record is a database question this dependency
                      does not ask". Gate 132 built the read path.
org_type              was hardcoded "real", with the reason recorded: "this
                      dependency does not read the organizations row". A demo
                      session classified real is refused by every demo-only
                      route, which is why it could not be attached to one.
```

Both are done. `deps_customer_auth` reads the membership and classifies the
organization from its row, and two new guards —
`require_customer_demo_org` and `require_customer_real_org` — are the
session-backed counterparts of the `isolation_deps` pair.

The cross-organization rule came with them: a cookie naming organization A held
by a member of organization B gets nothing. That is Gate 132's fix, now enforced
at this dependency too, with a test.

## What each conversion has to do

```text
1  depend on deps_customer_auth.get_customer_org_context_required, or the
   demo/real guards beside it, instead of deps_db.get_org_context_with_db
2  return 401 with no verified session, rather than falling back to the header
3  keep organization_id as the authority - the membership row supplies it
4  update the module's tests to seed a session instead of sending a header
```

## Why the rest could not go in this gate

The demo shell sends `X-NF-Org-Id` and no cookie. Converting a module it calls
returns 401 to the demo, and the demo is what this deployment exists to show.
Exactly one identity has a membership, so a session exists for one person.

Half-converting several modules and leaving them broken would have been worse
than converting one and writing the plan. This is one conversion, not a
half-conversion of many.

## Then, and only then

`NF_DEV_ORG_HEADERS=false`, and `dev_header_disabled_for_production` becomes
true — the last `customer_auth_live` blocker that is engineering rather than a
decision. Flipping it before the conversions would 401 all 207 routes at once,
including everything the demo shell reads.
