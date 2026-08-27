# Raw payload body store readiness

An S3-compatible write seam exists and is fully exercised by tests through an injected client. **No object store was contacted and none is configured.**

```text
body_store_implementation_available: true
body_store_configured: false
production_raw_payload_store_available: false
production_storage_live: false
live_fetch_performed: false
collectors_active: false
source_monitoring_active: false
live_source_coverage: false
```

## Two facts, kept apart

| Fact | State |
| --- | --- |
| body store implementation exists | yes |
| an environment configures it | **no** |

Gate 96 folded these together by requiring an installed SDK. With an injected-client seam the client arrives at call time, so that test could never have passed however correctly an operator configured their environment.

## Production components

| Component | Available |
| --- | --- |
| `metadata_table_available` | yes |
| `body_store_implementation_available` | yes |
| `body_store_configured` | **no** |
| `secret_scan_available` | yes |
| `promotion_gate_available` | yes |

4 of 5 present. `production_raw_payload_store_available` is derived from all of them and reads `False`.

## No dependency was added

The store writes through any object exposing `put_object` and keys objects at `raw_payloads/<hash[:2]>/<hash[2:4]>/<hash>.bin`. No SDK is imported, `uv.lock` is untouched, and every refusal path is exercised without a network, a credential or a vendor.

## Settings

| Env var | Required | Secret | Value present |
| --- | --- | --- | --- |
| `RAW_PAYLOAD_OBJECT_STORE_ENDPOINT` | yes | no | no |
| `RAW_PAYLOAD_OBJECT_STORE_BUCKET` | yes | no | no |
| `RAW_PAYLOAD_OBJECT_STORE_REGION` | yes | no | no |
| `RAW_PAYLOAD_OBJECT_STORE_ACCESS_KEY_ID` | yes | no | no |
| `RAW_PAYLOAD_OBJECT_STORE_SECRET_ACCESS_KEY` | yes | yes | no |
| `RAW_PAYLOAD_OBJECT_STORE_FORCE_PATH_STYLE` | no | no | no |

Presence only. No value is rendered here or anywhere downstream - not even masked, since a masked value still leaks its length. The secret key is a pydantic `SecretStr`, so an accidental repr prints `**********`.

A value that looks like a placeholder is not configuration: 20 known placeholder values are refused, including AWS's own documentation key.

