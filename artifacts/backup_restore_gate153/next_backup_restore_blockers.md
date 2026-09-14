# Gate 153 — what is still blocked after this gate

`operational_backup_restore_ready` is true for `controlled_dev_demo`.
That means this system can export its own operational state for one
organization,
load it into an isolated database, and still pass the Gate 152 replay.

It does not mean production is backed up. Nothing below moved.

## Still blocked, and by what

```text
a managed database instance   procurement. Unblocks the Gate 61/65
                              harness, which is still RESULT=SKIP.
backup automation             needs the instance first
point-in-time recovery        needs a provider that supports it
an executed provider restore  needs all three
```

None of those is engineering work, and none of them is what Gate 153
built. `scripts/verify_nativeforge_backup_restore.sh` measures them and
continues to return SKIP.

## Not applicable rather than blocked

```text
customer data backup    no customer data exists to back up
object store backup     no object store is configured
RPO / RTO in force      documented, enforced by nothing
```

## What must not be read into the lane

- The export is fixture data for one demo organization.
- The real organization is refused by name and was never read.
- No identity, redirect state or organization row is ever exported.
- The restore target is a temporary database, deleted by the verifier.
- Legacy gaps survive the round trip as legacy gaps. A restore that
  closed one would have invented a digest for an intent that never
  had one.

## The honest summary

The data path is proven and the infrastructure path is untouched. A
reader who takes `operational_backup_restore_ready=true` to mean the
product has backups has read it wrong, and the lane says so in four
places.
