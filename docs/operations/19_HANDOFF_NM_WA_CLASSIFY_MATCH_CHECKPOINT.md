# Checkpoint — NM/WA Classify+Match Expansion (Sprints 1–50)

**Block:** NM/WA classify+match expansion  
**Path:** `/home/josefgray/projects/nativeforge`  
**Baseline before block:** `c26d33a`  
**Push:** not performed  

## Delivered

- NM pilot fixture loader / profile loader / classify+match / honesty / invariants (22 federal profiles)
- WA pilot fixture loader / profile loader / classify+match / honesty / invariants (29 federal profiles)
- Matching profile selector wiring for `nm_pilot_` and `wa_pilot_`
- Shared NM/WA rollup: batch summary, readiness, missing-data, provenance
- Operator review queue, reasons, next-checks, fixture coverage
- OK/SC regression smokes
- Closeout packet + validation rollup services

## Hard invariants

1. No final eligibility claim without explicit evidence + operator review
2. Unknown/incomplete profile data remains discoverable and forces review
3. Partial matches remain discoverable
4. No live ingestion / source activation / scraping in this block

## Do Not Use

`/home/josefgray/projects/NativeForge` (capitalized) is stale/do-not-use.
