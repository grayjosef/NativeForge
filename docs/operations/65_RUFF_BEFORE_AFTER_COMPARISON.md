# Ruff Before/After Comparison

Block: NF Full-Suite Health / Lint-Debt Containment  
Sprint: 042

| Metric | Before | After | Delta |
|--------|-------:|------:|------:|
| Total ruff errors | 1285 | 702 | 583 |

## Rule-code movement (baseline → after)

| Code | Before | After | Notes |
|------|-------:|------:|-------|
| E501 | 1198 | ~696 | Large safe wrap slice; remainder unfixable tokens |
| I001 | 62 | 0 | Cleared |
| F401 | 19 | 0 | Cleared |
| F841 | 3 | 3 | Deferred ownership |
| F811 | 1 | 1 | Deferred ownership |
| E741 | 1 | 0 | Fixed |

## Categories fixed

I001, F401, E741, fixable E501 (tests-first containment)

## Categories deferred

Unfixable E501 remainder; F841; F811; full-suite alembic-head/activation expectation debt

## Safety

- Repo-wide ruff auto-fix used?: **no**
- Repo-wide ruff backlog touched safely?: **yes** (scoped batches only)
