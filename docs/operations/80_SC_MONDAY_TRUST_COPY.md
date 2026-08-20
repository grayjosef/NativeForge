# SC Monday Trust Copy (Sprint 038)

Buyer-visible honesty controls on `/?view=sc_customer_demo`:

- Advisory banner: curated/fixture only; not automated live ingestion
- Flags: live_ingestion=false, source_activation=false, final_eligibility_claim_allowed=false
- Per-row: human_review_required=true, data_label, live_ingest_not_claimed
- Claim matrix in payload: live/source/final claim NOT_CLAIMED / NOT_ALLOWED
