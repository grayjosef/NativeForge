# 720 — Gate 137: the real-org binding path

## `verified_operational_binding` — current runtime value

```text
FALSE
```

Reported by `/api/auth/session` for the first time as of this gate, beside
`customer_auth_live` rather than inside it.

Not false because of a missing write path — that existed. False because
`verified_binding_workflow_service` derives it as

```python
auth_live and repository_write_performed
    and production_verified_binding and not demo_fixture
```

and `auth_live` is false. That was the only reason.

## Why the demo org cannot satisfy it — and the part that was not true

Everyone, including three previous gates, credited Gate 113 with refusing a
verified binding on a demo organization. Measured in 137A, it refused a
verified binding on a row the **caller labelled** demo:

```python
def prepare_insert(..., is_demo: bool = False, ...):
    demo_fixture = bool(is_demo or status == DEMO_STATUS)
```

`is_demo` was a parameter and nothing read `organizations.org_type`. So:

```text
insert_binding(organization_id=<the demo org>,
               binding_status="verified_binding",
               is_demo=False)
  rows_written                 1
  production_verified_binding  TRUE
  blocked_reasons              []
  invariant_failures           []
  stored row: is_demo=0, against a demo organization
```

And the row landed where the RLS predicate matches nobody:

```sql
organization_id = current_setting('app.current_org_id')::uuid
AND is_demo = current_setting('app.current_org_is_demo')::boolean
```

`is_demo=0` on a demo organization matches no demo session and no real one. A
row nothing can see is a row nothing can revoke.

Gate 132's membership bootstrap refused this parameter and said why —
*"a caller-supplied `is_demo` is a caller-supplied choice of which partition a
row lands in"*. Gate 120B's binding repository, eight gates later, took it. And
the workflow above it went one worse:

```python
is_demo=bool((principal or {}).get("is_demo_principal"))
```

A principal's self-description choosing an organization's partition.

**Now**: `is_demo` is derived from `organizations.org_type`, the demo
organization is refused by classification, and a caller who supplies an
`is_demo` that disagrees with the row gets
`supplied_is_demo_disagrees_with_the_organization_row` rather than a silent
override.

Gate 113's contract is not weakened. It is enforced against the organization
instead of against the caller's word for it.

## What a real-org verified binding requires

```text
organization_id           the anchor, uuid-shaped, the only authority
is_demo = false           DERIVED from organizations.org_type
binding_status            verified_binding
verified_by_identity_id   an nf_identities row
verified_at               both required, per migration 0029's CHECK
the organization listed   in AUTHORIZED_REAL_ORGANIZATION_IDS
an approval object        naming that organization, its scope, the
                          environment, who authorized it, and when
customer_auth_live        true, or the workflow refuses the write
```

Seven facts. Six are checkable now; the seventh is Gate 136's second-person
invite event.

## What was built

```text
verified_operational_binding_preparation_service
    derives is_demo, refuses the demo org by classification, records four
    provenance sources, and writes nothing

verified_operational_binding_activation_boundary_service
    the approval object, its two scopes, the empty authorized list, the
    by-name refusal, and one environment variable that can only revoke

write_verified_operational_binding
    prepare -> insert -> read back, with is_demo carried through derived.
    The entry point that does not offer the caller a choice about it.

tenant_customer_org_binding_repository_service
    a second active binding for the same labels is refused
    a second active VERIFIED binding for the organization is refused
      whatever its labels say
    an ambiguous read refuses to pick instead of taking .first() off an
      unordered query
    RESULT_FIELDS, declared in Gate 120B and consumed by nothing, is now
      asserted against real results

customer_auth_activation_gate_service
    verified_operational_binding and production_write_readiness reported,
    with their own blocker list
```

## What was not activated

```text
AUTHORIZED_REAL_ORGANIZATION_IDS = frozenset()
```

Empty, and empty is the decision. Mayhem's standing authorization refuses
`real org activation` and refuses binding to
`aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee` by name.

Activating one organization needs **both** a reviewed code change adding its id
to that constant *and* an approval object naming it. Either alone is refused.

## Was the real organization touched?

**No.**

```text
bindings written for aaaaaaaa-…              0
bindings written for the demo organization   0
runtime database opened by this gate         false
rows written outside the hermetic fixture    0
```

Every write in this gate went through an in-memory SQLite engine created for
the call and disposed at the end of it. The dev database is never addressed.

The path is proved against a fixture organization —
`cccccccc-dddd-eeee-ffff-000000000001`, `org_type = 'real'` — which is neither
the demo org nor the real one, so both refusals stay separately reachable and
the permitted branch is reachable too. Without that last part every refusal
above would be indistinguishable from a constant.

## Did `customer_auth_live` change?

No. Still false, still for one reason:

```text
blocker=invite_binding_passed
```

This gate did not touch it and could not have: `verified_operational_binding`
is **not** in `REQUIRED_AUTH_GATES`, and adding it would close the cycle Gate
134F spent a gate opening.

## Next gate

Binder authorization decides by **role** — `{platform_admin, tenant_admin}` —
and reads `org_claim_verified` off the principal. Gate 132's binding evidence
and Gate 136's invite evidence both read real rows, and neither is an input to
that decision.

So the strongest membership facts in the system do not reach the decision that
writes a verified binding. The preparation service reports
`membership_source: not_consulted` rather than implying otherwise, and closing
it is the next gate's work.
