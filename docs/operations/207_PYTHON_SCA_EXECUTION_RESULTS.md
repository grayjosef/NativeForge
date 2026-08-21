# Python SCA Execution Results (Gate 16 / Block 38)

## Method

* Ephemeral `pip install pip-audit` into active `.venv` (not project lockfile)
* Command: `pip-audit --progress-spinner off`
* `uv.lock` not touched

## Results (Gate 16 run)

| Item | Value |
|------|-------|
| python_sca_run | true |
| python_sca_exit_status | 0 |
| python_sca_passed | true |
| frontend npm audit clean (Gate 14) | true |
| full_sca_passed_claimed | true |
| uv.lock touched | false |

Initial findings (before scoped remediation):

* `pydantic-settings` GHSA-4xgf-cpjx-pc3j → remodeled floor to `>=2.14.2` in `pyproject.toml` + venv upgrade
* `pip` PYSEC advisories → upgraded pip in `.venv` only (not a project lockfile)

`nativeforge` itself is skipped by pip-audit (local package not on PyPI) — expected.

## Claims

* Full SCA passed: **true** (frontend npm + Python pip-audit clean after scoped remediation)
* Pen-test passed: **false**
* Controlled customer pilot: **NO_GO**
