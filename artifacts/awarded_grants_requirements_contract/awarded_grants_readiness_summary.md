# Awarded Grants requirements tracking

A contract over labelled demo fixtures. No award package was read, nothing was fetched, and no compliance calendar is running for anybody.

## What exists

```text
awarded_grant_record_contract_available        True
award_transition_contract_available            True
requirement_model_available                    True
requirements_calendar_available                True
proof_audit_contract_available                 True
projected_vs_active_boundary_available         True
demo_fixture_available                         True
ready_for_demo_contract                        True
```

## What does not

An operational compliance tracker promises that a missed deadline will be caught. Nothing below can make that promise yet.

```text
ready_for_operational_awarded_tracking         False
ui_available                                   False
customer_persistence_live                      False
document_storage_live                          False
requirement_extraction_live                    False
live_source_collection_available               False
source_monitoring_live                         False
source_coverage_claimed                        False
```

## Nothing here is invented

```text
requirements_fabricated                        False
deadlines_fabricated                           False
proof_fabricated                               False
live_fetch_performed                           False
```

A projected burden stays projected, an unreadable document produces no verified requirement, an unknown due date stays unknown and visible, and proof of submission exists only where a caller supplied it or a demo fixture says so on its face.

## Next

1. **verify_a_real_tenant_customer_org_binding** — Gate 109 built the binding contract and Gate 110 decided its store: a new identity binding table anchored to organization_id, the column every row-level security policy enforces on. No verified non-demo binding exists yet, and the migration is not safe to apply until customer auth can supply a verifier
1. **persist_awarded_records_and_requirements** — nothing survives a request today, so a compliance calendar cannot be re-read after a missed deadline
1. **build_the_awarded_grants_surface** — the workspace is mandatory in the tenant beta contract and no UI exists for it
1. **attach_document_storage_under_the_existing_gates** — award packages have to live somewhere before requirements can be extracted from them
1. **wire_requirement_extraction_to_award_documents** — extraction exists for notices; award packages are a different corpus and nothing reads them
