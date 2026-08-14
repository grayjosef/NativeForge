# NativeForge Lint-Debt Inventory Report

**Source inventory log:** `/tmp/nativeforge_ruff_inventory_20260814T193734Z.log`  
**Baseline total:** 1285 errors (ruff footer)  
**Auto-fix used for inventory:** no

## Rule codes

| Code | Count | Containment stance |
|------|------:|--------------------|
| E501 | 1198 | Fix safe test wrapping only; defer dense packet services |
| I001 | 62 | Fix mechanically (`ruff check --fix --select I001`) in batches |
| F401 | 19 | Defer (unused import — needs ownership review) |
| F841 | 3 | Defer |
| F811 | 1 | Defer |
| E741 | 1 | Fix if test-local rename is behavior-neutral |

## I001 split

- tests: 32
- src: 30
- Prefer tests first, then src import sorting only.

## E741

- `tests/test_ta_tier3_foundation_adapter.py` ambiguous `l`

## Explicit deferrals

- F401/F841/F811 without clear dead-code proof
- E501 in large active-source packet services/tests with dense long identifiers
- Any lint requiring semantic/product understanding
