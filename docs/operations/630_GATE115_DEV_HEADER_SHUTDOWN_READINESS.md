# 630 — Gate 115E: dev org header shutdown readiness

`src/nativeforge/services/dev_org_header_shutdown_readiness_service.py`

What must happen before `X-NF-Org-Id` can go, and why it cannot go today.

## Two questions with opposite answers, and no contradiction

```text
safe_to_disable_now                    false
must_disable_before_production_auth    true
```

It cannot go **yet** because it is load-bearing: sixteen route modules obtain
their organization through it, and no authenticated replacement exists.
Removing it today breaks the application without making anything safer.

It cannot **stay** because an unauthenticated header that sets
`app.current_org_id` is a way to read another Tribe's data by typing a UUID.

## What the header actually is

```text
deps_db.get_org_context_with_db
  requires header X-NF-Org-Id
  refuses entirely unless settings.nf_dev_org_headers is true
  parses the value as a UUID, looks it up in `organizations`
  then calls apply_org_rls_gucs(session, org_id, org_type)
```

It is UUID-validated and existence-checked, so a label cannot reach the RLS
context — Gate 114 verified that no code path carries one there. What it does
not do is establish *who is asking*.

Gate 112 recorded that this is contained by deployment posture — loopback-only
backend behind Cloudflare Access — and containment is not safety. **Cloudflare
Access is not customer app auth.**

## A replacement is a route, not a set of contracts

```text
organization_id_resolution_available   true    Gate 112
membership_verification_available      true    Gate 112
rls_claim_guard_available              true    Gate 111
role_mapping_available                 true    Gate 115D
replacement_route_available            FALSE
auth_replacement_available             FALSE
```

Four contracts exist and there is nowhere for a customer to authenticate. An
invariant fails any result claiming `auth_replacement_available` without
`replacement_route_available`, because contracts existing is the easiest thing
in this repository to mistake for a working system.

## The boundary with no true branch

`must_disable_before_production_auth` is `True` unconditionally, and an
invariant fails any result where it is not.

That is not the kind of hard-coded constant this campaign keeps removing — those
were values that *should* have moved and could not. This one has no true branch
by design, and the invariant exists so nobody quietly gives it one.

## Detection avoids the containment service on purpose

`dev_org_header_containment_service` shells out to `systemctl`, so its output
depends on the machine it ran on. Gate 114 avoided depending on it for anything
reaching a committed artifact, and this service does the same: the header flag
comes from settings, and the route dependency is counted by reading the `api/`
package.

The `api/` directory is injectable, so a test points at an empty one and
observes `dev_header_used_by_routes: 0` — the branch that would otherwise be
unreachable in this repository.

## Reachability

A test supplies an empty `api/` directory, the header disabled, and a route
table with five secured auth routes, and asserts `safe_to_disable_now` becomes
true while `must_disable_before_production_auth` stays true. Both branches
observable; the boundary unmoved.
