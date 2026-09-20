"""Render the Gate 166G scale table from the phase output. Reads stdin."""

from __future__ import annotations

import json
import sys

data = json.load(sys.stdin)
print("  scale   sweep_ms   per_source_ms   fleet_computations   invariant_failures")
for key in ("10", "100", "1000", "5000"):
    row = data["scales"][key]
    print(
        f"{row['sources']:>7} {row['sweep_ms']:>10} {row['per_source_ms']:>15} "
        f"{row['total_fleet_computations']:>20}   {row['invariant_failures']}"
    )
print()
print("real fleet sweep:")
print(f"  registered        {data['real_sweep_registered']}")
print(f"  evaluated         {data['real_sweep_evaluated']}")
print(f"  authorized        {data['real_sweep_authorized']}")
print(f"  sweep_ms          {data['real_sweep_ms']}")
print(f"  counts            {data['real_sweep_counts']}")
print(f"  fleet             {data['real_sweep_fleet_computations']}")
