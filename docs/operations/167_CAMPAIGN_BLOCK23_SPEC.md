# Campaign Block 23 SPEC — Persistent Storage Approval Gate

## Objective

Advance evidence storage toward validated persistence readiness without applying
migrations unless `OWNER_APPROVED_MIGRATIONS=true`.

## This run

* `OWNER_APPROVED_MIGRATIONS=false`
* Adapters: fixture_backed, local_dev_only, planned_external
* `validated_persistent` unavailable
* All persistence claims remain false

## Deliverables

* `persistence_approval_gate_contract_service.py`
* `evidence_storage_adapter_service.py`
* `persistence_approval_assembler_service.py`
* Docs: `161` update + `166_PERSISTENT_STORAGE_APPROVAL_GATE.md`
* SC demo panel: `sc-demo-persistence-approval-gate`

## Forbidden claims

* Uploads durable / evidence persistently stored
* Customer data persistence / production storage
* Validated persistent adapter / migrations applied
