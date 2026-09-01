# 708 — Gate 134: the conversions

```text
before    14 modules, 207 routes reading X-NF-Org-Id
after      0 modules,   0 routes
overall   15 modules, 209 routes converted, counting Gate 133F's isolation_routes
```

Measured by walking every registered route and reading its resolved dependency
tree, on every call. Not a list anybody maintains.

## Modules converted, in the kill plan's order

```text
 1  stage12_guided_demo_routes            4
 2  trust_routes                          8
 3  activation_routes                     6
 4  form_package_routes                   6
 5  nofo_extraction_routes                6
 6  pursuit_brief_routes                  6
 7  spark_scoring_routes                  6
 8  tribal_profile_routes                 8
 9  operator_workbench_advisory_routes    8
10  grant_spark_routes                    9
11  sprint0_routes                       10
12  pursuit_routes                       20
13  source_ingestion_routes              26
14  opportunity_discovery_routes         84
```

## What a conversion is

An import swap. Every module depended on the same two names, so:

```python
-from nativeforge.api.deps_db import require_demo_org_db, require_real_org_db
+from nativeforge.api.customer_org_context_dependency import (
+    require_demo_org_session,
+    require_real_org_session,
+)
```

and the `Depends(...)` names follow. Same return type, same 403 semantics, same
RLS context. No route body changed, and no route's tenant guard changed: every
one still calls `guard_same_org_404(org_id, ctx)` with the id from its own URL.

The dependency decides which organization the caller **is**; the guard decides
whether the URL agrees. A session for organization B requesting organization A's
URL still gets 404 — and now it could not have been B by accident.

## Why the tests were the whole cost

Fifty-one files shared one helper, character for character:

```python
def _hdr(oid: uuid.UUID) -> dict[str, str]:
    return {"X-NF-Org-Id": str(oid)}
```

`tests/session_org_helper.py` provides the same shape backed by a real session:
it writes an `organizations` row, an `nf_identities` row through the actual
upsert path, and an `nf_org_memberships` row, then mints a session through
`customer_session_format_service` — which refuses one that would not verify. No
fake session, no fake user; a test that passes has exercised the whole chain.

Four files had variants (a role header alongside, a no-argument form, two inline
dicts) and were converted by hand. Eight files whose subject *is* the header
were excluded by name.

## What broke, and what that says

The full suite after converting all 207 routes and 55 test files:

```text
10,489 passed
15 failed
```

Every one of the fifteen asserted that the dev header was still load-bearing.
Zero product regressions. The list is worth reading as a map of where a
migration's assumptions get written down:

```text
gate 115   "the dev header is load bearing and cannot go yet"
gate 116   the usage detector's count > 0
gate 122   remaining modules == 14, in eight places
gate 133   dev_header_route_count > 0, and the ordering test needing rows
+ five committed artifacts embedding one of those numbers
```

Each was updated to the new state rather than deleted, and each kept what it was
for. Gate 115's became "no longer load bearing" **plus** a new test that points
the detector at a directory where a module does use the header and asserts it
counts it — so the zero is a migration that finished rather than a detector that
stopped looking.

## Two guards that fired on a zero that used to be impossible

`dev_header_replacement_demo_fixture_service` and
`dev_header_replacement_artifact_service` both refused a result reporting no
remaining route modules. That was the right guard: while 207 routes read the
header, a zero could only mean the detector had gone blind.

Gate 126 settled what to do when an invariant fires on its own permitted branch —
ignoring it makes it read as coverage. So both are **narrowed**, not removed: a
zero is permitted only when the service can also name what the modules were
converted onto. A detector gone blind reports zero and zero; a finished migration
reports zero and sixteen.

## What still reads the header

Nothing that serves a route.

```text
deps_db.get_org_context_with_db            defines the chain, 0 route consumers
isolation_deps.get_org_context_dev         defines the other one, 0 consumers
deps_customer_auth.get_dev_org_context_explicit_only   0 consumers
```

All three remain, and deleting them is Gate 135's. Their own tests exercise them
directly, and removing a dependency in the same change that proves nothing uses
it would remove the proof with it.

`dev_org_header_shutdown_readiness_service` was missing five of the seven
dependency names — a module depending only on `require_real_org_db`, or on the
`isolation_deps` chain, was not counted as a consumer at all. The count that
gates the shutdown decision could have read zero while routes still read the
header. Widened, along with the provider list it needed to keep the two apart.

## `NF_DEV_ORG_HEADERS=false`

Safe, and set on the deployment. With no route reading the header it is inert
either way, which is why the activation gate now derives
`dev_header_disabled_for_production` from a measured zero **as well as** from the
setting: a header nothing reads cannot set an RLS context, whatever a setting
says.

Measured on the running backend afterwards, with the header and a real
organization id:

```text
/v1/isolation/demo-only                          401
/v1/nf/demo/orgs/<demo>/discovery/stage12-...    401
/v1/nf/demo/orgs/<demo>/trust/manifest           401
/v1/nf/demo/orgs/<demo>/grant-sparks             401
/api/auth/login                                  302
/api/auth/current-user (no session)              401
```
