# NativeForge Handoff — NF Operator Surfacing Block (NM/WA review visibility)

**Closed:** 2026-08-10
**Block:** NF Operator Surfacing Block — NM/WA classify+match review visibility
**Status:** COMPLETE locally — WAIT for Mayhem review (do not push)

## Current State

| Field | Value |
|-------|-------|
| Project | NativeForge |
| Path | /home/josefgray/projects/nativeforge |
| Branch | main |
| HEAD before block | 392da8f |
| HEAD after block | 7213877 |
| origin/main | 392da8f |
| Ahead / behind | ahead 50, behind 0 |
| Push | Not performed |
| Working tree | clean at close |
| Protected stash | stash@{0}: On main: wip-sprint8-ui-redesign-do-not-commit — preserved |
| uv.lock | present, untouched |
| Smoke/demo run_id | UNKNOWN / NOT_RUN |
| Full-suite test count | NOT_RUN |
| Next token | UNKNOWN |

## Do Not Use — stale clone

Do not use /home/josefgray/projects/NativeForge (capitalized). Use only /home/josefgray/projects/nativeforge.

## Feature state

- NM operator surfacing built: yes (report builder + rollup over existing classify+match outputs)
- WA operator surfacing built: yes (symmetric structure; 29 profiles)
- Combined review queue/report built: yes (stable ordering, confidence/provenance summaries)
- Operator-review / unknown-data behavior: unknowns remain discoverable; missing_data shown; human review + next-check required; no final eligibility claim
- Hard invariant coverage: yes (schema validation, NM/WA/combined/closeout tests)
- Scoring/match logic changed: no
- Source activation / live ingestion touched: no
- Repo-wide ruff backlog touched: no

## Validation

- Scoped ruff/format on touched Python only
- Operator surfacing scoped tests: 46 passed (sprint-047 run of test_os_sprint*.py)
- Staging: scripts/nm_wa_operator_surfacing_staging_verify.sh OK
- Prior NM/WA pilot staging: scripts/nm_wa_pilot_staging_verify.sh OK
- Full suite: NOT_RUN
- Repo-wide ruff: NOT_RUN (legacy backlog)

## Related docs

- docs/operations/22_CHECKPOINT_OS_SPRINTS_001_010.md
- docs/operations/23_CHECKPOINT_OS_SPRINTS_011_020.md
- docs/operations/24_CHECKPOINT_OS_SPRINTS_021_030.md
- docs/operations/25_CHECKPOINT_OS_SPRINTS_031_040.md
- docs/operations/26_CHECKPOINT_OS_SPRINTS_041_050_PREP.md
- docs/operations/27_OS_BLOCK_FINAL_STATUS.md

## UNKNOWNs

- Smoke/demo run_id
- Full-suite pytest / ruff green counts
- Next sprint token after Mayhem review
- Whether Mayhem will push this block as-is

## Recommended next safe action

Mayhem review local ahead commits on /home/josefgray/projects/nativeforge; approve push manually if desired; keep capitalized clone unused; optional UI surfacing only under a new approved PLAN.
