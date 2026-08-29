# 629 — Gate 115D: the role mapping contract

`src/nativeforge/services/customer_auth_role_mapping_service.py`

Provider roles, groups and claims in; NativeForge roles out. Nothing grants
privilege by default.

## A provider claim is a string somebody else controls

Auth0 groups can be renamed. An OIDC provider can be misconfigured. A claim
named `admin` from an unexpected issuer is an assertion, not an authorization.

So mapping is explicit and closed:

```text
a claim maps to a role only if the configured mapping says so
an unrecognised claim maps to `unknown`
`unknown` grants nothing
```

A test supplies the literal claim `platform_admin` with no configured entry for
it and asserts the result is `unknown` with every permission false.

## The two administrative roles are stricter

`platform_admin` and `tenant_admin` require an explicitly configured mapping.
They are never reached by a default, a pattern match, or a claim that merely
looks administrative. Both have a test asserting that the same claim yields
`unknown` without a mapping and the role with one.

## Least privilege when a principal has several

A provider can assert many groups at once. `least_privilege_role` is the
**weakest** mapped role, and the permission fields derive from it:

```text
unknown  <  grants_viewer  <  auditor  <  grants_manager  <  tenant_admin  <  platform_admin
```

A principal carrying both `nf-platform-admins` and `nf-grants-viewers` resolves
to `grants_viewer`. Taking the strongest would let one stale directory group
silently widen what somebody can do.

## Inspecting a binding is not verifying one

From Gate 111's permission table, bridged rather than restated:

```text
grants_manager   read_operational, write_operational, inspect_binding
                 and NOT verify_binding
```

`can_verify_binding` requires the `verify_binding` permission — which only the
two administrative roles hold — **and** separate binder authorization at the
Gate 111 layer. A `platform_admin` without that authorization gets
`can_verify_binding: false` and a named reason.

Tests assert `grants_viewer`, `auditor` and `grants_manager` can never verify.

## No role grants an RLS context

Whatever a claim maps to, it never sets `app.current_org_id`. That requires
Gate 112's `organization_id` resolution **and** a verified membership record,
both of which are inputs here rather than decisions.

A `platform_admin` with a full mapping and binder authorization, but without
either prerequisite, gets every permission false:

```text
organization_id_resolved: false   ->  can_view_grants false, can_verify false
membership_verified: false        ->  can_view_grants false, can_verify false
```

`current_org_id_set` is a constant `False` with an invariant behind it.

## A mapping pointing at a role that does not exist

Refused, with the invalid target named. A configuration error is not a grant,
and the claim falls through to `unknown` rather than to whatever was typed.
