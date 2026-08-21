# Code Health / Test Posture Report (Gate 06 / Block 17)

Schema: `nf_code_health_inventory_v1`

## Totals

- Source files: **654**
- Test files: **597**
- Source LOC (approx): **154612**
- Test LOC (approx): **86073**
- Approximate test-to-code ratio: **0.5567**

## Breakdown

- Python source: {'file_count': 572, 'line_count': 141231}
- Python tests: {'file_count': 581, 'line_count': 84461}
- Frontend source: {'file_count': 82, 'line_count': 13381}
- Frontend tests: {'file_count': 16, 'line_count': 1612}
- Service modules: {'file_count': 518, 'line_count': 129495}
- Frontend pages: {'file_count': 8, 'line_count': 2936}
- Smoke scripts: {'file_count': 27, 'line_count': 600}
- Campaign block smokes: {'file_count': 18, 'line_count': 258}
- Playwright specs: {'file_count': 2, 'line_count': 413}

## Honesty flags

- full_suite_run: `False`
- full_suite_passed: `False`
- pen_test_passed_claimed: `False`

## Notes

- Inventory is approximate LOC (newline-based); not coverage %.
- artifacts/, .venv/, node_modules/ excluded.
- Secrets and env vars are never included.
- Full-suite green is NOT claimed by this inventory.
- Pen-test pass is NOT claimed by this inventory.

## Machine-readable JSON

```json
{
  "campaign_block": 17,
  "campaign_block_smoke_scripts": {
    "file_count": 18,
    "line_count": 258
  },
  "frontend_e2e_specs": {
    "file_count": 2,
    "line_count": 413
  },
  "frontend_pages": {
    "file_count": 8,
    "line_count": 2936
  },
  "frontend_source": {
    "file_count": 82,
    "line_count": 13381
  },
  "frontend_tests": {
    "file_count": 16,
    "line_count": 1612
  },
  "frontend_unit_tests": {
    "file_count": 14,
    "line_count": 1199
  },
  "full_suite_passed": false,
  "full_suite_run": false,
  "notes": [
    "Inventory is approximate LOC (newline-based); not coverage %.",
    "artifacts/, .venv/, node_modules/ excluded.",
    "Secrets and env vars are never included.",
    "Full-suite green is NOT claimed by this inventory.",
    "Pen-test pass is NOT claimed by this inventory."
  ],
  "operations_docs": {
    "file_count": 1035,
    "line_count": 5600
  },
  "pen_test_passed_claimed": false,
  "playwright_specs": {
    "file_count": 2,
    "line_count": 413
  },
  "python_source": {
    "file_count": 572,
    "line_count": 141231
  },
  "python_tests": {
    "file_count": 581,
    "line_count": 84461
  },
  "repo_root": "/home/josefgray/projects/nativeforge",
  "schema_version": "nf_code_health_inventory_v1",
  "service_modules": {
    "file_count": 518,
    "line_count": 129495
  },
  "smoke_scripts": {
    "file_count": 27,
    "line_count": 600
  },
  "totals": {
    "approximate_test_to_code_ratio": 0.5567,
    "source_files": 654,
    "source_loc": 154612,
    "test_files": 597,
    "test_loc": 86073
  }
}
```
