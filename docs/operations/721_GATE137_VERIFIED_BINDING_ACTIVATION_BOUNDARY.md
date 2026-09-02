# 721 — Gate 137: the verified binding activation boundary

## What this closes

Measured in 137A, with a fully-qualified verifier principal and
`customer_auth_live` injected true, against the **real** organization:

```text
authorization_allowed         True
repository_write_allowed      True
repository_write_performed    True
verified_operational_binding  TRUE
rows_written                  1
blocked_reasons               []
stored: organization_id=aaaaaaaa-…, verified_binding, is_demo=0
```

Nothing in the chain checked which organization it was.
`verified_binder_authorization_service` decides by role:

```text
VERIFIER_ROLES            {platform_admin, tenant_admin}
OPERATIONAL_AUTH_STATUSES {authenticated_verified_org}
```

A role is not an authorization to bind a particular Tribe's organization. The
real org was not refused by name, was not checked against any list, and needed
no approval of any kind.

**The only thing holding it shut was `customer_auth_live` being false** — via
`production_verified_binding_requires_live_customer_auth`. Gate 136 made that
reachable in minutes. This boundary is what stands behind the guard when it
opens.

## The decision

Same shape as Gate 133D's login decision and Gate 135D's customer-auth
decision, for a different subject.

```text
organization      must be in AUTHORIZED_REAL_ORGANIZATION_IDS
demo              refused by classification, in any environment, with any
                  approval, even if listed
aaaaaaaa-…        refused by name
approval object   required, and must be complete
scope             real_org_binding_activation | production_binding_activation
environment       local | dev | test with the narrow scope
                  production | prod needs the production scope
revocation        NF_REAL_ORG_BINDING_ACTIVATION_REVOKED
grant             no environment variable. None. Reported as
                  grant_environment_variable: null under an invariant.
```

`approves_production_rollout` and `approves_controlled_customer_pilot` are
reported False with no branch that changes them, and an invariant fails if
either is ever true.

## The approval object

Five fields, all required:

```text
organization_id      must be uuid-shaped and must match the request
authorized_by        who authorized it
authorization_scope  one of the two scopes
environment          must match the environment the call runs in
recorded_at          when
```

A dict missing any of them is not an approval, it is a dict, and the refusal
names the missing field. An approval naming a *different* organization gets
`approval_names_a_different_organization` — the substitution that would matter
most.

An approval carrying a label as its subject — `tenant_id`, `customer_org_id`,
`organization_profile_id`, `profile_id`, `subject`, `email` — is refused by
name. That is Gates 110–113's subject, restated because this is a new entry
point and a caller offering one should learn it was refused rather than have it
quietly dropped.

## Two scopes, and the narrow one does not reach the broad one

Gate 133D had to split one environment variable that was gating both a demo
login and customer auth for real Tribes. The same split, before it is needed:

```text
real_org_binding_activation    a real organization, in dev
production_binding_activation  a real organization, in production
```

An approval with the narrow scope in a production environment gets
`approval_scope_does_not_cover_production`. Nothing widens it.

## Why the authorized list is empty

Mayhem's standing authorization, verbatim, enumerates what it does not cover:

```text
This does not authorize:
  production rollout
  controlled customer pilot
  real org activation
  live customer data
  binding to aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee
```

So `AUTHORIZED_REAL_ORGANIZATION_IDS = frozenset()`, and the constant carries
that reason next to it. Authorizing an organization is a reviewed code change
plus an approval object — not a variable somebody exports on a Tuesday.

## A hole this gate's own test found

The authorized list is injectable, so the approved branch is reachable in a
hermetic test. The first version consulted the injected set for **every** id:

```text
authorized_organization_ids = frozenset({REAL_ORGANIZATION_ID})
-> approves_real_org_binding_activation  TRUE
-> a verified binding written for aaaaaaaa-…
```

`test_the_runtime_real_org_is_never_written_to` caught it — one binding where
zero were asserted. An escape hatch that reaches the one organization the
module exists to refuse is not an escape hatch, it is the hole.

Both protected ids are now stripped from anything injected, and the removal is
reported rather than silent:

```text
injected_authorization_ignored_for_a_protected_organization:<id>
```

Reaching them needs the module constant, which is a code change somebody reads.

## What it refuses, measured

```text
the demo org, listed and approved     demo_organization_is_never_a_verified_
                                        operational_binding
aaaaaaaa-…, approved                  organization_is_the_explicitly_refused_
                                        real_org
any unlisted organization             organization_is_not_in_the_authorized_
                                        real_org_list
no approval                           no_approval_object_supplied
an incomplete approval                approval_missing_field:<name>
an approval for another org           approval_names_a_different_organization
an approval for another environment   approval_recorded_for_a_different_
                                        environment:<env>
narrow scope in production            approval_scope_does_not_cover_production
a label offered as authority          not_an_authority_for_a_binding:<key>
a label inside the approval           approval_carries_a_non_authority_
                                        subject:<key>
the revocation variable set           activation_revoked_by_environment
a fixture real org, listed+approved   APPROVED — so every refusal above is a
                                        measurement rather than a constant
```

## What it does not do

It authorizes. It writes nothing, opens no connection of its own, contacts no
provider, and reads exactly one environment variable, which can only say no.
