# No Mass Ruff Autofix — Adherence Record

Block: NF Full-Suite Health / Lint-Debt Containment  
Sprint: 039

## Controls followed

- Repo-wide inventory only (`ruff check`, no `--fix` at tree scope)
- Fixes applied with explicit file lists + `--select` scopes
- No `git add -A`
- `uv.lock` never staged
- Protected stash untouched
- No push

## Allowed fix selectors used

- `--select I001`
- `--select E501` (scoped files only)
- `--select F401` (scoped files only)
- Manual E741 rename (one test site)
