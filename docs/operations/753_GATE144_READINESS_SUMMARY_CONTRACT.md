# 753 — Gate 144: the readiness summary contract

## Seven statuses, because "not ready" hides six situations

```text
operational               it works now, in controlled_dev_demo
readiness_only            the code is proved; the capability is not activated
preview_only              it produces something, and delivers nothing
blocked                   something specific stops it, and it is named
not_configured            settings are absent
requires_human_approval   a person has to decide, and no code can
production_false          deliberately false, and this gate cannot change it
```

Each has a different owner and a different fix. Collapsing them into
"ready / not ready" would tell an operator nothing about what to do.

## Every lane carries the same shape

```text
lane           the key, which is the contract
status         one of the seven
value          the boolean the rest of the system uses
scope          controlled_dev_demo, or null
summary        one sentence a person can act on
evidence       what this summary may conclude unaided
blockers       named, never counted
owner          who can move it
usable_today   status is operational or preview_only
```

## `LANE_EVIDENCE` is the load-bearing field

```text
self_evidencing             the lane's own service establishes it with nothing
                            supplied
needs_a_route_smoke         the service takes an injectable proof, so a summary
                            cannot conclude it alone
needs_a_database_round_trip same
```

Several readiness services take injectable proofs precisely so their permitted
branches stay reachable — Gate 140's digest needs a route smoke, Gate 141's body
storage needs an adapter proof. A summary that supplied those itself would be
reporting `true` for a lane whose evidence it invented.

So the summary takes seven parameters, one per lane that needs outside evidence,
and a caller that measured nothing gets `readiness_only` rather than a guess.

## The invariants

```text
lane_missing:<key>                       all 15 must be present
lane_status_not_recognised               only the seven
lane_true_alongside_blockers             a true lane has no blockers
lane_false_with_no_blocker               a false lane always says why
operational_without_a_value              status and value agree
operational_outside_the_scope            operational means controlled_dev_demo

a_cockpit_reported_a_forbidden_lane_true  the load-bearing one
a_forbidden_lane_was_marked_operational   the same rule, on status
```

`NEVER_TRUE_LANES` is the set no cockpit may report true whatever it is handed:

```text
email_delivery  source_monitoring  object_storage  customer_auth
verified_operational_binding  controlled_customer_pilot  production_rollout
```

A test forges each one true and asserts the invariant catches it.

## Two substring-versus-meaning defects, found and fixed in this gate

Both were mine, and both are the fourteenth and fifteenth instances of the same
family this campaign keeps finding.

```text
page_names_a_tribe read the page's own SOURCE, comments included - and the
page's docstring says "No Tribe name, no grant, no eligibility, no deadline
appears here". The check reported true for a file whose comment explains that
it does not. Comments are now stripped before the scan.

test_the_summary_names_no_customer_grant_or_deadline serialised the whole
summary and searched for "eligib" and "deadline" - and found them in
"eligibility_reported": false and "deadlines_reported": false, the fields whose
entire purpose is to state that the summary reports neither. It now scans
string VALUES, because a field name is the guarantee and not the leak.
```

The fix is the same as every other time: look at the thing, not at text that
mentions it.

## What the summary never reports

```text
production_rollout             false
controlled_customer_pilot      false
customer_auth_live             false
source_monitoring_live         false
email_delivery                 false
object_store_configured        false
verified_operational_binding   false
live_source_calls              0
emails_sent                    0
object_store_calls             0
collectors_activated           0
real_customer_data_written     false
real_organization_touched      false
customer_names_reported        false
eligibility_reported           false
deadlines_reported             false
```

None of those has a branch that sets it.
