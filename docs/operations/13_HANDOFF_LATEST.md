# 13_HANDOFF_LATEST — NativeForge

## Block complete
**NF Smoke/Demo Validation Block — NM/WA operator surfacing end-to-end visibility**

## Control point
- path:  (stale clone  avoided)
- branch: 
- HEAD before: 
- HEAD after: 
- origin/main: behind local by 52 commit(s); **not pushed**
- working tree: clean after sprint 050
- protected stash: 
- uv.lock: present, untouched/unstaged
- prior block: NF Operator Surfacing Block — NM/WA classify+match review visibility

## Smoke / demo state
- smoke executed: **yes** (offline_synthetic)
- smoke/demo run_id: 
- overall: **PASS**
- mode: offline fixtures + demo artifact + CLI/static HTML (no frontend, no network)
- artifact: 
- surfaces (all PASS):
  - nm_fixture_visibility
  - wa_fixture_visibility
  - nm_classify_match_outputs
  - wa_classify_match_outputs
  - nm_operator_report
  - wa_operator_report
  - combined_review_queue_report
  - missing_data_display
  - human_review_display
  - operator_next_check_display
  - provenance_evidence_display
  - confidence_readiness_labels
  - no_final_eligibility_claim_behavior
  - broad_partial_relevance_discoverable_behavior
- failures: none
- NOT_RUN reason: n/a (executed)

## Validation
- scoped : run (green at close)
- scoped : 48 passed (revalidated in sprint 044 window)
- : OK
- : OK (sprint 047)
- full suite: **NOT_RUN**
- repo-wide ruff: **NOT_RUN** / backlog untouched

## Feature state
- demo artifact builder: yes
- smoke runner + verify script: yes
- browser/frontend touched: no
- scoring/match logic changed: no
- source activation / live ingestion: no
- hard invariants covered: 9 (closeout packet)

## Commits
205ade5 docs(sprint-049): add NM/WA smoke validation closeout packet
c55a9a7 feat(sprint-048): mark full smoke/demo pytest suite revalidation
0bef525 feat(sprint-047): record NM/WA classify+match staging verify availability
24cfebb feat(sprint-046): record NM/WA operator surfacing staging verify availability
c4eef6c fix(sprint-042): correct smoke test module coverage threshold
93b80ce feat(sprint-045): capture real offline NM/WA smoke run_id and results
44ac761 feat(sprint-044): revalidate prior NM/WA operator surfacing builders
7949d78 feat(sprint-043): lock smoke hard invariant coverage list
2495888 feat(sprint-042): assert smoke/demo test module coverage present
91e4902 feat(sprint-041): add NM/WA smoke closeout packet builder
296abc1 fix(sprint-035): treat malformed demo artifact render errors as smoke FAIL
4ededfa docs(sprint-040): NM/WA smoke checkpoint after smoke runner sprints
5c45708 feat(sprint-039): fail smoke when operator next-check display is missing
8234d14 feat(sprint-038): add NM/WA operator surfacing smoke verify script
448c18e feat(sprint-037): fail smoke on live ingestion or source activation flags
ba22731 feat(sprint-036): fail smoke on final eligibility claim without evidence
bfdebab feat(sprint-035): fail smoke when combined review queue is missing
343c297 feat(sprint-034): support honest NOT_RUN smoke result without fabricated run_id
3a50376 feat(sprint-033): execute offline NM/WA operator surfacing smoke runner
2d9aa04 feat(sprint-032): evaluate per-surface smoke PASS/FAIL results
5b8961a feat(sprint-031): generate real NM/WA smoke run_id
faa5692 fix(sprint-026): repair static-only demo assertion and CLI docstring lint
123ab33 docs(sprint-030): NM/WA smoke checkpoint after demo visibility layer
eef286f feat(sprint-029): support HTML output via offline demo CLI
e0a3db5 feat(sprint-028): include confidence distribution in demo payload
bbfa59f feat(sprint-027): expose next-check and review flags in demo samples
d30b735 feat(sprint-026): keep demo visibility on CLI/static (no frontend)
0173fc9 feat(sprint-025): add NM/WA operator surfacing offline demo CLI
70d7834 feat(sprint-024): write static HTML demo report to local path
db5c348 feat(sprint-023): render static HTML NM/WA operator demo report
0b89867 feat(sprint-022): render plain-text NM/WA operator demo report
32c128d feat(sprint-021): add serializable NM/WA demo visibility payload
fc7d734 docs(sprint-020): NM/WA smoke checkpoint after demo artifact sprints
7657d8f feat(sprint-019): lock offline-only flags on demo artifact
b6e1694 feat(sprint-018): include operator next-check summary in demo artifact
9c9af31 feat(sprint-017): include provenance/evidence summary in demo artifact
26c794e feat(sprint-016): include missing-data summary in demo artifact
0757a33 feat(sprint-015): ensure demo artifact digest is deterministic
78977b7 feat(sprint-014): prove unknowns and review-required preserved in demo artifact
ee411b7 feat(sprint-013): validate demo artifact honesty invariants
d48db6a feat(sprint-012): write offline demo artifact JSON to local path
0a56322 feat(sprint-011): add NM/WA operator surfacing demo artifact builder
f685be6 docs(sprint-010): NM/WA smoke checkpoint after contract sprints
52c55bf feat(sprint-009): lock expected smoke surface coverage list
1350439 docs(sprint-008): add NM/WA smoke/demo validation plan
40c1bb1 feat(sprint-007): extract ordered surfaces from smoke manifest
ccb017f feat(sprint-006): add NM/WA smoke manifest checklist
eac59cd feat(sprint-005): validate smoke result honesty invariants
7426ef9 feat(sprint-004): add empty smoke result scaffold with expected surfaces
0b985b2 feat(sprint-003): add smoke surface PASS/FAIL/NOT_RUN result model
83b842b feat(sprint-002): validate NM/WA smoke run_id format
ea92ada feat(sprint-001): add NM/WA smoke validation contract

## Files changed (52 commits)
artifacts/nm_wa_smoke/closeout_packet.json
artifacts/nm_wa_smoke/nf_os_smoke_20260811T004712Z_9dccb0db.json
docs/operations/28_NM_WA_SMOKE_DEMO_VALIDATION_PLAN.md
docs/operations/29_NM_WA_SMOKE_CHECKPOINT_010.md
docs/operations/30_NM_WA_SMOKE_CHECKPOINT_020.md
docs/operations/31_NM_WA_SMOKE_CHECKPOINT_030.md
docs/operations/32_NM_WA_SMOKE_CHECKPOINT_040.md
docs/operations/33_NM_WA_SMOKE_LIVE_EXECUTION.md
docs/operations/34_NM_WA_SMOKE_CLOSEOUT_PACKET.md
pyproject.toml
scripts/nm_wa_operator_surfacing_demo_cli.py
scripts/nm_wa_operator_surfacing_smoke_verify.sh
src/nativeforge/services/nm_wa_operator_surfacing_demo_artifact_service.py
src/nativeforge/services/nm_wa_operator_surfacing_demo_render_service.py
src/nativeforge/services/nm_wa_smoke_closeout_packet_service.py
src/nativeforge/services/nm_wa_smoke_manifest_service.py
src/nativeforge/services/nm_wa_smoke_runner_service.py
src/nativeforge/services/nm_wa_smoke_validation_contract_service.py
tests/test_sm_sprint001_smoke_contract.py
tests/test_sm_sprint002_run_id_format.py
tests/test_sm_sprint003_surface_result.py
tests/test_sm_sprint004_empty_smoke_result.py
tests/test_sm_sprint005_validate_smoke_result.py
tests/test_sm_sprint006_smoke_manifest.py
tests/test_sm_sprint007_manifest_surfaces.py
tests/test_sm_sprint009_expected_surface_coverage.py
tests/test_sm_sprint011_demo_artifact_builder.py
tests/test_sm_sprint012_write_demo_artifact.py
tests/test_sm_sprint013_demo_artifact_invariants.py
tests/test_sm_sprint014_unknowns_visible_in_artifact.py
tests/test_sm_sprint015_demo_artifact_deterministic.py
tests/test_sm_sprint016_missing_data_summary.py
tests/test_sm_sprint017_provenance_summary.py
tests/test_sm_sprint018_next_check_summary.py
tests/test_sm_sprint019_offline_flags.py
tests/test_sm_sprint021_demo_visibility_payload.py
tests/test_sm_sprint022_demo_text_report.py
tests/test_sm_sprint023_demo_html_report.py
tests/test_sm_sprint024_write_demo_html.py
tests/test_sm_sprint025_demo_cli.py
tests/test_sm_sprint026_no_frontend_dependency.py
tests/test_sm_sprint027_sample_rows_guidance.py
tests/test_sm_sprint028_confidence_in_payload.py
tests/test_sm_sprint029_demo_cli_html.py
tests/test_sm_sprint031_generate_run_id.py
tests/test_sm_sprint032_evaluate_surfaces.py
tests/test_sm_sprint033_run_smoke.py
tests/test_sm_sprint034_smoke_not_run.py
tests/test_sm_sprint035_hard_stop_combined.py
tests/test_sm_sprint036_hard_stop_final_claim.py
tests/test_sm_sprint037_no_network_flags.py
tests/test_sm_sprint038_smoke_script_exists.py
tests/test_sm_sprint039_hard_stop_next_check.py
tests/test_sm_sprint041_closeout_packet.py
tests/test_sm_sprint042_all_sm_tests_marker.py
tests/test_sm_sprint043_hard_invariant_coverage.py
tests/test_sm_sprint044_prior_os_still_green.py
tests/test_sm_sprint045_live_smoke_artifact.py
tests/test_sm_sprint046_staging_verify_recorded.py
tests/test_sm_sprint047_classify_match_staging.py
tests/test_sm_sprint048_sm_suite_marker.py
tests/test_sm_sprint049_closeout_packet_file.py

## Guardrails
- stash preserved
- no push
- no migrations / alembic autogenerate
- no scrape / live ingest / external URLs / source activation
- no fabricated PASS or run_id

## UNKNOWNs remaining
- Full pytest suite not run this block
- Browser-based UI smoke not run (CLI/static path chosen intentionally)
- Production/demo deploy readiness not assessed

## NEXT SAFE ACTION
Mayhem review of  ahead of origin (52 commits), then manual push if approved. Optional: wire a gated demo page later without changing classify/match.
