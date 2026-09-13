# Gate 151 — what digest persistence still does not do

`tenant_digest_persistence_live` is true for `controlled_dev_demo`.
That is a narrower claim than it sounds, and the narrowness is the
point.

## What it does not mean

```text
not  that any digest was sent            email_delivery is false
not  that any live source was called     source_monitoring_live false
not  that a real tenant's digest exists  no consent, no customer org
not  that production persistence works   never computed
```

## The 71 legacy intents

They still name digests that exist nowhere, and this gate does not
backfill them. The digests cannot be reconstructed: the snapshots they
were built from are not guaranteed unchanged, and manufacturing one
would produce a record that looks like evidence and is not.

What changed is that no *new* intent has to be in that position. The
linkage is measured on every call and can be enforced with
`require_persisted_digest=True`.

## What would make the enforcement unconditional

```text
1  every live intent resolves to a persisted digest
2  the legacy rows are archived or accepted as pre-table history
3  the flag default flips, in a change somebody reviews
```

Step 2 is a decision rather than work: those intents are not wrong,
they are older than the table.

## What stays false

```text
production_digest_persistence   false
email_delivery   false
source_monitoring_live   false
object_store_configured   false
customer_auth_live   false
verified_operational_binding   false
controlled_customer_pilot   false
production_rollout   false
```

## Next

Gate 152 — audit replay / evidence ledger. A persisted digest is the
first thing a replay has to be able to read, which is why it came
first.
