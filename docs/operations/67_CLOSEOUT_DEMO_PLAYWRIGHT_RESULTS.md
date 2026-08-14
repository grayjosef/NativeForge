# Closeout Demo-Runtime / Playwright Results

Block: NF Full-Suite Health / Lint-Debt Containment
Sprints: 045–046

## Prior Playwright run_id (block start)

`nf_os_playwright_20260811T112219Z_4c991fc1`

## Demo-runtime smoke (sprint 045)

- exit: 0
- run_id: `nf_os_browser_20260814T201241Z_139b751a`
- overall: `PASS`

```
run_id=nf_os_browser_20260814T201241Z_139b751a
overall_status=PASS
smoke_mode=demo_runtime_static_vitest
playwright_status=NOT_RUN
result_path=/home/josefgray/projects/nativeforge/artifacts/nm_wa_browser_smoke/nf_os_browser_20260814T201241Z_139b751a.json
screen=nm_fixture_visibility status=PASS detail=nm_fixtures=22
screen=wa_fixture_visibility status=PASS detail=wa_fixtures=29
screen=nm_classify_match_outputs status=PASS detail=nm_cm=22
screen=wa_classify_match_outputs status=PASS detail=wa_cm=29
screen=nm_operator_report status=PASS detail=nm_report=22
screen=wa_operator_report status=PASS detail=wa_report=29
screen=combined_review_queue_report status=PASS detail=combined=51
screen=missing_data_display status=PASS detail=missing_rows=4
screen=human_review_display status=PASS detail=human_review=51
screen=operator_next_check_display status=PASS detail=next_checks=51
screen=provenance_evidence_display status=PASS detail=provenance_visible
screen=confidence_readiness_labels status=PASS detail=confidence_keys=['public_inferred_low']
screen=no_final_eligibility_claim_behavior status=PASS detail=no_final_claim
screen=broad_partial_relevance_discoverable_behavior status=PASS detail=all_visible
```

## Playwright E2E smoke (sprint 046)

- exit: 0
- run_id: `nf_os_playwright_20260814T201248Z_84db3820`
- overall: `PASS`

```
run_id=nf_os_playwright_20260814T201248Z_84db3820
overall_status=PASS
smoke_mode=playwright_e2e
demo_route_path=/?view=nm_wa_operator_demo
headless=True
screen=nm_fixture_visibility status=PASS detail=playwright_spec_passed_visible_markers
screen=wa_fixture_visibility status=PASS detail=playwright_spec_passed_visible_markers
screen=nm_classify_match_outputs status=PASS detail=playwright_spec_passed_visible_markers
screen=wa_classify_match_outputs status=PASS detail=playwright_spec_passed_visible_markers
screen=nm_operator_report status=PASS detail=playwright_spec_passed_visible_markers
screen=wa_operator_report status=PASS detail=playwright_spec_passed_visible_markers
screen=combined_review_queue_report status=PASS detail=playwright_spec_passed_visible_markers
screen=missing_data_display status=PASS detail=playwright_spec_passed_visible_markers
screen=human_review_display status=PASS detail=playwright_spec_passed_visible_markers
screen=operator_next_check_display status=PASS detail=playwright_spec_passed_visible_markers
screen=provenance_evidence_display status=PASS detail=playwright_spec_passed_visible_markers
screen=confidence_readiness_labels status=PASS detail=playwright_spec_passed_visible_markers
screen=no_final_eligibility_claim_behavior status=PASS detail=playwright_spec_passed_visible_markers
screen=broad_partial_relevance_discoverable_behavior status=PASS detail=playwright_spec_passed_visible_markers
artifact=artifacts/nm_wa_playwright_smoke/nf_os_playwright_20260814T201248Z_84db3820.log
artifact=artifacts/nm_wa_playwright_smoke/nf_os_playwright_20260814T201248Z_84db3820.json
```
