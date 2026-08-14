# Lint-debt containment plan (this block)

## Order of attack

1. I001 import sorting (tests, then src) — mechanical
2. E501 safe wrapping in test files only (assertions/imports/constants)
3. E741 single test-local rename
4. Re-inventory

## Deferred

- F401/F841/F811 without ownership review
- E501 in dense active-source packet services
- Full-suite 46 failing product/alembic-expectation tests
- Repo-wide `ruff --fix` mass sweep
