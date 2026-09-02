# 714 — Gate 135: dead dev-header chain removal

## What went

```text
api/deps_db.py                three functions, 61 lines
  get_org_context_with_db     X-NF-Org-Id -> OrgContext + app.current_org_id
  require_demo_org_db         the same, refusing a real organization
  require_real_org_db         the same, refusing a demo one

api/isolation_deps.py         the whole file, 72 lines
  the parallel chain that resolved org_type from the NF_DEMO_ORG_IDS
  allowlist rather than from the organizations row

api/deps_customer_auth.py     one function, 26 lines
  get_dev_org_context_explicit_only
```

159 lines. Nothing in `api/` reads `X-NF-Org-Id` any more.

## Why this was safe now and not in Gate 122

Gate 111A named `get_org_context_with_db` as the one code path in the tree that
set the RLS session variable from an unauthenticated request. It stayed for
twenty-four gates, and every one of them was right to leave it: 207 routes
across 14 modules could not answer a request without it.

That is what made it dangerous. Load-bearing meant the setting could not be
turned off, so `dev_header_disabled_for_production` could not pass, so customer
auth could not go live. Deleting it in Gate 122 would have returned 401 to every
caller and made nothing safer.

Gate 134 converted all fourteen modules onto
`api/customer_org_context_dependency.py`, which derives an organization from a
membership row. That left the chains standing with nobody calling them — which
the readiness service measured and reported, and which is a different state from
gone. A function that reads the header is one edit from a route trusting it
again.

Convert first, delete second. The order is the whole thing.

## `get_dev_org_context_explicit_only` in particular

Gate 122 added it deliberately: a module that could not be converted yet could
ask for the header *by name*, so the reliance was visible instead of inherited.
It refused production with 403 and reported `production_safe: False` on every
result.

Gate 134 converted all fourteen without one caller reaching for it. An escape
hatch nobody used is an unused way of reading the header, and this gate deleted
it. `tests/test_gate122_dev_header_replacement.py` now asserts its absence
rather than its presence — the same test, inverted, with the reason recorded.

## `get_db_session` stays

Twelve route modules import it. It hands out a database session and reads no
header; it was never part of the chain that made the header authority. The two
were in one file, which is a reason to read the file rather than the filename.

## What the detectors say now

```text
dev_header_used_by_routes       0
dev_header_route_modules        []
dev_header_provider_modules     []          was ["deps_db.py",
                                                 "isolation_deps.py"]
dev_header_mention_only_modules ["auth.py", "capability_guard.py",
                                 "customer_org_context_dependency.py",
                                 "deps_customer_auth.py", "deps_db.py"]
```

Five modules still name the header. All five name it to explain why they do not
use it, which is the distinction Gate 116 added the mention list for.

## A zero that can still go back up

Three empty lists are three chances for a detector to have quietly stopped
looking. Each is exercised against a directory that does have what it is looking
for:

```text
a route module importing require_real_org_db        counted, module_count 1
a provider defining the chain and wiring it to      counted as provider,
  itself                                              never as a consumer
```

The provider case needed the fixture written faithfully — a module that defines
the chain *and* `Depends()` on it — because a file that merely defines the
functions is not what `deps_db.py` was.

## The mentions list was wrong, and word boundaries fixed it

While measuring, the mention detector reported all fourteen converted modules as
discussing the header. `require_demo_org` is a prefix of
`require_demo_org_session`, the replacement each of them had just been moved
onto, and the check was a substring test.

Word-bounded now (`\brequire_demo_org\b`). This is the tenth substring-for-
meaning defect this campaign has found, and the tenth to have read as coverage
while measuring nothing.
