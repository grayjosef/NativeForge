# Code Health / Test Posture Report (Gate 06 / Block 17)

Schema: `nf_code_health_inventory_v1`

## Totals

- Source files: **1337**
- Test files: **787**
- Source LOC (approx): **385484**
- Test LOC (approx): **177965**
- Approximate test-to-code ratio: **0.4617**

## Breakdown

- Python source: {'file_count': 1250, 'line_count': 365828}
- Python tests: {'file_count': 768, 'line_count': 175030}
- Frontend source: {'file_count': 87, 'line_count': 19656}
- Frontend tests: {'file_count': 19, 'line_count': 2935}
- Service modules: {'file_count': 1152, 'line_count': 336330}
- Frontend pages: {'file_count': 10, 'line_count': 6201}
- Smoke scripts: {'file_count': 95, 'line_count': 1552}
- Campaign block smokes: {'file_count': 86, 'line_count': 1210}
- Playwright specs: {'file_count': 2, 'line_count': 933}

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
    "file_count": 86,
    "line_count": 1210
  },
  "frontend_e2e_specs": {
    "file_count": 2,
    "line_count": 933
  },
  "frontend_pages": {
    "file_count": 10,
    "line_count": 6201
  },
  "frontend_source": {
    "file_count": 87,
    "line_count": 19656
  },
  "frontend_tests": {
    "file_count": 19,
    "line_count": 2935
  },
  "frontend_unit_tests": {
    "file_count": 17,
    "line_count": 2002
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
    "file_count": 2022,
    "line_count": 81514
  },
  "pen_test_passed_claimed": false,
  "playwright_specs": {
    "file_count": 2,
    "line_count": 933
  },
  "python_source": {
    "file_count": 1250,
    "line_count": 365828
  },
  "python_tests": {
    "file_count": 768,
    "line_count": 175030
  },
  "repo_root": "/home/josefgray/projects/nativeforge",
  "schema_version": "nf_code_health_inventory_v1",
  "service_modules": {
    "file_count": 1152,
    "line_count": 336330
  },
  "smoke_scripts": {
    "file_count": 95,
    "line_count": 1552
  },
  "totals": {
    "approximate_test_to_code_ratio": 0.4617,
    "source_files": 1337,
    "source_loc": 385484,
    "test_files": 787,
    "test_loc": 177965
  }
}
```
