# NativeForge Handoff — Block NF-3: Org/Applicant Profile Foundation (Sprints 197–211)

**Date:** 2026-05-19  
**Branch:** `main` (ahead of `origin/main`)  
**Push:** Not performed (per governance)  
**Stash:** Preserved — `stash@{0}: wip-sprint8-ui-redesign-do-not-commit`

## Preflight verification

| Check | Result |
|-------|--------|
| `pwd` | `/home/josefgray/projects/nativeforge` |
| Branch | `main` |
| HEAD at block start | `61d3e4d` (met ≥ `7ef1937`) |
| Working tree | Clean (no staged `uv.lock`) |
| Stash preserved | `stash@{0}: wip-sprint8-ui-redesign-do-not-commit` |
| ContractForge/Spark language in org profile work | None found |

## Run summary

Completed the approved 15-sprint Stage 7 org/applicant profile foundation block with green baseline first (`4947` passed). All work is offline, deterministic, synthetic-fixture-only, advisory — no live ingestion, scraping, external URLs, LLM runtime, source activation, runtime DB mutation, or Alembic migrations.

| Sprint | Commit | Summary |
|--------|--------|---------|
| 197 | `8352606` | Profile schema vocabulary (20 fields) |
| 198 | `b393324` | Field-level provenance |
| 199 | `97f1cc7` | Sensitive-field flags |
| 200 | `b375a6a` | Review status model (draft → verified_by_user, stale, incomplete, archived) |
| 201 | `0f6f44a` | Unknown value policy (`UNKNOWN` sentinel; never invent) |
| 202 | `4cb26a3` | **No-invention guard** — protected fields cannot be fabricated |
| 203 | `1a387f6` | **Verified-by-user guard** — requires explicit human/customer confirmation |
| 204 | `b9f8eb6` | **No-mutation-without-approval guard** |
| 205 | `7d3de15` | Synthetic demo fixture corpus (`fixtures/org_applicant_profile/demo_records.json`) |
| 206 | `170ac6f` | Provenance-first profile record builder |
| 207 | `44e2f02` | Profile evaluator (all three hard invariants applied) |
| 208 | `74066b3` | Hardened profile record assembler |
| 209 | `89a4f34` | Profile rollup |
| 210 | `dc2ff50` | Operator review queue + Stage 7 gate verification |
| 211 | `f482ee6` | Stage 7 org/applicant profile closeout packet |

**Iterations used:** 15 product sprints (within leash)

## Build / test state

- **Baseline at block start:** `4947 passed`, `11 skipped`, `0 failed`
- **Full pytest (final):** `4989 passed`, `11 skipped`, `0 failed` (+42 org profile tests)
- **Ruff:** Green on org profile Python files (per-file `E501` ignores in `pyproject.toml`)
- **Alembic head:** `0019` (no new migrations in this block)
- **Stash:** Untouched
- **uv.lock:** Not staged or committed

## Profile schema (20 fields)

`legal_name`, `entity_type`, `tribal_government_status`, `federally_recognized_status`, `native_serving_nonprofit_status`, `alaska_native_status`, `native_hawaiian_status`, `tribal_college_status`, `geography`, `service_area`, `population_served`, `program_areas`, `funding_interests`, `eligibility_markers`, `past_awards`, `grant_capacity`, `staff_capacity`, `match_capacity`, `required_documents_on_file`, `contacts`

## Review statuses

`draft`, `needs_review`, `reviewed`, `verified_by_user`, `stale`, `incomplete`, `archived`

## Service chain

1. **Schema** (`org_applicant_profile_schema_service.py`)
2. **Field provenance** (`org_applicant_profile_field_provenance_service.py`)
3. **Sensitive fields** (`org_applicant_profile_sensitive_field_service.py`)
4. **Review status** (`org_applicant_profile_review_status_service.py`)
5. **Unknown value policy** (`org_applicant_profile_unknown_value_policy_service.py`)
6. **No-invention guard** (`org_applicant_profile_no_invention_guard_service.py`)
7. **Verified-by-user guard** (`org_applicant_profile_verified_by_user_guard_service.py`)
8. **No-mutation guard** (`org_applicant_profile_no_mutation_without_approval_guard_service.py`)
9. **Demo fixtures** (`org_applicant_profile_demo_fixture_service.py`)
10. **Record builder** (`org_applicant_profile_record_builder_service.py`)
11. **Evaluator** (`org_applicant_profile_evaluator_service.py`)
12. **Hardened record** (`org_applicant_profile_hardened_record_service.py`)
13. **Rollup** (`org_applicant_profile_rollup_service.py`)
14. **Gate verification + review queue** (`org_applicant_profile_stage7_gate_verification_service.py`)
15. **Closeout packet** (`org_applicant_profile_stage7_closeout_packet_service.py`)

Key artifact types: `nf_org_applicant_profile_hardened_record_v1`, `nf_org_applicant_profile_stage7_gate_verification_v1`, `nf_org_applicant_profile_stage7_closeout_packet_v1`.

## Hard invariants (all tested)

1. **No invention** — tribal affiliation, federally-recognized status, Native-serving status, certifications, geography, past awards, UEI, authorized representative, documents, and eligibility markers cannot be fabricated; unknown inputs remain `UNKNOWN`.
2. **No verified_by_user without confirmation** — `verified_by_user` downgrades to `needs_review` unless `human_confirmation_present` or `customer_confirmation_present` is true.
3. **No mutation without approval** — profile mutations blocked unless `operator_approved` is true; no runtime DB mutation in this layer.

## Coexisting Stage 7 layers

This block adds org/applicant profile foundation alongside the prior eligibility fit assessment layer (also sprints 197–211, committed earlier in the same block series). Both are preview-only advisory services with separate `org_applicant_profile_*` and `eligibility_fit_assessment_*` namespaces.

## Key decisions

1. **Green baseline first** before any org profile feature commit.
2. **Provenance-first record builder** applies no-invention guard per schema field before assembly.
3. **Six demo fixtures** cover tribal government, incomplete profile, native nonprofit, verified attempt (blocked), verified confirmed, and mutation request (blocked).
4. **Discoverability preserved** — incomplete profiles remain `discoverable: true` with forced human review.
5. **NativeForge language only** — no Spark, ContractForge, bid, or solicitation branding.

## Risks / needs human

- **Not pushed** — Review required before `git push`.
- **AIRTABLE_TOKEN** not set in agent environment — all `log_run.sh` calls skipped.
- **Live profile ingestion** explicitly out of scope until separate human authorization.

## Proposed next safe action

1. Push and review the 16 org-profile commits on `main`.
2. Operator walkthrough of Stage 7 gate verification + demo fixture corpus.
3. Wire org profile previews into discovery intake summaries (advisory only) or continue eligibility fit integration.

## Verification commands

```bash
cd /home/josefgray/projects/nativeforge
source .venv/bin/activate
pytest -q
git log --oneline -16
git stash list   # confirm stash@{0} still present
pytest tests/test_sprint211_org_applicant_profile_stage7_closeout_packet.py -q
```
