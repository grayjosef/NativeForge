# Deferred F841 / F811 Lint Debt

Block: NF Full-Suite Health / Lint-Debt Containment  
Sprint: 034

## Policy

Do **not** auto-remove assigned-but-unused locals (`F841`) or redefinition (`F811`) without ownership review. These can be intentional placeholders, incomplete assertions, or dual-definition patterns that need product/test intent.

## Remaining (deferred)

| Code | File | Note |
|------|------|------|
| F841 | `src/nativeforge/services/active_source_activation_review_packet_service.py` | `wrong_type` assigned unused |
| F841 | `src/nativeforge/services/recognition_tier_eligibility_gate_service.py` | `member_level_only` assigned unused |
| F841 | `tests/test_sprint56_active_source_human_approval_intake.py` | `oid` assigned unused |
| F811 | `src/nativeforge/services/mixed_corpus_grant_field_derivation_service.py` | `_TRIBAL_TYPE_RE` redefined |

## Fixed this block (related)

- `F401` unused imports removed in scoped test + src batches (sprints 032–033).
- `E741` ambiguous `l` renamed in `tests/test_ta_tier3_foundation_adapter.py` (sprint 031).
- `I001` import-order cleared repo-wide for `src` + `tests` (sprints 011–020).

## Next safe action for these codes

Separate ownership sprint: inspect each site, decide delete vs use vs `# noqa` with reason.
