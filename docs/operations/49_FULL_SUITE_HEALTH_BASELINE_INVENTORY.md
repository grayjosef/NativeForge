# NativeForge Full-Suite Health Baseline Inventory

**Block:** NF Full-Suite Health / Lint-Debt Containment Block  
**HEAD at inventory start:** `a1203ba`  
**Timestamp (UTC):** 20260814T193734Z  
**Path:** `/home/josefgray/projects/nativeforge`

## Control point

- branch: `main`
- origin/main: aligned (`a1203ba`)
- working tree: clean at start
- protected stash: `stash@{0}: On main: wip-sprint8-ui-redesign-do-not-commit`
- uv.lock: present, untouched

## Full-suite pytest

- command: `pytest -q --tb=line`
- collected tests: **5522**
- log: `/tmp/nativeforge_full_pytest_20260814T193734Z.log`
- **result: 5463 passed, 13 skipped, 46 failed, 18 warnings**
- duration: **1409.01s (0:23:29)**
- Alembic head at run time: `0021`

### Failure summary (46) — deferred (not lint-containment)

| Category | Approx count | Notes |
|----------|-------------:|-------|
| active_source runtime/migration tests | 24 | sprint47/62/64 clusters |
| alembic head expectation (`beyond_0019`) | 14 | tests assert no `0020_*` while head is `0021` |
| corpus/closeout gates (nf15/nf16) | 5 | sprint/gate assertions |
| eligibility/matching vocab | 3 | recognition/fit/readiness |

These are **pre-existing product/test expectation debt**, not introduced by lint work. This block inventories them and does **not** change scoring/match/activation/migration behavior to force green.

## Repo-wide ruff inventory (no auto-fix)

- command: `ruff check src tests --output-format=concise`
- log: `/tmp/nativeforge_ruff_inventory_20260814T193734Z.log`
- **total errors: 1285** (parser tally 1284 line matches; ruff footer reports 1285)
- fixable with `--fix`: **82** (mostly I001)
- unsafe fixes available: 3 hidden

### By rule code

| Code | Count | Notes |
|------|------:|-------|
| E501 | 1198 | line too long (>88) — dominant backlog |
| I001 | 62 | import block unsorted — mechanically fixable |
| F401 | 19 | unused import — defer unless clearly dead |
| F841 | 3 | unused local — defer |
| F811 | 1 | redefined while unused — defer |
| E741 | 1 | ambiguous variable name `l` |

### Split

- `src/`: ~638 findings
- `tests/`: ~646 findings

### Top offending files (by finding count)

1. `tests/test_sprint73_active_source_activation_execution_plan_authoring_authorization_decision_packet.py` (95)
2. `tests/test_sprint72_active_source_activation_execution_plan_authoring_authorization_request_packet.py` (84)
3. `tests/test_sprint74_active_source_activation_execution_plan_authoring_review_packet.py` (71)
4. `src/nativeforge/services/active_source_activation_review_packet_service.py` (43)
5. `src/nativeforge/services/active_source_activation_execution_plan_authoring_authorization_request_packet_service.py` (41)

### Containment plan (this block)

1. **I001** — safe mechanical import sorting in small batches (prefer tests, then src).
2. **E501** — safe wrapping in test-only files / assertions / imports; defer mega-packet service files if high risk.
3. **E741** — single ambiguous `l` rename in test if behavior-neutral.
4. **F401/F841/F811** — defer unless trivially safe; document.

### Explicit non-goals

- No product/scoring/match/auth/migration/activation changes
- No repo-wide `ruff --fix` mass sweep
- No uv.lock / stash / push

## Prior smoke lineage (unchanged by this block)

- Playwright: `nf_os_playwright_20260811T112219Z_4c991fc1` (PASS)
