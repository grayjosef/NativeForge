# NativeForge Handoff — Block M8: Operator Activation Console

**Status:** Closed locally at `328b48d`. Push: `git push origin main` (when GitHub reachable).

## Close-gate evidence (staging smoke)

- `NF_DEV_ORG_HEADERS=false` + `X-NF-Actor-Role: operator` → **503** (governed mutation denied; header not honored)
- Kill switch engaged → `verify-live` halts live publish + auto-publish queue (`kill_switch_engaged`)
- Agent governed actions → **403**
- Live publish without reason → **400**; with reason → **200** + audit row
- `policy:change` auto-publish enable → append-only config version + audit

Run: `bash scripts/m8_close_gate_staging_smoke.sh`

## Summary

Operators control per-workspace activation from a dedicated **Activation** console view. Durable M7 state (`nf_activation_state`, append-only `nf_auto_publish_config`) backs the UI and API. Governed dispatcher enforces `activation:toggle` and `policy:change`; agents are hard-denied; high-risk enables require confirm + reason; kill switch is one-click engage with no dialog.

## Sprint deliverables

| # | Deliverable | Status |
|---|-------------|--------|
| 1 | Activation read API + state view | `GET .../operator/activation` + Activation UI |
| 2 | Kill-switch control | `activation:toggle` engage/release, audited, halts M5 publish gate |
| 3 | Flag controls | live-publish / live-attribution / auto-publish (policy:change for enable) |
| 4 | Safety UX | Confirm+reason modal for live publish & auto-publish enable; prominent kill switch |
| 5 | Handoff + runbook | This doc + `docs/m0-demo-runbook.md` Activation section |

## Durable state (M7)

| Table | Purpose |
|-------|---------|
| `nf_activation_state` | Per-org flags (default OFF), `state_version`, last actor |
| `nf_auto_publish_config` | Append-only auto-publish policy versions |

## API routes

| Route | Method | Notes |
|-------|--------|-------|
| `/{org}/operator/activation` | GET | Read state + publish gate + recent audit |
| `/{org}/operator/activation/governed-action` | POST | `X-NF-Actor-Role`: operator \| admin \| agent |

**Governed actions:** `activation:toggle`, `policy:change` (auto-publish enable only).

## UI

Header toggle: **Activation** (`?view=activation`). Role selector (dev): operator / admin / agent (read-only).

## Test baseline

`pytest tests/test_m8_operator_activation_console.py` — defaults, kill switch, agent denied, reason gates, policy versioning, publish halt.

## Governance

Staging/dev: `X-NF-Actor-Role` honored **only** when `NF_DEV_ORG_HEADERS=true`. Production-shaped config denies governed mutations (503); future auth replaces header parsing.
