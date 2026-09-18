"""Which lanes are not ready, and what evidence each one is missing.

`runtime_status` is composed from six lanes, each observing its own evidence.
The composed answer says `not_ready`; it does not say which lane or why, and
the difference matters. A lane that is not_ready because nothing has exercised
it yet is a different thing from one that is not_ready because something is
broken, and only the second is a defect.
"""

from __future__ import annotations

import importlib
import sys
import uuid

sys.path.insert(0, "src")
sys.path.insert(0, ".")

from nativeforge.db.session import SessionLocal  # noqa: E402
from nativeforge.services.source_runtime_readiness_fact_service import (  # noqa: E402
    LANES,
    REQUIRED_FOR_COLLECTION,
    build_runtime_readiness_facts,
    runtime_readiness_invariant_failures,
)

DEMO = uuid.UUID("bbbbbbbb-cccc-dddd-eeee-ffffffffffff")

session = SessionLocal()
facts = build_runtime_readiness_facts(connection=session, organization_id=DEMO)

print(f"runtime_status            {facts['runtime_status']}")
print(f"lanes_ready               {facts['lanes_ready']} of 6")
print(f"unmet_for_collection      {facts['unmet_for_collection']}")
print(f"invariant failures        {runtime_readiness_invariant_failures(facts)}")
print()

for name, module_name, function_name, _ready_field in LANES:
    if facts["lanes"][name].get("status") == "ready":
        continue
    required = "REQUIRED" if name in REQUIRED_FOR_COLLECTION else "optional"
    print(f"=== {name}  [{required}]")
    try:
        module = importlib.import_module(f"nativeforge.services.{module_name}")
        builder = getattr(module, function_name)
        try:
            health = builder(connection=session, organization_id=DEMO)
        except TypeError:
            health = builder()
    except Exception as exc:  # noqa: BLE001
        print(f"    could not observe: {type(exc).__name__}: {exc}")
        continue

    for key in ("blockers", "conditions_not_met", "unmet_conditions", "missing"):
        value = health.get(key)
        if not value:
            continue
        print(f"    {key}:")
        for item in value if isinstance(value, list) else [value]:
            print(f"      - {item}")

    conditions = health.get("conditions")
    if isinstance(conditions, dict):
        unmet = sorted(k for k, v in conditions.items() if v is not True)
        if unmet:
            print(f"    conditions not True: {unmet}")
    print()

session.close()
