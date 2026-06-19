# AGENTS.md - NativeForge (Codex)
Canonical brief: CLAUDE.md in repo root. Follow exactly.
- Plan-gate: produce a PLAN, stop for approval before code.
- Autonomous after approval: per sprint -> implement -> ruff + pytest -> commit to main only if green -> log.
- Iteration leash 25 (cap, not target); plan sets the sprint range; then STOP + Clear Briefing. Never push.
- Auto-stop: red/unfixable tests, guardrail break, scope drift, blocker, or secrets/production/dependency-sensitive systems.
Guardrails: PRESERVE STASHES (never drop); no auto-submit grants; Native-RELEVANT scope (not only Native-specific); dry-run-first migrations via generation gate; never commit secrets or red builds.
