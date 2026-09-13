# 791 — Gate 151: the digest persistence readiness delta

## What moved

One lane, and it is a new one.

```text
tenant_digest_persistence_live   (did not exist)  ->  true, controlled_dev_demo
```

## What did not move

Everything else.

```text
tenant_digest_operational        true   ->  true
email_delivery                   false  ->  false
source_monitoring_live           false  ->  false
object_store_configured          false  ->  false
customer_auth_live               false  ->  false
verified_operational_binding     false  ->  false
consent_boundary_documented      false  ->  false
customer_beta_scope_approved     false  ->  false
controlled_customer_pilot        false  ->  false
production_rollout               NO_GO  ->  NO_GO
production_digest_persistence    false, and never computed
```

This is the first gate in eleven to turn a lane true, and it is worth being
precise about how narrow the claim is. `tenant_digest_persistence_live` means: a
digest built in the demo organization survives a write, comes back by its id
with its hash intact, keeps its counts and its caveats, refuses a cross-org
read, and can be resolved by the delivery intent that names it.

It does not mean anything was sent, any source was called, any real tenant's
digest was stored, or that production persistence works.

## The seven conditions

Each derived from something that happened, not asserted:

```text
table_exists                        migration 0042 applied and inspectable
repository_round_trip               written and read back by id
payload_hash_stable                 stored sha256 == recomputed sha256
counts_preserved                    four counts came back agreeing
honesty_fields_preserved            human review, unverified deadlines and
                                    unknown reporting burden survived
cross_org_read_refused              same answer as a digest that does not exist
delivery_intent_references_a_persisted_digest
                                    the gap Gate 150 found, closed forward
```

Removing any one blocks the lane, and a parametrised test proves each of the
seven individually.

## What the verifier reports

```text
RESULT=PASS
tenant_digest_persistence_live=true
scope=controlled_dev_demo
payload_hash_verified=true
rendered_body_stored=false
recipient_stored=false
cross_org_read_refused=true
delivery_intent_linkage_resolves=true
delivery_intents_total=71
legacy_intents_without_a_persisted_digest=71
live_fixture_digest_records=0
real_organization_digest_rows=0
tenant_supplied_digest_rows=0
emails_sent=0
live_source_calls=0
object_store_calls=0
```

The fixture digest it creates is archived before it exits, so fixture
cleanliness finds zero live records — and the archived one stays readable by id,
which is the behaviour the lane exists to provide.

## The 71, reported not hidden

They still resolve to nothing, and this gate does not backfill them. The digests
cannot be reconstructed and manufacturing one would produce something that looks
like evidence and is not. The number is printed on every verifier run so it goes
down visibly as new intents are recorded against persisted digests.

## The system had already named this gap, by table name

Regenerating the demo payload cleared a blocked reason that had been sitting in
it:

```text
-  "no_table_declares_this_capability:nf_tenant_digest_records"
```

Two services already referred to the table that did not exist:

```text
customer_persistence_capability_service
    "tenant_digest_persistence": "nf_tenant_digest_records"

controlled_beta_readiness_decision_service
    a technical blocker reading "nf_tenant_digest_records does not exist"
```

So Gate 145's own technical-blocker list named this exact table, the capability
map pointed at it, and the demo operating shell carried the blocker every day.
The gap was machine-identified before Gate 150 described it in prose — and the
blocker cleared by itself the moment migration 0042 ran, without anything in
this gate touching those two services.

That is the good version of the declared-versus-derived pattern this campaign
usually finds the bad version of: a declaration that was correct, checkable, and
went green on its own when the underlying fact changed.

## Two defects, both mine, both before commit

**A dialect split.** DATE columns fed ISO strings: SQLite refuses, Postgres
coerces. Would have passed in one environment and failed in the other — the same
class as Gate 142's untyped column binding a UUID on one dialect and not the
other. This is the second time the campaign has hit it, which suggests checking
column types against the values a builder actually produces is worth doing at
migration-writing time rather than at first-insert time.

**A misleading constant.** `organization_id` in `CALLER_MAY_NOT_SET` said the
repository refuses the one thing it requires. Caught by a parametrised test
colliding on it.

## What Gate 152 needs from this

A replay has to be able to read what was said before it can attest to it. A
persisted digest with a verifiable hash is the first such record, which is why
digest persistence came first in the durability block rather than after the
evidence ledger.

The next gate should be able to assume: a digest exists, it is addressable by a
deterministic id, its payload hash proves a rendering came from it, and an
archived one is still readable.

## Next

Gate 152 — audit replay / evidence ledger.
