# NM/WA Smoke Checkpoint — Sprint 040

## Shipped (031–040)

- Real run_id generator (`nf_os_smoke_...`)
- Per-surface evaluator (14 surfaces)
- Offline smoke runner service
- Honest NOT_RUN helper
- Hard-stop tests (combined queue, final claim, live flags, next-check)
- Shell verify script `scripts/nm_wa_operator_surfacing_smoke_verify.sh`

## Next (041–050)

- Execute smoke for real in this environment
- Capture run_id + per-surface results
- Closeout packet + update `13_HANDOFF_LATEST.md`
- STOP; no push

## Guardrails

Offline synthetic only; no classify/match/auth/migration changes; stash preserved.
