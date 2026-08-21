# Campaign Block 25 SPEC — Local/Dev Persistent Storage

## Objective

Apply Alembic `0022` in local/dev and validate `validated_persistent` adapter.

## Approval lane

- OWNER_APPROVED_MIGRATIONS=true
- APPROVED_ENVIRONMENT=local_dev_only
- No production/customer data mutation

## Deliverables

- Approval resolver
- Migration 0022 + model `NfEvidenceIntakeRecord`
- Validated persistent adapter (CRUD + review + archive + isolation)
- Docs 172
- SC demo panel updates
