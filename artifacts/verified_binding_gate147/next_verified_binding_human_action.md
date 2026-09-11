# Gate 147 — the next verified-binding human action

`verified_operational_binding` is false for five reasons, and clearing
any one of them moves nothing on its own.

```text
demo_organization_is_never_a_verified_operational_binding
    kind   never_clears
    owner  nobody
organization_is_the_explicitly_refused_real_org
    kind   never_clears_without_a_reviewed_code_change
    owner  Mayhem
organization_is_not_in_the_authorized_real_org_list
    kind   reviewed_code_change
    owner  Mayhem
no_approval_object_supplied
    kind   recorded_decision
    owner  Mayhem
production_verified_binding_requires_live_customer_auth
    kind   an_event
    owner  the second person, then the operator
verifier_principal_is_not_qualified
    kind   authenticated_role
    owner  the acting principal
```

## The order they have to be cleared in

```text
1  a real customer organization has to exist
     there is none in this deployment other than the refused one.
     This is the step that is further away than it looks.

2  the second-person event                    Gate 146
     unlocks customer_auth_live, which the verified binding needs
     because the row asserts somebody verified something

3  Mayhem authorizes that organization
     a reviewed code change adding its id to
     AUTHORIZED_REAL_ORGANIZATION_IDS - not an environment variable,
     and not the injectable test set, which strips both the demo and
     the real organization ids

4  an approval object is recorded
     five fields, and a scope that covers the environment

5  a qualified verifier principal acts
     an authenticated platform_admin or tenant_admin with
     verified-org status
```

## What never clears

```text
the demo organization is never a verified operational binding
    in any environment, with any approval, with any principal.
    Derived from organizations.org_type.
```

That is not a limitation to be worked around. It is the fifth
conflation Gate 145 named — the demo organization is not a customer
organization — enforced against the organization rather than against a
label somebody passed in.

## What stays false

```text
verified_operational_binding   false
customer_auth_live   false
controlled_customer_pilot   false
production_rollout   false
```

This gate made the boundary exact. It did not move it.
