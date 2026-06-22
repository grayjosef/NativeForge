# NativeForge Handoff — Block NF-13: Classify + Match the Real Grants (Sprints 322–331)

**Date:** 2026-05-19  
**Branch:** `main` (ahead of `origin/main`)  
**Push:** Not performed (per governance)  
**Stash:** Preserved — `stash@{0}: wip-sprint8-ui-redesign-do-not-commit`

## Run summary

Completed NF-13 with green baseline. Classified 40 real ingested grants through the 8-label native-relevance classifier with per-grant explanations derived from source text. Matched all grants against the Red Cedar Nation synthetic tribal profile (swappable, no real customer data). Surfaced results in operator workbench queues. Hard invariants: overclaim guard, over-filter guard, classification evidence honest labeling.

| Sprint | Summary |
|--------|---------|
| 322 | Real grants corpus loader (40 tier-1 public federal grants) |
| 323 | Classification input adapter — evidence derived from source only |
| 324 | Classification evidence honest labeling guard + failing tests |
| 325 | Real-grant native relevance records with explanations |
| 326–327 | Classify + match service against test tribal profile |
| 328 | Workbench queues (native relevance + matching readiness) |
| 329–331 | Orchestrator, routes, gate verification, closeout |

## Classification results (40 real grants)

| Label | Count (approx.) |
|-------|-----------------|
| `tribal_government_specific` | 38 |
| `irrelevant` | 2 |

All classifications include:
- `trigger_language`, `eligible_entity_types`, `whats_missing` from explanation templates
- `source_eligibility_excerpt` from real eligibility text
- `derived_evidence_codes` — never invented

## Matching results (Red Cedar Nation profile)

| Match label | Count |
|-------------|-------|
| `needs_operator_review` | 40 |

Applicant-specific recommendations correctly stay `needs_operator_review` (no human confirmation on synthetic profile). Fit dimensions, blockers, and missing data surfaced per grant.

## Honest labeling invariants

- `assert_classification_evidence_honest()` — evidence codes must ⊆ derived from source
- `native_specific` without explicit source evidence → test **fails**
- Overclaim guard: never `native_specific` without source evidence (existing Stage 6)
- Over-filter guard: broad labels stay discoverable (existing Stage 6)
- Unknown → flagged (`uncertain_relevance`, human review), not invented

## API

```
POST .../real-grant-classify-match?nf_live_source_ingestion=true&nf_real_resolver_validation=true
GET  .../real-grant-workbench-queues?...
GET  .../operator-workbench-advisory/real-grant-queues?nf_workbench=true&...
```

## Worked examples

Gate verification returns 2 worked examples with classification label, match label, explanation summary, fit dimensions, and blockers.

## Build / test state

- **Baseline at block start:** `5138 passed`, `11 skipped`
- **Full pytest (final):** `5146 passed`, `11 skipped` (+8 tests)
- **Stash:** Untouched

## Hard invariants preserved

- Staging only; plan gates unchanged
- Classifications from real source text only
- No fabricated eligibility, labels, or matches
- Public-only; no customer PII
- **STOP** at checkpoint — no push
- **WAIT**

## Verification commands

```bash
cd /home/josefgray/projects/nativeforge
pytest -q
pytest tests/test_sprint324_classification_evidence_honest_guard.py tests/test_sprint327_real_grant_classify_match.py tests/test_sprint331_real_grant_classify_match_closeout.py -q
```
