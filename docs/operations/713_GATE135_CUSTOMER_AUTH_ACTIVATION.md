# 713 — Gate 135: customer auth activation

## Did `customer_auth_live` become true?

**No.** Measured on the running backend after this gate:

```text
login_live            true
customer_auth_live    FALSE
blocked_reasons       ["auth_gate_not_satisfied:invite_binding_passed"]
```

One blocker, named. Gate 134 left two.

## What cleared: the owner decision

Mayhem authorized controlled dev customer-auth activation explicitly, scoped to
the demo organization. Gate 133D had already split "the demo login may be called
live" from "customer authentication is live for real Tribes"; this is the second
decision arriving.

`build_customer_auth_activation_decision` checks all three per call:

```text
organization    bbbbbbbb-cccc-dddd-eeee-ffffffffffff, and no other
refused         aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee, by name
provider        Google
environment     local | dev | test. production and unset refused.
revocation      NF_DEV_CUSTOMER_AUTH_ACTIVATION_REVOKED turns it off
grant           no environment variable turns it on
```

And it cannot reach further than it was given:

```text
approves_production_rollout            False, no branch returns True
approves_controlled_customer_pilot     False, no branch returns True
```

`NF_CUSTOMER_AUTH_ACTIVATION_APPROVAL` is still honoured. The recorded decision
is an additional route to `owner_approval`, not a replacement — a deployment
that sets the token gets what it always got, and the gate reports which of the
two answered in `owner_approval_source`.

The organization the decision is checked against is **derived**: the route reads
the single mapped organization out of the role-mapping evidence and offers that.
Nought or several, and no organization is offered.

## What remains: a person

`invite_binding_passed` requires a membership that came through a completed
invite. A completed invite requires somebody to accept it, and accepting means
authenticating.

The demo organization has one identity — the owner — whose membership is Gate
132's bootstrap. The owner cannot complete an invite to themselves: the
repository refuses it by name, and so does the database on PostgreSQL.

So the last blocker is **a second real person logging in**. Inventing one would
be faking a user, and it would also make the evidence worthless: the gate exists
to prove somebody else authorized a membership.

See `712` for the seam that was built so this can be completed, and
`715` for the exact four steps.

## Why `customer_auth_live` was not forced

It would have taken one line — passing `invite_binding_passed=True` to the
validation runner, which still accepts it as a parameter. That is precisely the
defect this campaign has found five times: a gate reading a value somebody
supplied rather than a fact somebody measured.

The gate is satisfiable. `tests/test_gate135_customer_auth_activation.py`
reaches `customer_auth_live: True` with every fact supplied, and turns it off
again by removing each one in turn. What is missing is not a branch — it is an
event.

## `verified_operational_binding` is still false

Unchanged since Gate 132, and for the same reason: Gate 113's contract refuses a
`verified_binding` on a demo organization, because a demo binding may not carry
a verifier. It is not in `REQUIRED_AUTH_GATES`, so it does not block
`customer_auth_live`; it is reported beside it.

## Production rollout and controlled pilot

Both false, both untouched, and neither is set by anything in this gate. The
authorization was explicit about that, and the activation gate now carries both
as reported constants with an invariant that fails if either is ever true —
so a future edit wiring one to `customer_auth_live` fails a test rather than
shipping.
