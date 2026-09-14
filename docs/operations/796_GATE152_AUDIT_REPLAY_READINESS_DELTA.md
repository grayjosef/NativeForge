# 796 — Gate 152: the audit replay readiness delta

## What moved

One new lane, and one guard that started working.

```text
audit_replay_ready                (did not exist)  ->  true, controlled_dev_demo
require_persisted_digest=True     reported only    ->  enforced end to end
```

## What did not move

```text
tenant_digest_persistence_live   true   ->  true
tenant_digest_operational        true   ->  true
email_delivery                   false  ->  false
source_monitoring_live           false  ->  false
object_store_configured          false  ->  false
customer_auth_live               false  ->  false
verified_operational_binding     false  ->  false
consent_boundary_ready           false  ->  false
customer_beta_scope_approved     false  ->  false
controlled_customer_pilot        false  ->  false
production_rollout               NO_GO  ->  NO_GO
production_audit_ready           false, and never computed
```

No customer data was written, the real organization was counted and never
addressed, no mail was sent, no source called, no object store contacted.

## Gate 152 found and fixed a Gate 151 defect

**The persisted-digest delivery guard reported without enforcing.**

```text
record_delivery_intent       gates its write on decision["storage_allowed"]
prepare_delivery_intent      computes that from its OWN blocked list, and takes
                             no connection, so it cannot know about persistence
Gate 151                     appended digest_id_names_no_persisted_digest to
                             the caller's list instead
result                       the reason appeared; the row was written anyway
```

A blocker that gates nothing is a comment.

It shipped looking correct because Gate 151's verifier exercised
`digest_record_exists` directly rather than driving the write path end to end.

**It also briefly read green in this gate, for an unrelated reason.** The first
version of Gate 152's verifier passed a raw address where Gate 142 takes a
fingerprint, so the write was refused by the fingerprint check. The refusal
looked like the digest guard working. Fixing the fingerprint removed the real
blocker and the unpersisted-digest intent was accepted.

That is worth keeping as a lesson in its own right: **a green check with two
possible causes has only been half-tested.** The regression tests now use a
valid fingerprint on every enforcement path, so the digest linkage is the only
thing that can refuse.

**The second half of the defect** was in the reported field. The result spread
`**decision`, so `storage_allowed` could read `True` beside a blocker and
`rows_written: 0` — three fields, two of them right. A caller reading
`storage_allowed` to decide whether the write happened would have been wrong,
which is the same report-only defect one field further along. All three now
agree on every branch.

## Two more defects, both in this gate's own new code

**A false negative in the ledger.** A raw `sa.text()` read of a JSON column
returns a `str` on SQLite; only the typed `sa.Table` path deserializes it. The
ledger hashed the string while the stored hash was over the parsed dict, and
reported a sound digest as `missing_record`. In an audit ledger that is the
worst direction — telling an operator their evidence is broken when it is not.
Fixed by reading through the repository that owns the read.

**A manufactured dangling link.** The verifier referenced a random
`audit_event_id` that resolved to nothing, and the replay correctly reported
`missing_record`. A verifier should not invent a broken link and then credit
itself for detecting it. The happy path now writes a real
`digest_delivery_intent_recorded` event; the dangling case is a negative test in
the suite.

## What is new

```text
evidence_status_vocabulary_service   10 statuses, 3 of them proof, closed
audit_replay_service                 digest and intent replay, per-link status
evidence_ledger_service              one normalized entry per record
audit_replay_readiness_service       six conditions, one of them "we report gaps"
audit_replay_routes                  4 GET routes, 401 unauthenticated
verify_nativeforge_audit_replay_readiness.sh
artifacts/audit_replay_gate152/      8 deterministic files
```

## Legacy gaps

```text
count         reported on every verifier run
backfilled    false
status        legacy_gap, not missing_record
```

No fake evidence was backfilled. The digests cannot be reconstructed, and a
plausible fabrication is worse than an honest gap.

## What `audit_replay_ready` does not mean

```text
not  legal-grade or production audit
not  that any digest was delivered
not  that any tenant read anything
not  that the legacy gaps were closed
not  that any real tenant's evidence exists
```

## Next

Gate 153 — operational backup and restore readiness. A restore path proved
after real data exists is a restore path proved too late.
