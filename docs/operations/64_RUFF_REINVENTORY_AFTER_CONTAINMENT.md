# Ruff Re-inventory After Containment

Block: NF Full-Suite Health / Lint-Debt Containment
Sprint: 041 (repaired sprint 044)

**Timestamp:** 20260814T201102Z
**Log:** `/tmp/nativeforge_ruff_inventory_20260814T201102Z.log`
**Archived:** `artifacts/repo_health/ruff_inventory_20260814T201102Z.log`
**Live post-I001-repair total:** 700

## Totals

- Before (sprint 010 baseline): **1285**
- After (inventory snapshot): **702**
- After (post sprint-043 I001 repair): **700**
- Fixed (delta vs baseline): **585**
- Footer: `Found 701 errors.`

## Rule codes after (live)

| Code | Count |
|------|------:|
| E501 | 696 |
| F841 | 3 |
| F811 | 1 |

## Top remaining files (live)

| Count | Path |
|------:|------|
| 50 | `tests/test_sprint73_active_source_activation_execution_plan_authoring_authorization_decision_packet.py` |
| 45 | `tests/test_sprint72_active_source_activation_execution_plan_authoring_authorization_request_packet.py` |
| 43 | `src/nativeforge/services/active_source_activation_review_packet_service.py` |
| 27 | `src/nativeforge/services/active_source_creation_execution_command_package_service.py` |
| 24 | `src/nativeforge/services/native_relevance_classification_label_explanation_service.py` |
| 23 | `src/nativeforge/services/active_source_activation_readiness_gate_service.py` |
| 22 | `src/nativeforge/services/active_source_creation_execution_plan_service.py` |
| 21 | `tests/test_sprint74_active_source_activation_execution_plan_authoring_review_packet.py` |
| 20 | `src/nativeforge/services/active_source_activation_execution_plan_authoring_authorization_decision_packet_service.py` |
| 19 | `src/nativeforge/services/active_source_activation_execution_plan_authoring_authorization_request_packet_service.py` |
| 16 | `src/nativeforge/services/sc_pilot_fixture_loader_service.py` |
| 14 | `src/nativeforge/services/active_source_activation_human_authorization_decision_packet_service.py` |
| 14 | `tests/test_sprint59_active_source_creation_execution_command_package.py` |
| 13 | `src/nativeforge/services/active_source_activation_execution_plan_review_packet_service.py` |
| 13 | `src/nativeforge/services/recognition_requirement_derivation_service.py` |
| 12 | `src/nativeforge/services/active_source_activation_execution_plan_authoring_review_packet_service.py` |
| 12 | `src/nativeforge/services/active_source_activation_human_authorization_request_packet_service.py` |
| 11 | `src/nativeforge/services/active_source_creation_execution_readiness_gate_service.py` |
| 11 | `src/nativeforge/services/active_source_runtime_migration_dry_run_command_package_service.py` |
| 11 | `src/nativeforge/services/recognition_tier_eligibility_gate_service.py` |
| 11 | `tests/test_sprint60_active_source_creation_execution_plan.py` |
| 10 | `src/nativeforge/services/active_source_post_runtime_verification_service.py` |
| 9 | `src/nativeforge/services/active_source_creation_execution_evidence_service.py` |
| 9 | `src/nativeforge/services/grant_eligibility_conditions_service.py` |
| 9 | `src/nativeforge/services/grants_gov_eligibility_parser_service.py` |

## Categories

- Fixed: I001 (cleared), F401 (cleared), E741 (cleared), large E501 slice
- Deferred: remaining E501 (unfixable tokens), F841 (3), F811 (1)
- Repo-wide autofix used?: **no**

