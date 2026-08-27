# 538 — Gate 95E: payload promotion gate

**Raw payload evidence is required before parsed opportunity data can be trusted
as collected.** No collectors were activated, no live fetch occurred, no source
monitoring started. This does not change Baseline X live coverage.

## What it decides

Whether a stored payload may back a collected opportunity record. It returns a
decision and writes nothing — `promotion_performed` and `fetch_performed` are
both `False`, held by invariants. `apply_promotion` returns a **copy** carrying
the new status, so the caller does the writing and the original is unchanged.

## Nine requirements, all affirmative

```text
source_id present               retrieved_at present
response_body_hash present      raw_payload_ref present
secret_scan_clean               redaction_resolved
terms_cleared                   parser_status_ok
activation_permits_storage
```

Each is checked for an affirmative value, never for the absence of a negative.
`secret_scan_status: pending` fails — nobody has looked yet, and "not yet found
to be dirty" is not "clean". An invariant asserts satisfied and missing together
account for exactly these nine, so a requirement cannot be dropped silently.

## The promotion matrix

Eleven scenarios, one promotes:

```text
clean fixture payload          yes    evidence_ready
secret scan pending            no     quarantine
secret findings                no     quarantine
redaction pending              no     quarantine
redaction failed               no     quarantine
terms review required          no     quarantine
human review only              no     quarantine    human review: yes
terms unknown                  no     quarantine
parse failed                   no     quarantine
parser unavailable             no     quarantine
live payload, no preflight     no     quarantine
```

Every row in the committed artifact is produced by **calling the real gate**,
not by hand-writing a table. A hand-written matrix drifts from the code it
claims to describe; this one cannot, and a test asserts exactly one scenario
promotes.

## Human review quarantines; it does not reject

`HUMAN_REVIEW_ONLY` terms produce `human_review_required: True` and
`promotion_status: quarantine` — **not** `rejected`. The payload is not bad; it
is not machine-promotable. Rejecting it would lose it, and losing evidence is
the thing this whole lane exists to stop. An invariant fails any decision that
rejects a human-review payload.

## Terms unknown blocks

An unstated `terms_status` resolves to `UNKNOWN`, which is in the blocking set.
This surfaced during development: a payload stored without terms did not
promote, which looked like a bug and was the deny-by-default rule working. A
payload whose terms nobody has recorded is not a payload we know we may use.

## Activation is consulted, not assumed

The gate takes a preflight **result**, not a boolean. A live payload with no
preflight is blocked with `activation_preflight_absent`, because the absence of
a check is not a check that passed — the Gate 93D rule one layer down. An
invariant fails any decision promoting a live payload without one.

A **fixture** payload needs no activation: nothing was contacted. Requiring one
would force tests to assert a collector is live in order to build evidence,
which is the inversion this campaign keeps having to undo.
