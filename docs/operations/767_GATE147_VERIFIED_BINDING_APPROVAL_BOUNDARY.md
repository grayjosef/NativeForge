# 767 — Gate 147: the verified binding approval boundary

## The answer

```text
verified_operational_binding   false
approval_boundary_ready        true
blocker_count                  5
mutation_path_enabled          false
real organization binding rows 0
```

Two different questions, reported separately and never collapsed:

```text
approval_boundary_ready        the boundary evaluates and refuses correctly
verified_operational_binding   somebody actually satisfied it
```

This is the same distinction Gate 146 drew for `customer_auth_live` and Gate 145
named five times over. It is the sixth and seventh instance, and the pattern is
now the campaign's most reliable defect class: a readiness fact and the
capability beside it read as the same thing to anyone who has not followed the
gates.

## The five refusals

Any one of them alone is sufficient. All five stand today.

```text
demo_organization_is_never_a_verified_operational_binding
    kind    never clears
    owner   nobody

organization_is_the_explicitly_refused_real_org
    kind    never clears without a reviewed code change
    owner   Mayhem

organization_is_not_in_the_authorized_real_org_list
    kind    reviewed code change
    owner   Mayhem

no_approval_object_supplied
    kind    recorded decision
    owner   Mayhem

production_verified_binding_requires_live_customer_auth
    kind    an event
    owner   the second person, then the operator
```

Plus two more that depend on state rather than approval:
`more_than_one_active_binding_for_this_organization` and
`active_binding_is_ambiguous`, both resolved by a person.

## Three layers, gathered

Each refusal was already correct where it lived, and none of the three layers
could see the other two:

```text
the activation boundary   the authorized list, the approval object, the two
                          organization refusals, the environment scope
the workflow service      production_verified_binding_requires_live_customer_auth
the repository            duplicate and ambiguous active bindings
```

Nothing before this gate could say how far the lane was from true. The
checklist asks all three so no reader has to know there are three.

## What Gate 147 did not do

It did not weaken the boundary, and Gate 137's
`build_real_org_binding_activation_decision` is untouched. The dry-run composite
is additive: it takes no connection, imports no repository, and returns
`mutation_performed: false` and `rows_written: 0` on every branch including the
permitted one.

## The permitted branch is reachable, and writes nothing

```text
a fixture organization that is neither the demo org nor the real one
an approval object with all five fields and a covering scope
that organization in the injected authorized set
an authenticated platform_admin with verified-org status
customer_auth_live true
no active binding
  -> may_attempt_binding  true
  -> rows_written         0
```

Nothing in runtime reaches it. A test does, because an unreachable permitted
branch makes every refusal above it unfalsifiable — Gate 134F's lesson, earning
its keep again.

## One defect this gate introduced and caught

The checklist first coined `organization_not_in_the_authorized_real_org_list`
beside the boundary service's existing
`organization_is_not_in_the_authorized_real_org_list`. The dry-run composite
unions both layers' blockers, so the same refusal appeared twice under two
names and an operator counting blockers would have found six problems where
five exist. The checklist now reuses Gate 137's constant, and a test asserts
exactly one name matches `authorized_real_org_list`.

## One wording defect in the cockpit, corrected

The cockpit lane read:

```text
summary   "Gate 137's two-part owner decision has not been made"
blockers  ["owner_decision_absent"]
```

True, and incomplete in exactly the way `invite_binding_passed` was before Gate
146. A reader took it to mean one decision would move the lane. It would not:
even with the owner's decision there is no organization it could apply to, the
demo org being refused categorically and the real org by name. The lane now
carries all five.

## What the routes do

```text
GET  .../verified-binding/readiness    the lane, the classification, the counts
GET  .../verified-binding/blockers     each refusal with its owner and kind
GET  .../verified-binding/checklist    every field
POST .../verified-binding/dry-run-decision
```

The POST is the only non-GET and it is a decision, not an activation: it
evaluates a hypothetical approval so an operator can ask whether one would be
enough without recording it. It records nothing. The principal is taken from the
session context and never from the body — a caller naming their own role would
be choosing their own authority, and a test proves a supplied principal is
ignored.

## What stays false

```text
verified_operational_binding   false
customer_auth_live             false
controlled_customer_pilot      false
production_rollout             false
```

## Next

`768` on why demo proof is not production proof, `769` on the real-org approval
requirements, `770` on the delta.
