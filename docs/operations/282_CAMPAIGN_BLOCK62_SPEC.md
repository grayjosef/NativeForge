# Campaign Block 62 Spec — Production Dry-Run Cutover

Sprint-equivalents: 2751–2800.

Service: `gate28_dry_run_cutover_service.py`  
Assembler: `gate28_dry_run_cutover_assembler_service.py`  
Smoke: `scripts/campaign_block62_smoke_verify.sh`  
Tests: `tests/test_dry_run_cutover_campaign62.py`  
Docs: `279_GATE28_PRODUCTION_DRY_RUN_CUTOVER.md`, `280_GATE28_FINAL_FREEZE_VERIFICATION.md`

Default Mode A: first hard blocker `auth0_oidc_preflight`; downstream `skipped_after_blocker`.
