# NativeForge Handoff — Block NF-11: True Live Grants.gov + Honest Labeling (Sprints 308–316)

**Date:** 2026-05-19  
**Branch:** `main` (ahead of `origin/main`)  
**Push:** Not performed (per governance)  
**Stash:** Preserved — `stash@{0}: wip-sprint8-ui-redesign-do-not-commit`

## Run summary

Completed NF-11 with green baseline (`5129` passed, `11` skipped). Active federal source path now executes `search2` + `fetchOpportunity` live in staging; `real_fetch: true` is set only when both HTTP calls succeed in live mode. Fixtures/replays are labeled `fetch_mode: "fixture"`, `fixture: true`, `real_fetch: false`. fed-001 binds strictly to ALN **15.020** (empty when no posted NOFO); resolver falls back to TEDC fed-006 (**15.148**) for live activation. Eligibility parser maps `applicantTypes` + `applicantEligibilityDesc` → `tribal_eligible` + populated `eligibility_text`.

| Sprint | Summary |
|--------|---------|
| 308 | Grants.gov eligibility parser (`applicantTypes` + `applicantEligibilityDesc`) |
| 309 | Fed program activation binding (15.020 primary → 15.148 TEDC fallback) |
| 310 | Honest `fetch_mode` / `real_fetch` labeling in search2 + fetchOpportunity adapter |
| 311 | Live Grants.gov honest orchestrator + gate verification |
| 312 | NF-11 closeout packet, routes, tests |
| 313–316 | Block closeout |

## Honest labeling

| Path | `fetch_mode` | `fixture` | `real_fetch` |
|------|--------------|-----------|--------------|
| Staging live HTTP (search2 + fetchOpportunity both succeed) | `live` | `false` | `true` |
| Recorded TEDC fixture (CI) | `fixture` | `true` | `false` |
| Empty ALN match (fed-001 / 15.020) | `live` | `false` | `false` |

## Program binding

| Seed | Program | Behavior |
|------|---------|----------|
| `nf-seed-2026-fed-001` | ALN **15.020** Aid to Tribal Governments | Primary; live search returns empty today (correct) |
| `nf-seed-2026-fed-006` | ALN **15.148** TEDC | Fallback when 15.020 has no live NOFO; activated in CI/staging resolver |

Exactly **one** source activated per block run. TEDC fixture (`BIA-TEDC-2026`, opp id 362648) bound to fed-006 — no longer served as fed-001 fixture.

## Eligibility parser

From real `fetchOpportunity` synopsis:

- Combines applicant type descriptions + `applicantEligibilityDesc` (HTML stripped)
- Sets `tribal_eligible: true` when tribal applicant type ids (07, 11) or narrative cues match
- TEDC fixture: `tribal_eligible=true`, eligibility text includes "Indian Tribes and Tribal Energy Development Organizations"

## API

New staging-gated route (same quadruple gate as NF-9/NF-10):

```
POST /v1/nf/{demo|real}/orgs/{org_id}/discovery/source-ingestion/live-grants-gov-honest
  ?nf_live_source_ingestion=true&nf_real_resolver_validation=true
```

Body: operator confirmation (`operator_handle`, `human_activation_acknowledged`, `public_only_acknowledged`, `single_source_only_acknowledged`).

## Build / test state

- **Baseline at block start:** `5124 passed`, `11 skipped`
- **Full pytest (final):** `5129 passed`, `11 skipped` (+5 tests)
- **Stash:** Untouched

## Hard invariants preserved

- Staging only; plan gates unchanged
- No illustrative/synthetic NOFO fabrication
- Public-only activation path
- Exactly one active source per activation
- **WAIT** — no push

## Proposed next safe action

1. Deploy to staging; POST `live-grants-gov-honest` for real HTTP against Grants.gov (expect fed-006 TEDC activation while 15.020 empty).
2. Confirm `real_fetch: true` on staging response when both API calls succeed.
3. Do not push without Mayhem review.

## Verification commands

```bash
cd /home/josefgray/projects/nativeforge
pytest -q
pytest tests/test_sprint308_grants_gov_eligibility_parser.py tests/test_sprint309_fed_program_activation_binding.py tests/test_sprint312_live_grants_gov_honest_closeout.py -q
```
