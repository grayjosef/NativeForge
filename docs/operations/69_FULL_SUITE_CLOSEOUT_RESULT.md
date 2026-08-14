# Full-Suite Closeout Result

Block: NF Full-Suite Health / Lint-Debt Containment  
Sprint: 047

**Executed:** yes  
**Timestamp:** 20260814T201102Z  
**Log:** `/tmp/nativeforge_full_pytest_20260814T201102Z.log`  
**Archived:** `artifacts/repo_health/full_pytest_20260814T201102Z.log`

## Result

- passed: **5463**
- skipped: **13**
- failed: **46**
- duration: **1384.38s** (~23m)
- EXIT: 1 (expected while suite-debt remains)

## Comparison to baseline (sprint 001)

| Metric | Baseline | Closeout |
|--------|----------|----------|
| passed | 5463 | 5463 |
| skipped | 13 | 13 |
| failed | 46 | 46 |

Lint containment did **not** change full-suite pass/fail totals.

## Failure theme counts (closeout)

- activation_readiness: 15
- alembic_head_0019_expectation: 12
- active_source_runtime: 9
- recognition_corpus: 6
- other: 4

## Failure list

- `tests/test_recognition_requirement_coverage_expansion.py::test_unknown_count_drops_ac1`
- `tests/test_sprint197_eligibility_fit_assessment_dimension_vocabulary.py::test_five_fit_dimensions`
- `tests/test_sprint20_discovery_engine_closeout.py::test_alembic_migrations_unique_revisions_and_expected_head`
- `tests/test_sprint222_matching_readiness_readiness_evaluator.py::test_incomplete_profile_blocked_readiness`
- `tests/test_sprint345_nf15_corrected_corpus.py::test_reingest_fixes_placeholder_grants`
- `tests/test_sprint345_nf15_corrected_corpus.py::test_corrected_corpus_no_tribal_federal_irrelevant`
- `tests/test_sprint348_nf15_closeout.py::test_nf15_gate_and_closeout - n...`
- `tests/test_sprint355_nf16_no_proxy_closeout.py::test_nf16_corpus_zero_proxy`
- `tests/test_sprint355_nf16_no_proxy_closeout.py::test_nf16_gate_and_closeout`
- `tests/test_sprint47_active_source_local_migration_verification.py::test_table_exists_after_upgrade_and_gone_after_downgrade`
- `tests/test_sprint47_active_source_local_migration_verification.py::test_full_artifact_with_isolated_proof_passes`
- `tests/test_sprint47_active_source_local_migration_verification.py::test_downgrade_does_not_drop_unrelated_tables`
- `tests/test_sprint53_active_source_runtime_migration_post_apply_verification.py::test_no_new_alembic_revision_file_added_for_sprint_53_chain`
- `tests/test_sprint54_active_source_empty_state_read_model.py::test_no_new_alembic_revision_beyond_0019`
- `tests/test_sprint55_active_source_creation_request.py::test_no_new_alembic_revision_beyond_0019`
- `tests/test_sprint56_active_source_human_approval_intake.py::test_no_new_alembic_revision_beyond_0019`
- `tests/test_sprint57_active_source_creation_execution_dry_run.py::test_no_new_alembic_revision_beyond_0019`
- `tests/test_sprint58_active_source_creation_execution_readiness_gate.py::test_no_new_alembic_revision_beyond_0019`
- `tests/test_sprint59_active_source_creation_execution_command_package.py::test_no_new_alembic_revision_beyond_0019`
- `tests/test_sprint60_active_source_creation_execution_plan.py::test_no_new_alembic_revision_beyond_0019`
- `tests/test_sprint61_active_source_creation_execution_evidence_packet.py::test_no_new_alembic_revision_beyond_0019`
- `tests/test_sprint62_runtime_active_source_creation_execution_evidence.py::test_missing_target_table_blocks_before_row_creation`
- `tests/test_sprint62_runtime_active_source_creation_execution_evidence.py::test_duplicate_source_blocks_before_sprint_61_execution`
- `tests/test_sprint62_runtime_active_source_creation_execution_evidence.py::test_valid_controlled_runtime_path_creates_exactly_one_row`
- `tests/test_sprint62_runtime_active_source_creation_execution_evidence.py::test_count_delta_equals_one_and_row_id_recorded`
- `tests/test_sprint62_runtime_active_source_creation_execution_evidence.py::test_created_row_reloads_matches_payload_has_rollback_activation_pending`
- `tests/test_sprint62_runtime_active_source_creation_execution_evidence.py::test_no_new_alembic_revision_beyond_0019`
- `tests/test_sprint62_runtime_active_source_creation_execution_evidence.py::test_sprint_61_packet_embedded_on_success`
- `tests/test_sprint64_active_source_activation_readiness_gate.py::test_valid_post_runtime_yields_blocked_requires_activation_review_artifacts`
- `tests/test_sprint64_active_source_activation_readiness_gate.py::test_gate_includes_required_future_activation_review_artifacts`
- `tests/test_sprint64_active_source_activation_readiness_gate.py::test_gate_includes_review_requirement_sections`
- `tests/test_sprint64_active_source_activation_readiness_gate.py::test_gate_does_not_write_db`
- `tests/test_sprint64_active_source_activation_readiness_gate.py::test_gate_stateless_counts_remain_zero`
- `tests/test_sprint64_active_source_activation_readiness_gate.py::test_no_new_alembic_revision_beyond_0019`
- `tests/test_sprint64_active_source_activation_readiness_gate.py::test_invalid_optional_runtime_evidence_blocks_not_ready`
- `tests/test_sprint64_active_source_activation_readiness_gate.py::test_placeholder_review_artifacts_can_yield_ready_for_future_packet`
- `tests/test_sprint64_post_runtime_active_source_verification.py::test_evidence_snapshot_field_mismatch_blocks`
- `tests/test_sprint64_post_runtime_active_source_verification.py::test_already_activated_row_blocks`
- `tests/test_sprint64_post_runtime_active_source_verification.py::test_valid_runtime_row_verifies_ready_for_activation_gate`
- `tests/test_sprint64_post_runtime_active_source_verification.py::test_runtime_row_snapshot_includes_required_fields`
- `tests/test_sprint64_post_runtime_active_source_verification.py::test_rollback_contract_present_and_activation_fields_null`
- `tests/test_sprint64_post_runtime_active_source_verification.py::test_pipeline_evidence_remains_false`
- `tests/test_sprint64_post_runtime_active_source_verification.py::test_all_actual_counts_zero_and_may_flags_false`
- `tests/test_sprint64_post_runtime_active_source_verification.py::test_service_does_not_write_db`
- `tests/test_sprint64_post_runtime_active_source_verification.py::test_no_new_alembic_revision_beyond_0019`
- `tests/test_sprint65_active_source_activation_review_packet.py::test_28_no_new_alembic_revision_beyond_0019`
