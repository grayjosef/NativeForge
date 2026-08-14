# Remaining Unfixable E501 Inventory

Block: NF Full-Suite Health / Lint-Debt Containment
Sprint: 035

Total remaining E501: **696** across **118** files.

Ruff `--fix` reports **0** additional safe autofixes for E501 at this point.
Remainder is mostly long single-token strings / identifiers that exceed 88 chars.

## Top offenders (remaining)

| Count | Path |
|------:|------|
| 50 | `tests/test_sprint73_active_source_activation_execution_plan_authoring_authorization_decision_packet.py` |
| 45 | `tests/test_sprint72_active_source_activation_execution_plan_authoring_authorization_request_packet.py` |
| 42 | `src/nativeforge/services/active_source_activation_review_packet_service.py` |
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
| 11 | `tests/test_sprint60_active_source_creation_execution_plan.py` |
| 10 | `src/nativeforge/services/active_source_post_runtime_verification_service.py` |
| 10 | `src/nativeforge/services/recognition_tier_eligibility_gate_service.py` |
| 9 | `src/nativeforge/services/active_source_creation_execution_evidence_service.py` |
| 9 | `src/nativeforge/services/grant_eligibility_conditions_service.py` |
| 9 | `src/nativeforge/services/grants_gov_eligibility_parser_service.py` |
| 8 | `src/nativeforge/services/active_source_activation_command_package_service.py` |
| 8 | `src/nativeforge/services/eligibility_fit_assessment_dimension_evaluator_service.py` |
| 8 | `src/nativeforge/services/eligibility_fit_assessment_operator_guidance_service.py` |
| 8 | `tests/test_recognition_requirement_coverage_expansion.py` |
| 8 | `tests/test_sprint58_active_source_creation_execution_readiness_gate.py` |
| 8 | `tests/test_sprint71_active_source_activation_execution_plan_review_packet.py` |
| 7 | `src/nativeforge/services/active_source_activation_authorization_readiness_packet_service.py` |
| 6 | `tests/test_sprint56_active_source_human_approval_intake.py` |
| 6 | `tests/test_sprint61_active_source_creation_execution_evidence_packet.py` |
| 5 | `src/nativeforge/services/active_source_creation_execution_dry_run_service.py` |
| 5 | `src/nativeforge/services/active_source_runtime_migration_apply_execution_service.py` |
| 5 | `src/nativeforge/services/active_source_runtime_migration_post_apply_verification_service.py` |
| 5 | `src/nativeforge/services/eligibility_fit_assessment_evaluator_service.py` |
| 5 | `src/nativeforge/services/eligibility_fit_assessment_stage7_closeout_packet_service.py` |
| 5 | `src/nativeforge/services/native_relevance_classification_stage6_closeout_packet_service.py` |

## Containment stance

- Do not mass-wrap long domain token strings in packet services/tests without ownership.
- Prefer per-file `# noqa: E501` only when reviewed and intentional.
- Further E501 reduction belongs in a dedicated formatting/ownership block.
