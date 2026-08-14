# Lint Categories Fixed vs Deferred (mid-block)

Block: NF Full-Suite Health / Lint-Debt Containment  
Sprint: 036

## Fixed in this block

| Category | Action |
|----------|--------|
| I001 | Cleared for `src` + `tests` (sprints 011–020) |
| E501 (fixable) | Contained large safe slice via ruff wrap on tests (021–030); remaining are unbreakable tokens |
| E741 | Fixed (1 site) (031) |
| F401 | Cleared (19 sites) (032–033) |

## Deferred

| Category | Count (approx) | Reason |
|----------|----------------|--------|
| E501 remainder | ~700 | Long single-token strings; no safe autofix |
| F841 | 3 | Needs ownership (unused locals may be intentional) |
| F811 | 1 | Redefinition needs ownership review |
| Full-suite failures | 46 (baseline) | Alembic-head `0019` vs `0021`, activation/corpus gates — separate block |

## Explicitly not used

- Repo-wide `ruff check --fix` (mass)
- Repo-wide format sweep
- Product/scoring/match/auth/migration changes
