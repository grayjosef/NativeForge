# NativeForge Handoff — NM/WA Classify+Match Expansion (50-sprint block)

**Repaired/closed:** 2026-08-10
**Block:** NM/WA classify+match expansion (Sprints 1–50)
**Status:** COMPLETE locally — WAIT for Mayhem review (**do not push**)

## Current State

| Field | Value |
|-------|-------|
| Project | NativeForge |
| Path | /home/josefgray/projects/nativeforge |
| Branch | main |
| HEAD before block | c26d33a |
| HEAD after block | f80f994 (tip may advance by this docs pin commit) |
| origin/main | c26d33a |
| Ahead / behind | ahead of origin (block commits not pushed) |
| Push | Not performed |
| Working tree | clean at close (expected after handoff pin) |
| Protected stash | stash@{0}: On main: wip-sprint8-ui-redesign-do-not-commit — preserved |
| uv.lock | present, untouched |
| Smoke run_id | UNKNOWN |
| Full-suite test count | UNKNOWN (not run) |
| Next token | UNKNOWN |

## Do Not Use — stale clone

Do not use /home/josefgray/projects/NativeForge (capitalized). Use only /home/josefgray/projects/nativeforge.

## Feature state

- NM wired: yes — fixture loader, profile loader, classify+match orchestrator, honesty, invariants, selector wiring (22 federal profiles)
- WA wired: yes — same stack (29 federal profiles)
- Operator-review / unknown-data: all matches labeled needs_operator_review; unknown/incomplete fields remain discoverable via missing-data reporting and operator review queue
- Hard invariants: covered in NM/WA/rollup/closeout tests (no final claim without evidence; unknowns force review; partial matches discoverable; no live exec/activation)

## Validation

- Scoped ruff/format on touched Python only (no repo-wide ruff mass-fix)
- Scoped pytest for NM/WA/rollup/review/closeout tests
- Offline staging: scripts/nm_wa_pilot_staging_verify.sh (OK)
- Scoped test files: 39 (full suite not claimed)
- Repo-wide ruff backlog: untouched by design

## Related docs

- docs/operations/19_HANDOFF_NM_WA_CLASSIFY_MATCH_CHECKPOINT.md
- docs/operations/20_HANDOFF_NM_WA_VALIDATION_ROLLUP.md
- docs/operations/21_NM_WA_BLOCK_FINAL_STATUS.md

## UNKNOWNs

- Smoke run_id
- Full-suite pytest / ruff green counts
- Next sprint token after Mayhem review
- Whether Mayhem will push this block as-is

## Recommended next safe action

Mayhem review local ahead commits on /home/josefgray/projects/nativeforge; approve push manually if desired; do not use capitalized clone; optional full-suite run only if explicitly approved.
