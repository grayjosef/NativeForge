# Gate 134 — the dev-header blocker, and what is left

## The count

```text
before (Gate 133)    14 modules, 207 routes
after                0 modules, 0 routes
converted here       14 modules, 207 routes
converted overall    15 modules, 209 routes
```

Measured by walking every registered route and reading its resolved dependency
tree, which is how a route inherits the header without naming it.

## Why it could go this fast

The public demo never reached these routes. The deployed bundle's API base is
`http://127.0.0.1:8000` — the **viewer's own machine** — because `VITE_API_BASE`
is not set at build time, and the two demo surfaces short-circuit their API
calls entirely and render from bundled JSON. Measured in a browser against the
live deployment: zero `/v1` requests.

So "do not break the public demo shell" and "convert aggressively" were not in
tension. They looked like they were until somebody checked.

The cost was in the tests, and it was uniform: fifty-one files shared one
one-line helper returning `{"X-NF-Org-Id": str(oid)}`. It returns a signed
session for a member of the same organization now, so the call sites did not
change.

## What remains

```text
route consumers                  0
provider modules                 []
```

The providers are the chains themselves — `deps_db.get_org_context_with_db` and
`isolation_deps.get_org_context_dev`. Both still exist and **no route depends on
either**. Deleting them is a deletion rather than a rewrite, and it is Gate 135's
to do: their own tests still exercise them directly, and removing a dependency
in the same change that proves nothing uses it would remove the proof too.

## `NF_DEV_ORG_HEADERS=false`

Safe, and set. With no route reading the header it is inert either way, which is
why the activation gate now derives `dev_header_disabled_for_production` from a
*measured* zero as well as from the setting: a header nothing reads cannot set
an RLS context, whatever the setting says.

## `customer_auth_live` is still false

```text
dev_header_disabled_for_production   TRUE, measured
invite_binding_passed                false - never validated against a real flow
owner approval                       absent - NF_CUSTOMER_AUTH_ACTIVATION_APPROVAL
```

Two blockers left, one of them a decision. `verified_operational_binding` is
also still false: Gate 113's contract refuses a verified binding on a demo
organization.

## Next

Gate 135: delete the two dev-header chains and their dependencies, run one
invite flow through `membership_invite_approval_service` and record it. That
leaves owner approval, which is not an engineering task.
