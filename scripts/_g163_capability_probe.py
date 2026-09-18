"""Measure collector capability for the authorized source, and for others.

A capability report that only ever ran against the one source it was built for
has not been shown to discriminate. Three subjects: the authorized API row, a
real row whose adapter has no capability, and a row that does not exist.
"""

from __future__ import annotations

import json
import sys
import uuid

sys.path.insert(0, "src")
sys.path.insert(0, ".")

from nativeforge.db.session import SessionLocal  # noqa: E402
from nativeforge.services.source_collector_capability_service import (  # noqa: E402
    capability_invariant_failures,
    measure_collector_capability,
)
from nativeforge.services.source_monitoring_approved_source_service import (  # noqa: E402
    load_registry_rows,
)

DEMO = uuid.UUID("bbbbbbbb-cccc-dddd-eeee-ffffffffffff")
AUTHORIZED = "nf-seed-2026-api-grants-gov-search2"
OTHER_REAL = "nf-seed-2026-fed-001"

registry = load_registry_rows()
session = SessionLocal()

for label, source_id in (
    ("the authorized API source", AUTHORIZED),
    ("another real source (adapter has no capability)", OTHER_REAL),
    ("a source that does not exist", "nf-seed-2026-does-not-exist"),
):
    row = registry.get(source_id)
    result = measure_collector_capability(
        source_id=source_id,
        registry_row=row,
        connection=session,
        organization_id=DEMO,
    )
    print(f"=== {label}")
    print(f"    source_id        {source_id}")
    print(f"    adapter_key      {result['adapter_key']}")
    print(f"    collector_status {result['collector_status']}")
    print(f"    capable          {result['capable']}")
    print(f"    measured         {json.dumps(result['measured'], sort_keys=True)}")
    print(f"    unmet            {result['unmet']}")
    invariants = capability_invariant_failures(result)
    print(f"    invariants       {invariants or 'clean'}")
    if result["notes"].get("request_body"):
        print(f"    request_body     {json.dumps(result['notes']['request_body'])}")
    for key in (
        "adapter_endpoint",
        "registry_endpoint",
        "known_adapters",
        "import_error",
        "request_builder_error",
        "endpoint_error",
        "executor_error",
    ):
        if result["notes"].get(key):
            print(f"    {key:<16} {result['notes'][key]}")
    print()

session.close()
