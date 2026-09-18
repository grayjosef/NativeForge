"""Run the runtime lane exerciser and report what each lane measured."""

from __future__ import annotations

import json
import sys
import uuid

sys.path.insert(0, "src")
sys.path.insert(0, ".")

from nativeforge.db.session import SessionLocal  # noqa: E402
from nativeforge.services.source_runtime_lane_exerciser_service import (  # noqa: E402
    exercise_runtime_lanes,
    exerciser_invariant_failures,
)

DEMO = uuid.UUID("bbbbbbbb-cccc-dddd-eeee-ffffffffffff")

session = SessionLocal()
result = exercise_runtime_lanes(connection=session, organization_id=DEMO)
session.close()

print(f"runtime_status        {result['runtime_status']}")
print(f"lanes_exercised       {result['lanes_exercised']} of 4")
print(f"unmet_lanes           {result['unmet_lanes']}")
print(f"fixture_rows_cleaned  {result['fixture_rows_cleaned']}")
print(f"fixture_residue       {result['fixture_residue']}")
print(f"cleanup_failures      {result['cleanup_failures'] or 'none'}")
print(f"invariants            {exerciser_invariant_failures(result) or 'clean'}")
print()
for name in result["lane_names"]:
    lane = result["lanes"][name]
    print(f"=== {name}")
    print(f"    exercised      {lane['exercised']}")
    print(f"    ready          {lane['ready']}")
    print(f"    cleanup_count  {lane['cleanup_count']}")
    if lane["unmet_conditions"]:
        print(f"    unmet          {lane['unmet_conditions']}")
    if lane["evidence"]:
        print(f"    evidence       {json.dumps(lane['evidence'], sort_keys=True)}")
    print()
