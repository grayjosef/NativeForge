# 757 — Gate 145: the controlled beta decision matrix

## The answer

```text
internal / demo beta        GO
controlled customer beta    LIMITED_GO
production rollout          NO_GO
```

## Three scopes, decided separately

They differ not in how much software works but in **who is on the other side**:

```text
internal_demo_beta        operators, the demo organization, fixture rows
controlled_customer_beta  a real person, a real organization, real data
production_rollout        everyone
```

A single "are we ready" answer would be useless. Everything the first needs is
built; the second needs two human decisions and a consent boundary nobody has
written; the third needs both of those and an owner saying yes.

## The five conflations the matrix exists to prevent

Each pair reads as the same thing to anyone who has not followed the gates, and
each is the difference between a true statement and a false one:

```text
email_delivery_readiness          is not  email_delivery
source_monitoring_preflight_ready is not  source_monitoring_live
document_metadata_operational     is not  document_body_storage_ready
customer_persistence_live         is not  customer_auth_live
the demo organization             is not  a customer organization
```

The decision service reports all five on every call, and a test asserts that
every readiness flag is true while every capability beside it is false.

More strongly: the four capability flags are **not parameters** of the decision
function. A caller cannot hand it a capability it did not measure, and a test
inspects the signature to prove it.

## Two scopes in genuine tension, and a defect it exposed

`INTERNAL_DEMO_MUST_BE_FALSE` includes `customer_auth_live` and
`verified_operational_binding` — a demo in which a real customer has signed in
is not a demo. But the controlled customer beta **requires** both to be true.

The first version appended the demo scope's blockers wholesale to the customer
scope, so the moment the customer beta's conditions were met it returned GO
carrying two blockers saying those same conditions must be false. The
`go_alongside_blockers` invariant caught it.

Only **condition failures** propagate now — the software either works or it does
not, for every scope — and demo-scope honesty violations stay in the demo scope.
The result is visible and correct:

```text
runtime today            internal GO      customer LIMITED_GO   production NO_GO
all approvals granted    internal LIMITED_GO   customer GO      production NO_GO
```

The internal demo dropping to LIMITED_GO once a real customer signs in is not a
bug. It is the matrix noticing that the thing stopped being a demo.

That defect would have shipped invisible: nothing in runtime reaches the
customer GO branch. The test that keeps it reachable is what found it — Gate
134F's lesson, earning its keep for the fifth time.

## Production is NO_GO, and not because something is missing

No branch in the decision service returns anything else for that scope.
Production is not the sum of the technical gates; it is those gates **and**
somebody saying yes. A service that could compute its way to GO would have
mistaken one for the other.

## What the matrix reports on every call

```text
by_scope              three decisions, each with conditions, blockers,
                      constraints and a one-sentence summary
conflations           the five above
unsafe_claims         seven sentences that would be false today, each paired
                      with a true one
human_approvals       eight, each with an owner and why no code moves it
technical_blockers    six, separate from the approvals, because an operator
                      needs to know whether to write code or to decide
```

## What it changed

Nothing. No lane's value moved, no capability was activated, no approval was
granted, no pilot was started. It answered a question.
