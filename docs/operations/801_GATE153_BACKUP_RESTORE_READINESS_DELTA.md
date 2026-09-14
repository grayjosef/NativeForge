# 801 — Gate 153: the readiness delta

## What changed

```text
operational_backup_restore_ready            (new lane)  ->  true, controlled_dev_demo
```

## What did not change

```text
production_backup_ready         false  ->  false   (no branch computes it)
customer_auth_live              false  ->  false
verified_operational_binding    false  ->  false
source_monitoring_live          false  ->  false
email_delivery                  false  ->  false
object_store_configured         false  ->  false
controlled_customer_pilot       not activated, no mechanism created
audit_replay_ready              true   ->  true    (Gate 152, still true)
tenant_digest_persistence_live  true   ->  true    (Gate 151, still true)
```

`scripts/verify_nativeforge_backup_restore.sh` still returns `RESULT=SKIP`. It
was run after this gate to confirm it.

## The lane's eight conditions

```text
manifest_classified_by_meaning             every table has a reason a person
                                           wrote; the name matcher is a hint
export_scoped_to_one_organization          org-partitioned, real org refused by
                                           name, non-fixture rows counted
export_carries_a_hash_per_table            sha256 over sorted serialised rows
restore_into_isolated_target_works         every exported row, restored
restore_into_source_refused                RUN, not asserted
restore_into_live_refused                  RUN, not asserted
restored_state_passes_the_gate_152_replay  9/9 checks
legacy_gaps_preserved                      the count is unchanged
```

Two of the eight are refusals, and both are exercised. A permitted branch
nobody can reach makes a refusal unfalsifiable.

One of the eight is a preserved gap. A restore that closed one would score
better on the replay and be worthless.

## What `operational_backup_restore_ready=true` means

This system can export its own controlled dev/demo operational state for one
organization, load it into a separate migrated database, and have the Gate 152
replay give identical answers on both sides.

## What it does not mean

- **Not** that production is backed up. There is no managed instance, no backup
  automation, no PITR, and no provider restore has ever been executed.
- **Not** that customer data is backed up. None exists.
- **Not** that object storage is backed up. None is configured.
- **Not** that an RPO or RTO is enforced by anything. Both are documented in
  doc 400 and enforced by nothing.
- **Not** that a real organization was exported, restored, or read. It is
  refused by name in three services.

A reader who takes this lane to mean the product has backups has read it wrong,
and the lane says so in `what_this_does_not_mean`, in the verifier header, in
the artifact `next_backup_restore_blockers.md`, and in doc 798.

## Exact blockers remaining

```text
a managed database instance   procurement, not engineering. Unblocks the Gate
                              61/65 harness, which is the production lane.
backup automation             needs the instance first
point-in-time recovery        needs a provider that supports it
an executed provider restore  needs all three
```

None of those is what this gate built, and none of them moved.

## The naming collision this gate caused and then fixed

The first draft of the lane was written to
`src/nativeforge/services/backup_restore_readiness_service.py`. That file
already existed: it is **Gate 65's production readiness module**, 320 lines, and
it shares `SCHEMA_VERSION = "nf_backup_restore_readiness_v1"` and the function
name `build_backup_restore_readiness`. The overwrite was total and silent — the
Gate 65 verifier still returned SKIP afterwards, because its SKIP path never
reaches the code that had been replaced.

It was caught by `git status` showing the file as modified rather than new.

Two lanes that answer opposite questions had collided in one filename, which is
precisely the confusion this gate exists to prevent, committed in the
filesystem instead of in prose. The Gate 65 file is restored untouched and the
Gate 153 lane now has names that cannot be mistaken for it:

```text
Gate 65    backup_restore_readiness_service.py
           nf_backup_restore_readiness_v1
           build_backup_restore_readiness
           result key: "ready"

Gate 153   operational_backup_restore_readiness_service.py
           nf_operational_backup_restore_readiness_v1
           build_operational_restore_readiness
           result key: "operational_backup_restore_ready"
```

## Unchanged campaign blockers

Every customer-beta blocker from Gates 146–150 is still human and still
outstanding:

```text
a real customer organization must exist       nobody has created one
a named customer must sign in as themselves   nobody has
a signed operational binding approval         not signed
a controlled pilot activation approval        not granted
```

Gate 153 touched none of them, and could not have: operational durability is
the part of this system that is not waiting on a person.

## Files

```text
src/nativeforge/services/operational_backup_manifest_service.py
src/nativeforge/services/operational_backup_export_service.py
src/nativeforge/services/operational_restore_service.py
src/nativeforge/services/operational_restore_verification_service.py
src/nativeforge/services/operational_backup_restore_readiness_service.py
src/nativeforge/services/backup_restore_artifact_gate153_service.py
src/nativeforge/api/operational_backup_routes.py
scripts/verify_nativeforge_backup_restore_readiness.sh
tests/test_gate153_backup_restore_readiness.py
artifacts/backup_restore_gate153/  (8 files)
docs/operations/797..801
```

No migration. Head stays at **0042**.
