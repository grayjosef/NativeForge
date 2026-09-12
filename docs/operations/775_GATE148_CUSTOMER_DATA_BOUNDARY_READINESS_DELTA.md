# 775 — Gate 148: the customer data boundary readiness delta

## What moved

No lane's value. No consent was created, no scope approved, no customer data
written, no row of any kind.

```text
consent_boundary_documented    false  ->  false
customer_beta_scope_approved   false  ->  false
customer_auth_live             false  ->  false
verified_operational_binding   false  ->  false
controlled_customer_pilot      false  ->  false
production_rollout             false  ->  false
```

## What changed

A boundary exists that did not exist before, and it exists **ahead of the thing
it guards** rather than behind it.

```text
before   consent was a named gap with no definition, no classes, no guard,
         and no lane in the cockpit
after    nine data classes, a consent record shape, a beta scope approval
         shape, a write guard, two cockpit lanes, a verifier and artifacts
```

## The finding that justified the gate

Every post-award repository gates a production write on exactly
`customer_auth_live` and `verified_operational_binding`. Both are identity
facts. Neither is consent.

Gates 146 and 147 are working to make both true. On the day they succeed, a
production customer write becomes permitted with nothing anywhere recording that
a tenant agreed to it. The boundary had to be built before those lanes turn,
which is the entire argument for this gate's position.

## The cockpit

```text
before   15 lanes, none of them consent
after    17 lanes
```

A reader could previously see `customer_auth` and `verified_operational_binding`
false and take those for the last two things in the way. They are two of four.
The two new lanes are `consent_and_data_boundary` and `customer_beta_scope`,
both false, both `REQUIRES_HUMAN_APPROVAL`, each carrying its blocker stack.

Both the verifier and the Gate 144 tests derive the lane count from `LANE_KEYS`,
so adding lanes broke neither.

## The verifier

```text
new    verify_nativeforge_customer_data_boundary.sh
       RESULT=PASS  consent_boundary_documented=false
                    customer_beta_scope_approved=false
                    customer_data_write_guard_ready=true
                    demo_fixture_writes_allowed=true
                    customer_data_writes_allowed=false
                    unknown_data_class=blocked
                    login/membership/invite/verbal implies consent = false
                    rows_written=0
```

`RESULT=PASS` is the boundary question. The two lanes stay false on their own
lines — the same shape Gates 146 and 147 use, for the same reason: a verifier
that goes red because a human has not done a human thing trains an operator to
ignore it.

## One defect found, in my own code

The classifier matched field names with `\b(email|address|recipient|...)\b`.
There is no word boundary before `email` in `recipient_email`, because `_` is a
word character — so the pattern matched **nothing at all** on every
underscore-separated field name in this codebase, which is all of them.

Every hint silently failed and every field came back `unknown`. Because
`unknown` is blocked, the guard was still safe: it refused everything. But it
was refusing for the wrong reason, and a guard that is right by accident stops
being right the moment anything changes.

Fixed by tokenising the field name and matching token sets. A token match is
exact, which also sidesteps the substring problem this campaign has hit
repeatedly: `subject` matches `provider_subject` and not `subject_line`.

## What stays allowed

The fixture lane is untouched. `test_demo_fixture_writes_are_still_allowed` is
one of the five node ids pinned in the coverage guard, because breaking that
lane would stop the demo working and it would be a strange way to fail.

## The distance, stated honestly

```text
1  a real customer organization has to exist       still the front of the queue
2  decide what is collected, retained, exported, deleted   a document
3  decide how a tenant agrees, and how they withdraw       a document
4  Mayhem approves the controlled customer beta scope
5  a consent record per organization, ten fields
```

Steps 2 and 3 are not engineering, and Gate 148 did not pretend to do them. It
built the boundary that will enforce them and reported their absence.

## Next

Gate 149 is digest persistence in the block plan — delivery intents name a
digest nobody kept, and a digest that cannot be re-read cannot be audited after
a missed deadline. Gate 150 then re-decides the controlled customer beta with
146–149 established.
