# 722 — Gate 137: customer auth readiness delta

## The delta

```text
                                       before 137    after 137
verified_operational_binding             false        false
  reported by /api/auth/session          NO           yes
  refused for the demo organization      NO           yes, by classification
  refused for aaaaaaaa-…                 NO           yes, by name
  requires an approval object            NO           yes
production_write_readiness               not reported reported, false

customer_auth_live                       false        false
customer_auth_live blockers                1            1
login_live                               true         true
alembic head                             0039         0039  (no migration)
```

Nothing about `customer_auth_live` moved, and nothing about it could have. This
gate built a path and refused to walk it.

## `customer_auth_live` is unchanged, and stays out of the loop

`verified_operational_binding` is **not** in `REQUIRED_AUTH_GATES` and was not
added.

```text
verified_operational_binding  needs  customer_auth_live
customer_auth_live            needs  17 gates, none of them this one
```

Adding it would close exactly the cycle Gate 134F spent a gate opening —
`customer_auth_live` needing something that needs `customer_auth_live` is
unsatisfiable, and every "not ready" claim above it becomes unfalsifiable.

What consumes it, correctly, is production writes:

```python
# award_requirements_repository_service
if production_write and not verified_operational_binding:
    blocked.append(
        "production_requirement_write_requires_a_verified_operational_binding"
    )
```

## The two are reported separately, on purpose

Gate 136 made `customer_auth_live` reachable for **one demo organization with
two real Google identities**. That is not production readiness, and the gate now
says so rather than leaving it to be inferred:

```text
customer_auth_live_scope           controlled_dev_demo_org_only
production_write_readiness         customer_auth_live AND
                                   verified_operational_binding
production_write_blockers          named, in their own list
```

The blockers are in a **separate** list, and the first version was not.
Putting a production-write blocker into `blocked_reasons` made a fully
satisfied gate report a blocker, which broke Gate 115's
`blocked_reasons == []` on the activated branch — and was right to. That list
has meant one thing since Gate 115: what stops `customer_auth_live`. A reason in
the wrong list is a reason about the wrong question.

## Five defects found while measuring

**1. The demo-org refusal was a label refusal.** `prepare_insert` took
`is_demo` as a parameter and read no organization row, so a verified binding
written onto the demo organization with `is_demo=False` produced
`production_verified_binding: True`, no blockers, no invariant failures, and a
row in an RLS partition matching nobody. Full account in `720`.

**2. No approval was required to bind the real organization.** Authorization is
role-based and checks no organization id. Only `customer_auth_live` being false
held it shut, and Gate 136 made that reachable. Full account in `721`.

**3. Duplicate bindings were not refused.** Two active `verified_binding` rows
for the same organization and label pair both wrote, and `get_active_binding` —
documented as returning *"the one live binding"* — took `.first()` off an
unordered query. Both are refused now, and an ambiguous read refuses to pick
rather than making a coin toss on somebody's behalf.

The second refusal was found by this gate's **artifact** measuring the first
one and disagreeing with the claim printed beside it: the "duplicate" attempt
used different labels, so it was not a duplicate and wrote. Two verified
bindings for one organization contradict each other whatever their labels say,
so verified bindings are now one per organization.

**4. `RESULT_FIELDS` was declared in Gate 120B and consumed by nothing.** A
declared list nothing checks is a list that drifts. Asserted against real
results now.

**5. The old workflow path was still open.** The survey named it and 137B did
not reach it: `verified_binding_workflow_service` calls `insert_binding`
directly and passes `is_demo=bool(principal["is_demo_principal"])`, so the new
preparation service closed the hole only for callers using the new entry point.

Closed at `insert_binding`, where every write path converges and where the
connection is — the same place the duplicate checks went, and for the same
reason: a refusal that needs a database belongs where the database is.
`prepare_insert` keeps its connection-free contract.

Measured through the *old* workflow, demo organization, principal insisting it
is not a demo principal:

```text
write_performed  False
rows written     0
blocked          repository:demo_fixture_cannot_be_a_verified_binding
                 repository:supplied_is_demo_disagrees_with_the_organization_row
```

## Two mistakes of mine, and what they cost

**The `is_demo` mismatch refusal was too broad.** The first version refused any
disagreement between the caller's `is_demo` and the row, for every binding
status. That broke three of Gate 120's tests — revocation, conflict marking, and
a tenant-admin demo approval — none of which are about partitions. A
`demo_fixture` row saying `is_demo=True` on a real organization is a fixture in
a real organization, which is what a fixture *is*.

Narrowed to `verified_binding`, which is the status where getting the partition
wrong writes an unrevokable claim. The disagreement is still reported for every
status, as
`is_demo_derived_from_the_organization_row`, so it stays visible without being
fatal.

**Requiring classification made a permitted branch unreachable.** Gate 120's
`test_the_operational_branch_is_reachable_with_auth_injected` builds a
bindings-only database with no `organizations` table, so a verified binding
could no longer be written at all and the test failed.

The fix was the fixture, not the check: the test now builds the organization row
the check reads, and two new tests cover the refusals — one against a database
with no organizations, one against a demo organization. An unreachable
permitted branch makes every refusal above it unfalsifiable, which is the
defect that file exists to catch.

Plus one in this gate's own code: the injectable authorized-organization set
was consulted for every id, so listing `aaaaaaaa-…` in it approved a real-org
binding and wrote the row. Caught by
`test_the_runtime_real_org_is_never_written_to`.

## Still false, and not touched

```text
production_rollout             false
controlled_customer_pilot      false
verified_operational_binding   false
customer_auth_live             false
customer_persistence_live      false
awarded_operational_tracking   false
tenant_digest_operational      false
source_monitoring_live         false
email_delivery                 false
object_store_configured        false
real organization touched      no
real customer data written     no
```

## Next

Two blockers remain for `verified_operational_binding`, in order, and neither
is code:

```text
1  customer_auth_live true      Gate 136's second-person invite event.
                                docs/operations/717 has the four steps and
                                the OAuth test-user prerequisite.
2  an owner decision            adding an organization to
                                AUTHORIZED_REAL_ORGANIZATION_IDS, plus an
                                approval object naming it. Both, not either.
```

And one engineering gap, named rather than fixed: binder authorization decides
by role and reads `org_claim_verified` off the principal, while Gate 132's
membership evidence and Gate 136's invite evidence both read real rows and
reach that decision not at all. The preparation service reports
`membership_source: not_consulted` rather than implying otherwise.
