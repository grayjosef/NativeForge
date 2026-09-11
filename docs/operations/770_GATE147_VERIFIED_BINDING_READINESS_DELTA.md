# 770 — Gate 147: the verified binding readiness delta

## What moved

Nothing. No lane's value changed, no approval was granted, no binding was
written, and the real organization has the same zero rows it had before.

```text
verified_operational_binding   false  ->  false
customer_auth_live             false  ->  false
controlled_customer_pilot      false  ->  false
production_rollout             false  ->  false
```

## What changed

What is *knowable* changed. Before this gate, the answer to "how far is the
verified binding from true?" required reading three modules that do not import
each other.

```text
before   one blocker reported:  owner_decision_absent
after    five reported, each with a kind and an owner, one of which never
         clears
```

## The cockpit

```text
before   summary   "Gate 137's two-part owner decision has not been made"
         blockers  ["owner_decision_absent"]
         owner     "the owner"

after    summary   five refusals stand, and any one is sufficient...
         blockers  five, including the one that never clears
         owner     "Mayhem, and only after a real customer organization exists"
```

The old wording was true and incomplete in exactly the way
`invite_binding_passed` was before Gate 146: it named one refusal, so a reader
took it to mean one decision away. The owner clause is the important half of the
correction — there is currently nothing for the owner to decide about.

## The verifiers

```text
new    verify_nativeforge_verified_binding_approval_boundary.sh
       RESULT=PASS  approval_boundary_ready=true
                    verified_operational_binding=false
                    blocker_count=5
                    real_organization_binding_rows=0
                    mutation_path_enabled=false
```

`RESULT=PASS` is the boundary question. The lane stays false on its own line, as
Gate 146's second-person verifier does. A verifier that went red because a human
has not yet done a human thing trains an operator to ignore it.

## The artifacts

```text
artifacts/verified_binding_gate147/
  verified_binding_survey.json
  verified_binding_approval_checklist.json
  verified_binding_dry_run_decision.json
  verified_binding_refusal_matrix.json
  verified_binding_cockpit_status.json
  verified_binding_activation_blockers.json
  next_verified_binding_human_action.md
```

They carry the boundary, not today's row counts. A committed artifact holding
live counts would churn on every regeneration and be wrong the moment anything
changed; the counts belong in the verifier, read at the moment somebody asks.

## Two defects found

**A near-duplicate blocker name, mine.** The checklist coined
`organization_not_in_the_authorized_real_org_list` beside the boundary service's
`organization_is_not_in_the_authorized_real_org_list`. The dry-run composite
unions both layers, so one refusal appeared twice and the blocker count read six
instead of five. Fixed by reusing Gate 137's constant; a test now asserts exactly
one name matches.

**An eligibility word in a cockpit that must not discuss eligibility.** The new
lane summary used "categorically ineligible", and Gate 144's guard scans for the
substring `eligib` to stop the cockpit reporting a Tribe's grant eligibility.
The guard is correct and the wording was careless — a cockpit forbidden from
discussing eligibility has no business carrying the vocabulary for an unrelated
subject. The wording changed; the guard did not.

That second one is worth noting precisely because it is *not* the usual
substring-versus-meaning false positive this campaign has hit sixteen times. The
previous sixteen were guards that were wrong. This one was a guard that was
right.

## The distance, stated honestly

```text
1  a real customer organization has to exist        nothing exists yet
2  the second-person event                          Gate 146, still absent
3  Mayhem authorizes that organization              a code change
4  an approval object is recorded                   five fields
5  a qualified verifier principal acts
```

The campaign has been describing this lane as needing an owner decision. Step 1
is the front of the queue and it is not a decision — it is a customer.

## Next

Gate 148: the consent and data boundary. Gate 142 named that gap and
deliberately did not fill it — nothing in this repository records that a tenant
asked for anything — and it is the third of the four approvals the controlled
customer beta needs.
