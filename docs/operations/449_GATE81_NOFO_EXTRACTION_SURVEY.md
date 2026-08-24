# 449 — Gate 81A: NOFO / parser / amendment survey

Surveyed before writing anything, because 770 services already exist in this
package and Gate 79B's lesson was that the expensive mistake is forking a
vocabulary that already had an owner.

## Existing NOFO / parser code

| Service | What it actually does | Reusable here? |
| --- | --- | --- |
| `nofo_extraction_service` | Sprint 3 orchestration over `NfGrantSpark` ORM rows; writes review artifacts | **No** — DB-bound, not a text parser |
| `nofo_stub_extractor` | deterministic stub; synthesises text when the body is missing | **No** — inventing prose is the opposite of this gate |
| `nofo_extraction_pilot_extractor_service` | Block 09; section detection over **one** fixture, pinned to `la-real-006` | **Pattern yes, code no** — hardcoded to one opportunity and one fixture path |
| `nofo_extraction_pilot_contract_service` | `FIELD_STATUSES`, `CONFIDENCE_LABELS`, `make_extracted_field` | **Yes, as precedent** for field-level status + confidence |
| `grants_gov_eligibility_parser_service` | parses Grants.gov **structured synopsis** (applicant type ids `07`/`11`) | **No** — structured API fields, not notice prose |
| `no_live_nofo_state_service` | honest `no_live_nofo` source state | **Yes** — the honesty boundary stays |

The two `nofo_showcase_*` and `active_source_activation_m*` families are
planning/demo packets, not parsers.

## Existing amendment handling

`opportunity_freshness_service` (Gate 76D) already owns this and owns it well:

```text
FRESHNESS_STATES        fresh, stale, expired, amended, superseded, unknown
CURRENT_STATES          {fresh, amended}          (NON_CURRENT derived by difference)
VISIBLE_STATES          all of them
EXTENSION_EVIDENCE_KINDS      amendment_notice_url, federal_register_notice_url,
                              funder_announcement_url, operator_verified_extension
SUPERSESSION_EVIDENCE_KINDS   same_opportunity_number, amendment_notice_url,
                              funder_stated_supersession, operator_verified_supersession
```

It already enforces: missing close date → `unknown`, never fresh; supersession
requires same lineage **plus** evidence; expired/stale stay visible.

**Gate 81D must not re-answer any of that.** What it adds is the step before:
reading a notice and producing the evidence that service consumes.

## Existing eligibility text handling

`eligibility_exclusion_evidence_service` (Gate 79) already has a text analyser:

```text
CLASS_PHRASES        7 Native classes, conservative phrase lists
RESTRICTION_PHRASES  federal_trust_land, reservation_only, service_area_only
EXCLUSIVITY_MARKERS  only, limited to, restricted to, must be, solely, ...
analyse_eligibility_text(text) -> named_classes, is_exclusive_list, restrictions
evaluate_applicant_class(...) -> excluded_by_evidence requires evidence_reference
```

So "detect classes in eligibility prose" **exists**. Three things do not:

1. **Context gating.** `analyse_eligibility_text` analyses whatever string it is
   handed. Nothing stops a caller passing the whole notice, so a "tribal" in a
   background paragraph would read as eligibility. Gate 81's central rule.
2. **Citation spans.** It returns class *names*, never where they were found.
   Gate 79 requires a citation for exclusion but the analyser cannot supply one.
3. **Non-Native classes.** Only 7 Native classes are known. An exclusive list
   reading "only units of local government" names nothing the analyser knows, so
   it cannot see that tribes are excluded.

### Applicant vocabularies found — three, and a fourth is required

| Where | Members |
| --- | --- |
| `eligibility_exclusion_evidence_service.APPLICANT_CLASSES` | 8 — **canonical for exclusion** |
| `eligibility_evidence_contract_service.APPLICANT_CATEGORIES` | 14 — Block 02 evidence axis, incl. `tribal_college_university`, `alaska_native_entity`, `native_hawaiian_organization` |
| `federal_native_eligibility_service.RECOGNITION_TIERS` | 3 — bridged already via `FEDERAL_TIER_MAP` |

Gate 81C needs 12 classes: the 8 canonical, minus `unknown`, plus
`local_government`, `state_government`, `nonprofit`, `education_institution`.

**Resolution: superset, not fork.** `PARSER_APPLICANT_CLASSES` is declared as a
strict superset of the canonical set, guarded by a test asserting
`APPLICANT_CLASSES ⊆ PARSER_APPLICANT_CLASSES`, and projected back down (the
four non-Native classes dropped) before anything reaches the exclusion service.
The non-Native classes exist to make *exclusive lists* readable, which is the
only way to evidence exclusion of a class the text never names.

## Existing deadline handling

`opportunity_freshness_service` consumes `close_date` / `posted_date` /
`amendment_date` as already-parsed strings. `eligibility_fit_assessment_deadline_risk_service`
scores risk from parsed dates. **Nothing turns notice prose into a date**, and
nothing represents a date whose precision is uncertain. That is the gap.

## Safe reuse points

1. `analyse_eligibility_text` + `CLASS_PHRASES` + `RESTRICTION_PHRASES` +
   `EXCLUSIVITY_MARKERS` — import, do not re-declare.
2. `evaluate_applicant_class` / `evaluate_all_applicant_classes` — the parser
   feeds these rather than deciding eligibility itself.
3. `evaluate_opportunity_freshness` / `evaluate_supersession` and both evidence
   kind sets — the detector emits evidence in those shapes.
4. `native_opportunity_discovery_service.build_native_opportunity_record(
   exclusion_result=...)` — the Gate 79B seam, already wired.
5. `make_extracted_field` field-status/confidence precedent from Block 09.

## Gaps Gate 81 fills

- Source-agnostic section detection over arbitrary notice text (Block 09's is
  pinned to one opportunity and one fixture).
- **Char-offset spans** so every extracted claim cites where it came from.
- **Eligibility-context gating** — a class named outside an eligibility section
  earns no eligibility credit.
- Date extraction that preserves uncertainty instead of guessing precision.
- Non-Native classes, so exclusive lists become readable.
- A notice-status axis (`original`/`corrected`/`supplemented`/`extended`/
  `cancelled`/`withdrawn`/...) that projects onto freshness rather than
  competing with it.

## Deliberately not touched

- `FRESHNESS_STATES` and both evidence-kind sets — the detector projects onto
  them; it does not extend them.
- `APPLICANT_CLASSES` — extended by superset, never edited.
- `not_eligible` remains unassertable.
- The hermetic Grants.gov guard and corpus write-back guards.
- `nofo_stub_extractor`'s synthesis path — left alone, and never called here.
- Anything that would fetch. No network in any Gate 81 code path.
