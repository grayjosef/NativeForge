# 780 — Gate 149: the pilot activation readiness delta

## What moved

No lane's value. No pilot activated, no approval recorded, no customer data
written, no row of any kind.

```text
controlled_customer_pilot      false  ->  false
production_rollout             NO_GO  ->  NO_GO
internal_demo_beta             GO     ->  GO
controlled_customer_beta       LIMITED_GO -> LIMITED_GO
customer_auth_live             false  ->  false
verified_operational_binding   false  ->  false
consent_boundary_documented    false  ->  false
customer_beta_scope_approved   false  ->  false
source_monitoring_live         false  ->  false
email_delivery                 false  ->  false
object_store_configured        false  ->  false
```

## What changed

The question "what has to be true before a pilot starts" now has one answer in
one place, with an owner per item and a refusal per bundle.

```text
before   four approvals named by Gate 145's matrix, three of them made exact
         by Gates 146-148, and no statement of what else a pilot needs
after    nine prerequisites, ten refused bundle keys, a dry-run boundary, four
         routes, a cockpit lane that names the missing mechanism, and artifacts
```

## The finding

`controlled_customer_pilot` is not a value that is false. It is not a value at
all: no table records a pilot approval, no environment flag exists, and no code
path assigns it. Every occurrence is a literal `False` written into a response.

This gate did not build the missing mechanism, and that is the decision rather
than an omission. A switch that exists before its prerequisites do is a switch
somebody flips early. Two tests hold the line: no file under `api/` may put
`True` on a line mentioning the flag, and no migration may create a
pilot-approval table. Both are pinned in the coverage guard.

## Two facts, kept apart

```text
activation_package_ready       true    the prerequisites are stated
controlled_customer_pilot      false   a pilot is running
```

The seventh instance of this distinction in the campaign. It is also why
`may_activate` is false on every branch of the boundary — including the one
where all nine prerequisites and the approval are satisfied — while
`prerequisites_would_permit` is true there. The first answers whether anything
could act on the decision. Nothing can.

## The cockpit

```text
before   summary   "not approved, and this gate does not approve it"
         blockers  ["pilot_not_approved"]
         owner     "the owner"

after    summary   eight prerequisites outstanding, one of which is a customer,
                   and there is nothing to approve with
         blockers  seven, including no_activation_mechanism_exists
         owner     "Mayhem, and only after a real customer organization exists"
```

The old wording invited a reader to go and get the approval. The correction is
the same one Gates 146 and 147 made to their own lanes: name the whole stack,
and say when the front of the queue is not a decision at all.

## The verifier

```text
new    verify_nativeforge_controlled_customer_pilot_activation_package.sh
       RESULT=PASS  activation_package_ready=true
                    controlled_customer_pilot=false
                    pilot_activation_allowed=false
                    activation_mechanism_exists=false
                    prerequisites_satisfied=1/9
                    unsafe_bundled_activations_refused=true
                    rows_written=0
```

It checks all ten bundle keys individually with everything else granted, and
fails if any one of them is permitted.

## No defects this gate

Three lint fixes (an unused import, an import-order slip, two long lines) and
nothing else. That is worth recording plainly rather than dressing up: the
previous four gates each turned up a real defect in their own new code, and this
one did not.

The tests that would have caught one were written the same way — the permitted
branch kept reachable, every prerequisite removed one at a time, every bundle
key exercised individually — so the absence of a finding is a result rather than
an untested guess.

## The distance, unchanged and stated again

```text
1  a real customer organization has to exist
2  the second-person invite event
3  the verified binding approval
4  the consent document, then a record
5  the customer beta scope approval
6  a support and rollback owner
7  an owner accepting the pilot scope limitations
8  a decision about how an activation is recorded
```

Item 1 has been the front of the queue for three gates. Nothing in Gates 146,
147, 148 or 149 could move it, and none of them pretended to.

## Next

Gate 150 re-decides the controlled customer beta with 146–149 established. The
honest expectation is that it stays LIMITED_GO with the same four approvals
outstanding — the block made the boundaries exact, not the lanes true — and a
Gate 150 that reported otherwise would be worth distrusting.
