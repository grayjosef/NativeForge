# Dev header replacement readiness (Gate 122)

## The sentence to refuse

> "The replacement exists, so the dev header is gone."

The replacement exists and is imported by no route. Fourteen route
modules still obtain an organization through `X-NF-Org-Id`, and every
one of them stays for the same reason: converting today would return
401 to every caller, because the only claim source the RLS guard
trusts needs customer auth.

## The counting correction

```text
before   dev_header_used_by_routes: 15
after    route modules:     14
         provider modules:  1
         prose-only:        3
```

`deps_db.py` defines the dev-header chain and depends on its own
providers internally. It was being counted as one of the routes that
consume it, which overstated the migration by one in four places since
Gate 116.

## What moved

```text
org context contract        none      3 modes, 12 reported fields
central dependency          none      3 functions, imported by no route
dev header posture          implicit  named dev_demo_explicit, refused
                                      in production
claim guard wiring          none      routed for the first time
route module count          15        14, with the provider separated
```

## What did not move

```text
customer_auth_live                          false
login_live                                  false
customer_persistence_live                   false
safe_to_disable_now                         false
dev_header_is_production_safe               false
current_org_id_set_by_this_gate             false
production_safe_dev_header_uses             0
real_customer_data_written                  0
routes_converted                            0
```

## The fourteen route modules that remain

```text
activation_routes.py
form_package_routes.py
grant_spark_routes.py
nofo_extraction_routes.py
operator_workbench_advisory_routes.py
opportunity_discovery_routes.py
pursuit_brief_routes.py
pursuit_routes.py
source_ingestion_routes.py
spark_scoring_routes.py
sprint0_routes.py
stage12_guided_demo_routes.py
tribal_profile_routes.py
trust_routes.py
```

Each is listed in `dev_header_usage_inventory.csv` with the same
reason. None was converted, and converting any of them before a
session can verify would make it unreachable.

## Why converting now would gain nothing

```text
API paths called by frontend/src   0
API paths called by frontend/e2e   0
```

The frontend calls the API zero times; the public demo is a static
app fed by committed JSON. So no customer can reach the fourteen
today, and the safety property a conversion would buy is one the
deployment already has by accident.

That is worth saying plainly rather than leaving as an assumption:
the demo cannot break, and the reason it cannot is also the reason
the conversion is not urgent.

## The fixture set

```text
cases                        9
permitted org contexts       1
dev-only contexts            1
refused with 401             5
any claiming auth live       false
```

Exactly one case reaches a production-safe organization context and
exactly one reaches a dev-only one. Collapsing those two would undo
the distinction this gate exists to make.

## What the next gate needs

```text
1. customer auth activation   the 11 gates from Gate 121. Until a
                              session can verify, no route can be
                              converted without becoming
                              unreachable.

2. then convert the fourteen  one at a time, each with a test
                              proving unauthenticated refusal or
                              optional no-context behaviour

3. then disable the header    safe_to_disable_now becomes true only
                              when no route module depends on it
```
