# Gate 152 — what audit replay still cannot do

`audit_replay_ready` is true for `controlled_dev_demo`. That is a
narrower claim than it sounds.

## What it does not mean

```text
not  legal-grade or production audit    production_audit_ready false
not  that any digest was delivered      email_delivery false
not  that any tenant read anything      nothing records a view
not  that the legacy gaps were closed   they are reported, not filled
not  that real tenant evidence exists   no consent, no customer org
```

## The open gaps

```text
legacy delivery intents            reported as legacy_gap, never
                                   backfilled
no view or read event is recorded  out of scope, named so it is not
                                   mistaken for something that exists
award proof events not in ledger   a different subject; a later gate
                                   should build its own ledger
```

## What Gate 152 fixed in Gate 151

The persisted-digest delivery guard reported without enforcing. The
reason appeared in `blocked_reasons` and the row was written anyway,
because the write gates on a `storage_allowed` computed before the
digest linkage is known.

It shipped looking correct because Gate 151's verifier exercised the
linkage function directly rather than driving the write path, and it
briefly read green here because an invalid recipient fingerprint was
refusing for an unrelated reason.

`require_persisted_digest=True` is now enforced end to end, and
`storage_allowed`, `blocked_reasons` and `rows_written` all agree.

## What stays false

```text
production_audit_ready   false
email_delivery   false
source_monitoring_live   false
object_store_configured   false
customer_auth_live   false
verified_operational_binding   false
controlled_customer_pilot   false
production_rollout   false
```

## Next

Gate 153 — operational backup and restore readiness. A restore path
proved after real data exists is a restore path proved too late.
