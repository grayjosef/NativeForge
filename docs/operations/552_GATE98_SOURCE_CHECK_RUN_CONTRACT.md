# 552 — Gate 98D: source check-run record contract

`src/nativeforge/services/source_check_run_contract_service.py`

The shape of the row a check writes when it finishes. It builds records; it never
performs a check and never writes to the database.

## Two gaps in nf_source_check_runs

Gate 98A read the table's 22 columns:

```text
id  organization_id  is_demo  source_registry_id  check_mode  check_status
started_at  completed_at  checked_for_period_start  checked_for_period_end
opportunities_seen_count  new_candidates_count  accepted_count
duplicate_count  rejected_count  review_items_created_count
error_code  error_message  operator_notes  result_summary_json
created_at  updated_at
```

**No link to evidence.** A run can record `opportunities_seen_count = 42` with
nothing pointing at the payloads that produced the 42. That is the same shape as
the 185/18 corpus split Gates 87–89 measured: a number with no retrievable thing
behind it. The contract carries `raw_payload_ids`, referencing
`nf_raw_source_payloads` rows, and a record that reports a successful run finding
opportunities with no payload behind them is warned —
`counts_reported_without_payload_evidence` — with an invariant that fails any
record where the warning was stripped.

**`error_message` is free text.** An HTTP client's exception text routinely
carries a presigned URL, an echoed `Authorization` header, or a query string with
a key in it. The column would store that verbatim, forever, in a table operators
read. The contract field is `error_message_redacted`.

## Redaction happens here, not upstream

The redaction runs inside `build_check_run_record` via Gate 95's scanner. There
is deliberately no `error_message_redacted` parameter, no `already_redacted`
flag, and no `skip_redaction` escape — a test asserts all three are absent from
the signature. A caller who redacted already loses nothing; a caller who forgot
is caught. A flag saying the message is clean is a claim about a claim.

### A leak this found in Gate 95

The first end-to-end run produced:

```text
in :  GET https://api.example.gov/v1/x?api_key=AKIA1234567890ABCDEF failed;
      sent Authorization: Bearer abcdefghijklmnopqrstuvwxyz012345
out:  GET https://api.example.gov/v1/x?api_key=AKIA1234567890ABCDEF failed;
      sent Authorization: Bearer [REDACTED]
```

The bearer token was redacted. The API key in the URL was not.

Gate 95's `key=value` pattern is anchored `^...$` with `MULTILINE`, so it only
ever matched a whole line. A URL sits mid-sentence, so it never matched — and
doc 549 had named this exact case ("an error can carry a presigned URL") without
anyone checking whether the scanner handled it.

Fixed at the source rather than in this contract, because the payload store has
the same exposure: a stored JSON body containing a URL with a key in it was
equally unredacted. Gate 95 gained `URL_QUERY_SECRET_PATTERNS` and a
`url_query_credential` finding kind, matching `[?&]key=value` for the existing
secret key names plus signature and token parameters.

Those extra names are scoped to URL query position on purpose. As a JSON field
name, `token` is usually a pagination cursor — Grants.gov returns one on every
page — and treating those as secrets would set `findings_blocked` on every
payload and stop promotion entirely. The distinction is the position, so the
pattern carries it. Verified against both directions: 8 credential-bearing
strings now redact, 6 benign ones (continuation tokens, Grants.gov and Federal
Register pagination URLs) still do not.

## References, never contents

`raw_payload_ids` holds sha256 ids. Anything that is not one is dropped and
counted, not kept on the chance it was useful. `PROHIBITED_FIELD_NAMES` lists 21
names — `body`, `response_body`, `headers`, `token`, `error_message` among them —
and an invariant rejects a record carrying any of them as a key, so a future edit
that adds one fails a test rather than turning this table into a second,
unscanned copy of the payload store.

## Counts we cannot read are not zero

An unreadable or negative count becomes `None`, reported as unknown. Coercing it
to 0 would turn "we do not know what this run saw" into "this run saw nothing",
which reads as a clean result.

## Constants held by invariants

```text
check_executed          false
fetch_performed         false
persisted               false
response_body_included  false
secret_values_included  false
```
