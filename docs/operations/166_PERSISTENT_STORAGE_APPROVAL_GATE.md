# Persistent Storage Approval Gate (Gate 09 / Block 23)

> **OWNER_APPROVED_MIGRATIONS=false** for this run.
> Migrations **not** applied. `validated_persistent` adapter **unavailable**.

## Owner approval request

Mayhem: please approve Alembic migration + object-storage path for
`nf_evidence_intake_records` before any `validated_persistent` adapter or
`upload_persistence_claimed=true`.

Until approval:

* `migration_applied=false`
* `upload_persistence_claimed=false`
* `customer_data_persistence_claimed=false`
* `production_storage_claimed=false`
* dry-run status: `blocked_pending_approval`

## Available adapters now

* `fixture_backed`
* `local_dev_only` (metadata placeholder files under `artifacts/local_dev_evidence_placeholders/`)
* `planned_external`

## Not available

* `validated_persistent`

## Approval checklist (before flipping claims)

- [ ] Owner sets `OWNER_APPROVED_MIGRATIONS=true` in instruction
- [ ] Review schema/object model in `161_EVIDENCE_UPLOAD_STORAGE_PROPOSAL.md`
- [ ] Dry-run `alembic` commands (not applied until review)
- [ ] Confirm no production/customer data mutation
- [ ] Rollback plan reviewed
- [ ] MIME/size/malware/retention/IAM requirements acknowledged
- [ ] Validation tests for persistent adapter pass
- [ ] Only then may `validated_persistent` become available

## Proposed migration commands (NOT RUN)

```bash
# After approval only:
# alembic revision --autogenerate -m "evidence_intake_persistence"
# alembic upgrade head   # only after dry-run review
# alembic downgrade -1   # rollback posture check in non-prod
```

## Related

* Proposal: `docs/operations/161_EVIDENCE_UPLOAD_STORAGE_PROPOSAL.md`
* Evidence intake contract: Gate 08 Block 21
