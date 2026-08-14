# Closeout Smoke / Staging Results

Block: NF Full-Suite Health / Lint-Debt Containment  
Sprint: 044

## Classify/match staging verify

```
nm_pilot_staging_verify: OK
wa_pilot_staging_verify: OK
nm_wa_pilot_staging_verify: OK
```

## Operator surfacing staging verify

```
nm_wa_operator_surfacing_staging_verify: OK
```

## Offline operator surfacing smoke

- run_id: `nf_os_smoke_20260814T201145Z_6392e848`
- overall: `PASS`

```
run_id=nf_os_smoke_20260814T201145Z_6392e848
overall_status=PASS
result_path=/home/josefgray/projects/nativeforge/artifacts/nm_wa_smoke/nf_os_smoke_20260814T201145Z_6392e848.json
surface=nm_fixture_visibility status=PASS detail=nm_profiles=22
surface=wa_fixture_visibility status=PASS detail=wa_profiles=29
surface=nm_classify_match_outputs status=PASS detail=nm_classify_match_rows=22
surface=wa_classify_match_outputs status=PASS detail=wa_classify_match_rows=29
surface=nm_operator_report status=PASS detail=nm_report_rows=22
surface=wa_operator_report status=PASS detail=wa_report_rows=29
surface=combined_review_queue_report status=PASS detail=combined_rows=51
surface=missing_data_display status=PASS detail=missing_rows=4
surface=human_review_display status=PASS detail=human_review_rows=51
surface=operator_next_check_display status=PASS detail=next_check_rows=51
surface=provenance_evidence_display status=PASS detail=provenance_summary_present
surface=confidence_readiness_labels status=PASS detail=confidence_keys=['public_inferred_low']
surface=no_final_eligibility_claim_behavior status=PASS detail=no_final_claim_across_rows
surface=broad_partial_relevance_discoverable_behavior status=PASS detail=all_rows_visible_in_operator_review
```

## Demo-runtime / Playwright

Deferred to sprint 046 — run only if dependencies remain valid; no live ingest.
