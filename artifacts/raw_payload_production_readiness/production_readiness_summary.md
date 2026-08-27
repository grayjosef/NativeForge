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
| `body_store_implementation_available` | yes | s3_raw_payload_body_store_service.store_body importable and callable; the seam takes an injected client, so no SDK is required |
| `body_store_configured` | **no** | all five RAW_PAYLOAD_OBJECT_STORE_* settings hold real, non-blank, non-placeholder values - read by value, never by field existence, and no credential value is rendered |
| `secret_scan_available` | yes | raw_payload_secret_scan_service.scan_payload_for_secrets importable and callable |
| `promotion_gate_available` | yes | raw_payload_promotion_gate_service.evaluate_payload_promotion importable and callable |

4 of 5 present. `production_raw_payload_store_available` is derived from all four, never set beside them, so it cannot read true while one is missing.

## Why the body store is missing

There is no object-store client in the dependency set and none of the three required settings exists on the Settings model. Both are checked by importing and inspecting rather than by reading a flag - a flag saying a component exists is a claim about a claim.

## The migration

`alembic/versions/0028_nf_raw_source_payloads.py` creates `nf_raw_source_payloads` with **31 columns**, 5 indexes, 1 unique constraint and 7 check constraints.

It stores a content-addressed reference and the hashes needed to verify what it points at. It does not store response bodies: a 78 MB Grants.gov extract is not a database row.

## Next required actions

- configure the S3-compatible object store: set RAW_PAYLOAD_OBJECT_STORE_ENDPOINT / _BUCKET / _REGION / _ACCESS_KEY_ID / _SECRET_ACCESS_KEY to real values in the environment (never in the repo); placeholders do not count
- prove a round trip against the configured bucket in staging - settings being present is not the same as a write succeeding

