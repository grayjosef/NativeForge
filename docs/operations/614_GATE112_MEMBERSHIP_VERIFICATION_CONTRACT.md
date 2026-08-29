# 614 — Gate 112C: membership verification contract

`src/nativeforge/services/customer_org_membership_verification_service.py`

## Verified membership is required for RLS

An organization claim says *which* organization was asserted. Membership says the
person belongs to it. Both, or no RLS context.

Gate 111's principal contract was tightened accordingly: `rls_context_allowed`
now requires `membership_verified`, and an invariant fails a principal claiming a
context without it. Two Gate 111 tests were updated to supply the new fact rather
than deleted — the rule they guarded got stronger, not obsolete.

## Keyed on organization_id, deliberately

Gate 112A found both existing membership directories key on
`organization_profile_id`, and that the Postgres one binds a parameter of that
name to the `organization_id` UUID column — two identity spaces sharing one
variable.

This service keys on `organization_id` and nothing else. `nf_org_memberships`
carries it as a UUID foreign key to `organizations.id` under the same RLS policy
as every other table, so matching on it is matching on what the database
enforces.

A record for a different organization does not count. The mutation that matches
any record regardless of organization is caught.

## Membership is read from state, not from existence

A row means somebody once proposed a relationship. Whether it currently holds is
in `state` and `revoked_at`.

```text
verified_member    an active state, not revoked
verified_admin     the same, and the role carries administrative authority
pending_member     proposed, nobody approved it
missing_membership no record for this organization
conflict           records disagree about the same organization
revoked            withdrawn
demo_fixture       a demo relationship
unknown            an unrecognised state
```

A service that treated "a row exists" as membership would keep letting revoked
people in. The mutation removing the `revoked_at` check is caught.

## Member and admin are different answers

```text
can_set_rls_context   verified_member or verified_admin
can_verify_binding    verified_admin only
```

Acting within an organization is not administering it. Gate 111 restricted binder
authority to `platform_admin` and `tenant_admin`; reporting these as one flag
would let a grant lead quietly inherit it. The mutation granting binder authority
to members is caught.

## A UUID is required even when membership is fine

`can_set_rls_context` requires a UUID-shaped `organization_id` as well as
verified membership. That conjunct is only observable when a matching record
exists for a profile-shaped organization — with no record the missing-membership
branch blocks first — so a test supplies exactly that case.

## demo_fixture is not production membership

It permits nothing operational, `is_production_membership` is False, and
invariants fail a demo membership claiming production or carrying authority.
