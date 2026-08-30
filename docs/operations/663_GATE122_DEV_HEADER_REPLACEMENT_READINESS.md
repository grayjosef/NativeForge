# 663 — Gate 122: dev header replacement readiness

What changed, what did not, and the sentence to refuse.

## The sentence to refuse

> "The replacement exists, so the dev header is gone."

The replacement exists and is imported by no route. **Fourteen route modules**
still obtain an organization through `X-NF-Org-Id`, and every one stays for the
same reason.

## The counting correction

```text
before   dev_header_used_by_routes: 15
after    route modules      14
         provider modules    1   deps_db.py
         prose-only          3   modules that name it without wiring it
```

`deps_db.py` defines the dev-header chain and uses its own providers
internally. It was being counted as one of the routes that consume it.

That number has appeared in a gate remedy, a runbook item, an activation
blocker and a readiness doc since Gate 116 — whose own correction was for
exactly this species of error, a substring match counting a file that documents
the header rather than uses it. This one was subtler: a real `Depends()`, in a
file that is not a route.

The inventory CSV now carries three relationships, and only `route` counts
toward the migration.

## What moved

```text
                          before      after
org context contract      none        3 modes, 12 reported fields
central dependency        none        3 functions, imported by no route
dev header posture        implicit    named dev_demo_explicit, refused in
                                      production, refused on an unknown app_env
claim guard wiring        none        routed for the first time since Gate 111
route module count        15          14, provider separated
```

## What did not move

```text
customer_auth_live                     false
login_live                             false
customer_persistence_live              false
safe_to_disable_now                    false
dev_header_is_production_safe          false
dev_header_is_customer_auth            false
must_disable_before_production_auth    true
routes converted                       0
real customer data written             0
current org id set by this gate        0
production-safe dev header uses        0
alembic head                           0030, unchanged
```

## The fourteen that remain

```text
activation_routes.py                    grant_spark_routes.py
form_package_routes.py                  nofo_extraction_routes.py
operator_workbench_advisory_routes.py   opportunity_discovery_routes.py
pursuit_brief_routes.py                 pursuit_routes.py
source_ingestion_routes.py              spark_scoring_routes.py
sprint0_routes.py                       stage12_guided_demo_routes.py
tribal_profile_routes.py                trust_routes.py
```

Each appears in `dev_header_usage_inventory.csv` with the same reason, and the
artifact writer refuses to write a module with an empty one — a list of fourteen
names with no explanation reads as an oversight rather than a decision.

## Why no route was converted

```text
convert now  ->  the only claim source the RLS guard trusts is
                 verified_auth_claim
             ->  producing one needs customer auth
             ->  Gate 121 measured that as 11 activation gates away with
                 zero code-only blockers
             ->  every converted route returns 401 to every caller
```

And converting would buy nothing, because of a fact worth stating plainly:

```text
API paths called by frontend/src   0
API paths called by frontend/e2e   0
```

The frontend calls the API **zero times**. The public demo is a static React app
fed by committed JSON snapshots, and the Playwright specs assert against
rendered DOM. So the fourteen are reachable only by an operator with `curl`, a
UUID and `NF_DEV_ORG_HEADERS=true`.

That is why the demo cannot break, and it is also why the conversion is not
urgent. Both halves are worth knowing before the migration rather than after.

## The gate that would have been a mistake

Converting all fourteen "for safety" would have made every product route
unreachable, in exchange for a property the deployment already holds by
accident. It would have looked like progress on a checklist and been a
regression in the system.

This is the same untestable-conjunct shape the campaign has hit five times in
services — a branch that cannot be reached makes every claim about it
unfalsifiable — arriving this time as a deployment property rather than a
service field.

## Nothing was written, called, or claimed

```text
routes converted                  0
customer data written             0
production verified bindings      0
real users created                0
production sessions created       0
RLS context set by this gate      no
live provider called              no
live source called                no
URL fetched                       no
collector executed                no
scraper activated                 no
email sent                        no
secret or env value printed       none
```

## What the next gate needs

```text
1. customer auth activation   the 11 gates from Gate 121. Until a session can
                              verify, no route can be converted without
                              becoming unreachable.

2. then convert the fourteen  one at a time, each with a test proving
                              unauthenticated refusal or optional no-context
                              behaviour

3. then disable the header    safe_to_disable_now becomes true only when no
                              route module depends on it
```

The order is not negotiable and step 1 is not a code change. That has been the
answer since Gate 121 and this gate does not move it — what it moves is the
thing waiting behind it, which is now built, tested, and one import away from
each of the fourteen.
