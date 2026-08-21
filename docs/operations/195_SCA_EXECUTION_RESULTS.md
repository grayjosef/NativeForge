# SCA Execution Results (Gate 14 / Block 34)

## Status

* Tooling discovery: **complete** (no new installs)
* SCA run: **true** (frontend `npm audit --omit=dev`)
* Full SCA passed claim: **false**
* Pen-test passed: **false**
* `uv.lock` touched: **false**

## Commands run

| Command | Exit | Result |
|---------|------|--------|
| `cd frontend && npm audit --omit=dev --json` | 0 | clean (0 high/critical) |
| `pip-audit` | blocked | not installed |
| `bandit` / `safety` / `gitleaks` | blocked | not installed |

## Honest claims

* Allowed: “SCA execution attempted”; “frontend npm audit clean”
* Forbidden: “SCA passed” (pip-audit incomplete); “production secure”; “pen-test passed”

## Remediation

* No high/critical npm findings requiring scoped dependency upgrades in this gate
* Next: install/run `pip-audit` under owner approval; remediate Python findings if any
* Do not mass-upgrade dependencies; do not touch `uv.lock` without intentional report

## Controlled pilot impact

* Controlled customer pilot remains **NO_GO**
* Production rollout remains **NO_GO**

Artifact: `artifacts/sca_execution/latest_sca_execution.json`
