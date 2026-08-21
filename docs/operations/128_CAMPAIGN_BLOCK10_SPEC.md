# Campaign Block 10 Spec — Source Ingestion + Freshness Pilot

Block **10 of 20** (Gate 02). Fixture-backed read-only source freshness / health pilot.

## Delivered

- Source freshness contract with live/continuous/production claims forced false
- Fixture-backed checks for federal TEDC fixture, SC curated pack, unsupported SC portal monitor
- Deadline / staleness / change / duplicate warnings v0
- SC demo Source freshness panel + smoke

## Hard guards

- `external_live_check_not_run=true` for fixture pilot
- No live ingest / continuous monitoring / production activation claims
- Opportunities not auto-removed when stale
