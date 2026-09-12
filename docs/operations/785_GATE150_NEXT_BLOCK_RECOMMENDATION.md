# 785 — Gate 150: the recommended next block

## Where Gates 146–150 finished

```text
internal_demo_beta         GO
controlled_customer_beta   LIMITED_GO
production_rollout         NO_GO
lanes moved by this block  0
```

Four boundary gates, every refusal now exact, and four approvals outstanding —
**none of which is technical**.

## The problem that decides the next block

Every remaining customer-beta blocker is an approval, a document, or a person
signing in:

```text
a real customer organization        nobody in this repository can create one
the second person signing in        the second person
the verified binding authorization  Mayhem, after a customer exists
the consent document                Mayhem writes it; each tenant agrees
the customer beta scope approval    Mayhem
```

Nothing further in engineering advances that block. Waiting for it leaves the
campaign idle on work only Mayhem and a second person can do, which is the worst
available use of the next five gates.

## Recommended: Gates 151–155, operational durability

```text
151  digest persistence
       delivery intents name a digest nobody kept. A digest that cannot be
       re-read cannot be audited after a missed deadline, and a missed
       deadline is the failure mode this product exists to prevent.

152  source terms review tooling
       171 sources need a human decision each. It is the long pole on
       source_monitoring_live, it is unblocked today, and it is the one piece
       of human work the campaign can make faster rather than wait on.

153  backup and restore proof
       a pilot customer's data needs a restore path that has actually been
       exercised, not one that exists. Before real data, not after.

154  operational runbook and on-call
       Gate 149 asked for a named support and rollback owner. Naming somebody
       without handing them a runbook makes them an addressee, not an owner.

155  the block close
```

## Why this order

151 first because it is the only item on the list that is a **correctness gap
in something already operational**. The tenant digest is live and its delivery
intents reference a digest that was never stored, so the audit trail has a hole
in it today — not after a pilot starts.

152 second because it is the longest-running human work and every week it is
not started is a week added to `source_monitoring_live`.

153 and 154 before any customer, deliberately. A restore path proved after real
data exists is a restore path proved too late, and the same is true of a
runbook.

## Why not the alternatives

```text
wait for the approvals      idle gates; the campaign stops producing
email delivery              gives a customer nobody can sign in a digest
                            nobody consented to receive
object storage              gives document bytes a home before anybody can
                            upload one
production hardening        production is NO_GO and would stay NO_GO
a second customer surface   there is not yet a first customer
```

## What runs in parallel, outside the gates

The 171 source terms reviews are human work that nothing blocks. Gate 152 builds
tooling for them; the reviews themselves can start before it lands and should.

## What would change this recommendation

A real customer organization appearing. If one exists, the customer identity
block becomes unblocked and Gates 151–155 should yield to finishing it — the
four approvals would then have something to apply to, and the pilot prerequisite
list would go from 1-of-9 satisfied to genuinely in progress.

Nothing else on the current board changes the ordering.
