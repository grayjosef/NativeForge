# Gate 133F — the dev-header kill plan

## Where it stands

```text
routes total                     217
routes reading X-NF-Org-Id       207
modules reading it               14
converted in Gate 133F           isolation_routes (2 routes)
publicly routed of those         207
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
207 stayed exposed.

Third instance of this shape in three gates: Gate 130's detector read the wrong
cloudflared file, Gate 131's migration reader hardcoded one filename for a table
defined by two, this one models one hop of two.

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
207 routes at once.
