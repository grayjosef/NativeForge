# 705 — Gate 133: role mapping evidence

## Why this needed no table when JWKS did

```text
JWKS validation   an EVENT. It happened, and then it stopped existing. A local
                  in a request handler. To measure it, write it down: 0037.
role mapping      a ROW. nf_org_memberships holds the mapping itself, not a
                  report that a mapping occurred. It survives because it is not
                  a memory of anything.
```

`role_mapping_passed` was false for the same reason `org_binding_passed` was
false before Gate 132 — a parameter of `run_auth0_live_validation` that no
caller passed. The fix was a query.

## What "mapped" means

```text
role                nf_org_memberships.role, one of six
role_source         'membership_record'. The only trusted value.
membership_source   verified_directory | operator_approved | org_owner_approved
organization_id     the membership row's
state               'active', not revoked, not expired
```

And what it must never mean:

```text
a cookie's org claim   the cookie says which organization it thinks it is for;
                       the membership says which one the holder belongs to
an email domain        Gate 112. gmail.com is not a Tribe.
a token claim          'token_claim' is in the role-source vocabulary and not in
                       the trusted subset. An IdP group claim is the provider's
                       opinion, not this product's record.
a header               X-NF-Org-Id selects an organization and authenticates
                       nobody
a caller argument      there is no role parameter anywhere in this path
```

## The cookie-override check is an exercise, not a restatement

`cookie_claim_can_override_membership` is derived by two checks, because either
alone would be weak:

```text
1  the resolver's signature is inspected for any parameter a claim could arrive
   under - organization_id, org_claim, claimed_organization_id, ...
2  a claim is actually offered. The resolver has no such parameter, so the call
   raises TypeError, and that is the answer.
```

It is false because Gate 132's fix makes it false. If somebody reintroduces that
defect — a resolver that accepts a claimed organization and returns it — this
reports `True` and the invariant fires, rather than a docstring continuing to
assert it cannot happen.

## A guard that could not fire

The first version of `build_role_mapping_evidence` asked the resolver whether a
membership resolved, and *then* checked the row's `role_source` and
`membership_source` against the trusted sets:

```python
resolution = resolve_session_organization(...)
if not resolution["organization_id_resolved"]:
    continue                                  # <- always taken first
if role_source not in TRUSTED_ROLE_SOURCES:
    blocked_reasons.append(...)               # <- unreachable
```

The resolver already filters on both before counting a membership as active, so
an untrusted source made the row unresolvable and the loop `continue`d one
branch earlier. Both named refusals were unreachable. Gate 126 settled that a
guard which cannot fire reads as coverage and is worse than none.

Caught by a test that set `role_source = 'token_claim'` and asserted the reason
by name. The reasons are now reported as observations about the row, before the
`continue`, and the refusal itself stays in the resolver where it belongs. Five
parametrised cases cover both columns.

## Measured

```text
mapped_identities              1
mapped_organizations           [bbbbbbbb-cccc-dddd-eeee-ffffffffffff]
roles_observed                 [org_owner]
membership_sources_observed    [org_owner_approved]
role_sources_observed          [membership_record]
role_mapping_passed            true
cookie_claim_can_override      false
email_domain_can_map_a_role    false
```

## One thing this gate did not build

There is **no write path for a real-organization membership** anywhere in
`src/`. Gate 132's bootstrap refuses any organization whose `org_type` is not
`demo`, and that refusal is the enforcement of the authorization it was built
under. `tests/test_isolation_routes.py` inserts a real-org membership row
directly to give the real half of the demo/real separation something to stand
on, and says so where it does it.

That is a gap by design today and will need a decision before a real
organization can have a member.
