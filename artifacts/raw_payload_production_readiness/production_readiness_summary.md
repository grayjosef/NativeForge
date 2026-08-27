# Production raw payload storage readiness

A metadata table exists. A body store does not. **Adding a table is not the same as production storage being live.**

```text
metadata_table_available: true
body_store_configured: false
production_raw_payload_store_available: false
production_storage_live: false
live_fetch_performed: false
collectors_active: false
source_monitoring_active: false
live_source_coverage: false
```

## Components

| Component | Available | How it is established |
| --- | --- | --- |
| `metadata_table_available` | yes | alembic/versions/0028_nf_raw_source_payloads.py present, or the table found by SQLAlchemy inspection when a session is supplied |
| `body_store_configured` | **no** | importlib.util.find_spec for boto3/minio/google.cloud.storage/azure.storage.blob AND all three object-store settings on the Settings model |
| `secret_scan_available` | yes | raw_payload_secret_scan_service.scan_payload_for_secrets importable and callable |
| `promotion_gate_available` | yes | raw_payload_promotion_gate_service.evaluate_payload_promotion importable and callable |

3 of 4 present. `production_raw_payload_store_available` is derived from all four, never set beside them, so it cannot read true while one is missing.

## Why the body store is missing

There is no object-store client in the dependency set and none of the three required settings exists on the Settings model. Both are checked by importing and inspecting rather than by reading a flag - a flag saying a component exists is a claim about a claim.

## The migration

`alembic/versions/0028_nf_raw_source_payloads.py` creates `nf_raw_source_payloads` with **31 columns**, 5 indexes, 1 unique constraint and 7 check constraints.

It stores a content-addressed reference and the hashes needed to verify what it points at. It does not store response bodies: a 78 MB Grants.gov extract is not a database row.

## Next required actions

- choose an object store, add its client to the dependency set, and add endpoint/bucket/credential settings
- implement the body store against the four required guarantees: content-addressed, hash-preserving, secret-scan-clean before promotion, no body values in logs

