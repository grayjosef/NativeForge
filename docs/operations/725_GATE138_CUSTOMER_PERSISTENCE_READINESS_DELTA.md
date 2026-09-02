# 725 — Gate 138: customer persistence readiness delta

## The delta

```text
                                        before 138   after 138
customer_persistence_live (controlled)    false        TRUE
  scope                                   —            controlled_dev_demo
  measured by                             import checks a round trip
  lanes round-trip proved                 0            5
  rows written / archived / left live     0/0/0        5/5/0
  cross-org rows read                     —            0

customer_persistence_live (production)    false        false
production_persistence_ready              not reported reported, false
controlled_dev_persistence_available      not reported 6 lanes

customer_auth_live                        false        false
login_live                                true         true
verified_operational_binding              false        false
object_store_configured                   false        false
alembic head                              0039         0039  (no migration)
```

## `customer_auth_live` did not change, and could not have

This gate touched no auth gate. `customer_persistence_live` is reported
**beside** `customer_auth_live`, never inside it, and the invariant refuses the
claim outside the controlled scope:

```text
customer_persistence_live_outside_the_controlled_scope:<scope>
customer_persistence_live_without_a_proof
customer_persistence_live_without_a_proved_lane
```

The two words are otherwise a production claim nobody made.

## What was measured rather than asserted

The capability matrix reads the models file, the migrations and the import
table. It has never written a row and still says so:

```text
build_capability_matrix -> rows_written: 0, persisted: False
```

It answers *could this lane work*. A lane with all five components and a broken
INSERT would report the same thing. `customer_persistence_activation_service`
answers *does it*, by doing it — and that is where
`customer_persistence_live` now comes from.

## Four defects found while building this

**1. The read step was a count, not a proof.** `rows_read >= 1` passed against
a live database carrying archived rows from earlier runs — it read 15 for five
writes. It proved the table had rows, not that the write did anything. Now an
id-specific, organization-anchored read of the row this run wrote.

**2. The read ran after the archive.** Three lanes default to
`include_archived=False`, so asking after cleanup found nothing and the step
failed for rows that had round-tripped perfectly well. The invariant caught it;
the read now happens before the archive.

**3. Scaffolding rows were never cleaned up.** Four lanes hang off an award
they write themselves, and only the lane's own row was archived — a live count
found three awards and two requirements left behind. The invariant that should
have caught it compared *totals*, so five leftovers summed to "some were
archived" and passed. It is per-row now.

**4. Determinism made the live smoke un-re-runnable.** A fixed seed derived
fixed ids, so the second run collided with the first run's *archived* row on
the primary key and died on an IntegrityError. Determinism belongs to the
artifact, which builds and throws away its own database; a proof against a live
database has to be runnable twice. Fresh seed by default, fixed only when a
caller asks.

## And one the live database found

`created_by_identity_id` is a foreign key into `nf_identities`. The first live
run passed a synthetic identity and was refused. The throwaway SQLite database
had no such target table and had accepted it — so the proof passed where it did
not matter and failed where it did.

The accountable identity is read from `nf_org_memberships` now. The constraint
was right and so is what it forces.

## What consumes the new fields

```text
customer_persistence_capability_service
  operational                          unchanged: production. Still needs
                                       customer_auth_live.
  production_operational               the same thing, named
  controlled_dev_persistence_available NEW. Six lanes. Availability only -
                                       whether one round-trips is measured
                                       elsewhere, and this service still
                                       writes nothing.

org_scoped_customer_persistence_guard_service
  controlled_dev_fixture_write         NEW. Reports which kind of write was
                                       judged. It never relaxes the anchor:
                                       organization_id is still the only
                                       authority and a label still never
                                       substitutes.

customer_auth_activation_gate_service
  customer_persistence_live            NEW, from a supplied proof
  customer_persistence_scope           NEW
  production_persistence_ready         NEW, false
  object_store_configured              NEW, false
  awarded_operational_tracking         NEW, false
```

## Still false, and not touched

```text
production_persistence_ready   false
customer_auth_live             false   blocker: invite_binding_passed
verified_operational_binding   false   Gate 137's two-part owner decision
object_store_configured        false
awarded_operational_tracking   false   Gate 139's facts do not exist
tenant_digest_operational      false
source_monitoring_live         false
email_delivery                 false
production_rollout             false
controlled_customer_pilot      false
real organization touched      no
real customer data written     no
```

## Next

```text
1  a second real person completes an invite      -> customer_auth_live
2  an owner decision authorizing a real org      -> verified_operational_binding
3  those two together                            -> production persistence
4  routes for four repository-live lanes         -> customer-usable persistence
```

Item 4 is engineering and is the only one of the four this campaign can do
without a person.
