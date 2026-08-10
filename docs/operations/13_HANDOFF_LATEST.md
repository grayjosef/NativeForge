# NativeForge Handoff — Current State (repair)

**Repaired:** 2026-08-10
**Purpose:** Replace stale Block M8 handoff text with verified repo truth. No feature work in this repair.

## Current State

| Field | Verified value |
|-------|----------------|
| Project | NativeForge |
| Path | `/home/josefgray/projects/nativeforge` |
| Branch | `main` |
| HEAD | `658659e` (`658659e9aeb862018689fe18b4c4b8a7dbf786b1`) — Add NM and WA pilot tribal profile fixtures for classify+match expansion |
| `origin/main` | `d266475` (`d266475556a33389235a4c9e59976c96cd76def2`) — Fix static extraction gap with card-DOM parser and tuned seed matching |
| Ahead / behind | Local `main` **ahead 1**, behind 0 vs `origin/main` |
| Push | **Not performed** — do not push without Mayhem approval |
| Working tree (at inspection / pre-repair) | Clean |
| Remote | `origin` → `git@github.com:grayjosef/NativeForge.git` |
| Protected stash | `stash@{0}: On main: wip-sprint8-ui-redesign-do-not-commit` — **preserved; do not drop/pop/apply** |
| Smoke `run_id` | **UNKNOWN** |
| Full-suite test count | **UNKNOWN** (not re-run for this docs-only repair) |
| Next token | **UNKNOWN** (no current proven token in ops handoffs for HEAD) |

## Do Not Use — stale clone

**Do not use** `/home/josefgray/projects/NativeForge` (capitalized path). That clone is **stale / do-not-use**. All NativeForge work must use **`/home/josefgray/projects/nativeforge`** only.

## Latest known work (from git history)

Current HEAD is fixture expansion on top of extraction and pilot work already on `origin/main` and recent ancestors:

1. **`658659e`** — NM and WA pilot tribal profile fixtures (`fixtures/nm_pilot/`, `fixtures/wa_pilot/`) for classify+match expansion (**local only; not on origin yet**).
2. **`d266475`** (`origin/main`) — Static extraction gap fix: card-DOM parser, noise filter, tuned seed matching; staging verify script + tests.
3. **`cd01ced`** — Tier-3 foundation cohort-3 (9 seeds) activatable coverage exhaust.
4. **`12e0ae3`** — Tier-2 state portal pilot (per-portal ingest, MT tribal filter, honest empty portals).
5. **`fd2b44a`** — Tier-3 foundation cohort-2 (14 seeds) with native-relevance ranking.
6. **`33f69db`** — OK pilot classify+match for 38 federal tribes with `grant_posture` advisory.

Older topical handoffs still exist under `docs/operations/14_HANDOFF_*` … `18_HANDOFF_*` (LA/SH/RT/TA/SC). They describe prior blocks and are **not** a substitute for this current-state file.

## What this repair does **not** claim

- Does **not** invent sprint numbers, next tokens, smoke `run_id`, or test counts.
- Does **not** restate Block M8 Activation Console as current HEAD work. Prior M8 content in the previous version of this file was **stale relative to HEAD** (cited hash `328b48d` was not current).
- Does **not** authorize push, migrations, scraping, live ingestion, source activation, or stash changes.

## UNKNOWNs

- Smoke `run_id` for current HEAD
- Current full-suite pytest / ruff green counts
- Next sprint / handoff token
- Whether NM/WA fixtures already have matching orchestrator/service wiring beyond fixtures (not verified in this repair)
- Whether Mayhem intends to push `658659e` as-is or fold further pilot work first

## Guardrails (standing)

- Never push without Mayhem approval.
- Preserve protected stash; never drop/clear stash.
- No migrations, scrape, live ingest, external URL calls, source activation, or runtime data mutation in handoff-only work.
- NativeForge terminology only; do not import ContractForge product language into NativeForge planning.

## Recommended next safe action

Mayhem: review local commit `658659e` (NM/WA fixtures) and decide push vs further pilot wiring; optionally refresh this handoff again after any verified pytest/ruff run or after a real next-token is assigned. Do not use the capitalized clone.
