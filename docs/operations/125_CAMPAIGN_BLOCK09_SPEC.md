# Campaign Block 09 Spec — Real NOFO PDF Extraction Pilot

Block **9 of 20** (Gate 02). Controlled one-opportunity NOFO extraction pilot for `la-real-006` (TEDC) using fixture text derived from Grants.gov fetch `362648`.

## Delivered

- Extraction contract with honesty flags (`full_pdf_extraction_claimed=false`, `broad_pdf_support_claimed=false`, `pdf_bytes_parsed=false`)
- Section detection + requirement map with confidence / missing labels
- Package-chain integration (parallel; does not replace curated showcase)
- SC demo panel + smoke

## Hard guards

- No full/broad PDF claim
- No PDF byte parsing (named PDF referenced only)
- No final eligibility from extraction
- No proposal drafting
