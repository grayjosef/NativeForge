# 661 — Gate 122A: dev header replacement survey

Read before implementing. Every answer below was measured, not recalled.

## The nine questions

```text
1  route modules using the dev header dependency   14, not 15
2  which uses are customer-facing                  none reachable by a customer
3  which uses are demo/dev-only                    all of them, by construction
4  which can switch to the auth claim guard now    none, and the reason matters
5  which must stay dev-only behind a guard         all 14
6  can the replacement be introduced centrally     yes - one provider, one file
7  would product route behaviour change            no, if the replacement is
                                                   added beside rather than over
8  would any route become inaccessible             yes, all 14, if converted now
9  would the public demo break                     no - it never calls the API
```

## 1. Fourteen route modules, not fifteen

The dev header reaches routes through one chain in
`src/nativeforge/api/deps_db.py`:

```text
get_db_session          a SQLAlchemy session
get_org_context_with_db reads X-NF-Org-Id, resolves an organizations row,
                        applies the RLS GUCs, returns an OrgContext
require_demo_org_db     the same, refusing a non-demo org
require_real_org_db     the same, refusing a demo org
```

Counting `Depends(...)` on those four providers across `src/nativeforge/api/`
gives **15 files** — and one of them is `deps_db.py` itself, which depends on
its own providers internally. It is the provider, not a consumer.

```text
14  genuine route modules
 1  deps_db.py, the dependency module being counted as a route module
```

The existing detector reports `dev_header_used_by_routes: 15`. That number has
appeared in a gate remedy, a doc, and a runbook item since Gate 116 — and Gate
116's own correction was for exactly this species of error, a substring match
counting a file that documents the header rather than uses it. This one is
subtler: a real `Depends()`, in a file that is not a route.

Gate 122D fixes the count and separates the two.

The fourteen:

```text
activation_routes.py                    grant_spark_routes.py
form_package_routes.py                  nofo_extraction_routes.py
operator_workbench_advisory_routes.py   opportunity_discovery_routes.py
pursuit_brief_routes.py                 pursuit_routes.py
source_ingestion_routes.py              spark_scoring_routes.py
sprint0_routes.py                       stage12_guided_demo_routes.py
tribal_profile_routes.py                trust_routes.py
```

Four more files mention `X-NF-Org-Id` in prose only and depend on nothing:
`auth.py`, `capability_guard.py`, `isolation_deps.py`, `request_identity.py`.
Three of those four document why they do *not* use it.

## 2–3. None of the uses is customer-facing, because nothing customer-facing exists

```text
API paths referenced by frontend/src   NONE
API paths referenced by frontend/e2e   NONE
```

The frontend calls the API **zero times**. The public demo is a static React app
fed by committed JSON snapshots, and the Playwright specs assert against
rendered DOM, not against responses.

So every one of the fourteen is reachable only by an operator with `curl` and a
UUID, in a deployment where `NF_DEV_ORG_HEADERS=true`. That is the current
posture and it is why the header has survived this long without being an active
incident.

## 4. Why none can switch to the claim guard *now*

The claim guard already refuses the dev header, in both directions:

```text
claim_source          production_context   rls_context_allowed
dev_request_header    True                 False
dev_request_header    False                False
verified_auth_claim   True                 True
demo_fixture          either               False
```

`dev_request_header_is_not_an_authenticated_claim` — the guard has been correct
about this since Gate 111 and nothing routes its answer.

The trouble is what happens if a route switches today. `verified_auth_claim` is
the only source the guard trusts, and producing one needs a verified session,
which needs customer auth, which Gate 121 measured as eleven gates away with
**zero code-only blockers**.

```text
convert a route now  ->  every request to it returns 401
                     ->  14 route modules become unreachable
                     ->  nothing gains safety, because nothing was reachable
                         by a customer in the first place
```

That is the trade this gate declines. Converting now would break the operator
path that exists to buy a safety property that is already held by the fact that
no customer can reach these routes at all.

## 5. All fourteen stay dev-only, behind an explicit guard

What they get instead is a *named* posture. Today the guard is implicit: the
routes work because `nf_dev_org_headers` defaults to `True` and nobody has
turned it off. After this gate the mode is explicit, the dev path is labelled
`dev_demo_explicit`, and production mode refuses the header with a reason
rather than by accident.

## 6. The replacement can be central

One provider chain, one file, four functions. A replacement introduced beside
`get_org_context_with_db` — rather than over it — reaches all fourteen modules
without touching any of them.

That is the shape Gate 122C builds: `deps_customer_auth.py` with a required
path, an optional path, and an explicitly-named dev path.

## 7–8. Behaviour changes only if a route opts in

Adding a dependency module changes nothing until a route imports it. The
fourteen keep the behaviour they have; the new path exists, is tested, and is
reachable when a session can be produced.

Any route converted before that would return 401 to everybody — the same
untestable-conjunct shape this campaign has hit five times, arriving this time
as a *deployment* property rather than a service field.

## 9. The demo cannot break

```text
frontend API calls        0
e2e API assertions        0
demo data source          committed JSON snapshots
```

Verified rather than assumed, because "the demo might break" is the reason a
migration like this usually stalls. It cannot break, and that is worth knowing
before rather than after.

## The counting defect, stated plainly

```text
before   dev_header_used_by_routes: 15
after    dev_header_route_modules: 14
         dev_header_provider_modules: 1
         dev_header_prose_only_modules: 4
```

Same header, three different relationships to it. A single number that conflated
the first two has been quoted in four places since Gate 116.

## Implementation constraints carried out of this survey

```text
1  add the replacement beside the dev path, never over it
2  production mode must refuse X-NF-Org-Id as authority, with a reason
3  the dev path must be named dev_demo_explicit and refuse in production
4  optional mode returns no_org_context, never a fabricated organization
5  tenant_id, customer_org_id and organization_profile_id never set RLS context
6  count genuine Depends() uses, and separate the provider from its consumers
7  safe_to_disable_now stays false while any of the fourteen has no replacement
8  auth_replacement_available may become true only when the central replacement
   exists - a module that can be imported, not a route that can be reached
9  every new conjunct both derived and injectable
10 no route conversion in this gate; document the fourteen and why
```
