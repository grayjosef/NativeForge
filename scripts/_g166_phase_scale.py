"""Gate 166G: authorization at 10 / 100 / 1,000 / 5,000 sources. No network.

Synthetic catalog entries only. Nothing here contacts a source, and a synthetic
row cannot authorize anything: it makes a source `registered`, which is the
floor of the ladder. The governance rows still come from the database.

## The invariant this exists to prove

```text
fleet_fact_computations  O(1) per sweep   <- required
per_source_evaluations   O(N)             <- expected
```

A timing number alone would not prove it. Timings vary with the machine, and
Gate 164 spent three attempts learning that a confident number from a defective
instrument is worse than no number. So the fleet-fact COUNT is measured
directly and asserted, and the timings are reported beside it as observations
of this machine rather than as throughput claims.

## What it does not measure

Fleet-fact cost is measured against the real database, which currently holds
2 payloads and 1 attempt. How fact resolution behaves at millions of rows is
NOT measured here and is reported as UNKNOWN rather than extrapolated.
"""

from __future__ import annotations

import json
import socket
import sys
import time
import uuid

sys.path.insert(0, "src")
sys.path.insert(0, ".")

_NETWORK = {"attempts": 0}
_real_socket = socket.socket


class _Refused(socket.socket):
    def __init__(self, *a, **k):  # noqa: ANN002, ANN003
        _NETWORK["attempts"] += 1
        raise OSError("gate166 makes no network request")


socket.socket = _Refused  # type: ignore[misc,assignment]

from nativeforge.db.session import SessionLocal  # noqa: E402
from nativeforge.services.source_authority_sweep_service import (  # noqa: E402
    sweep_invariant_failures,
    sweep_source_authority,
)
from nativeforge.services.source_monitoring_approved_source_service import (  # noqa: E402
    load_registry_rows,
)

DEMO = uuid.UUID("bbbbbbbb-cccc-dddd-eeee-ffffffffffff")
SCALES = (10, 100, 1000, 5000)

#: A reserved prefix. Nothing real can collide with it, and every row built
#: here is discarded when this process exits - no fixture residue, because
#: nothing is written.
SYNTHETIC = "nf166.scale."


def synthetic_catalog(count: int) -> dict[str, dict[str, str]]:
    """`count` catalog rows that exist only in memory."""
    return {
        f"{SYNTHETIC}{index:05d}": {
            "seed_id": f"{SYNTHETIC}{index:05d}",
            "source_name": f"Synthetic scale source {index}",
            "source_url": f"https://scale-{index:05d}.invalid/opportunities",
            "adapter_key": "html_listing",
            "source_type": "state_agency",
            "tier": "2",
        }
        for index in range(count)
    }


out: dict[str, object] = {}
session = SessionLocal()
try:
    real = load_registry_rows()
    out["real_catalog_rows"] = len(real)

    # ---- the real fleet, swept once ---------------------------------
    started = time.perf_counter()
    real_sweep = sweep_source_authority(
        connection=session, organization_id=DEMO, now=None
    )
    out["real_sweep_ms"] = round((time.perf_counter() - started) * 1000, 1)
    out["real_sweep_registered"] = real_sweep["registered_sources"]
    out["real_sweep_evaluated"] = real_sweep["evaluated_sources"]
    out["real_sweep_authorized"] = real_sweep["authorized_for_live"]
    out["real_sweep_counts"] = real_sweep["counts_by_state"]
    out["real_sweep_fleet_computations"] = real_sweep["fleet_facts"]["computations"]
    out["real_sweep_invariant_failures"] = sweep_invariant_failures(real_sweep)

    # ---- the synthetic scales ---------------------------------------
    results: dict[str, object] = {}
    fleet_counts: dict[str, int] = {}
    for scale in SCALES:
        catalog = synthetic_catalog(scale)
        started = time.perf_counter()
        report = sweep_source_authority(
            connection=session,
            organization_id=DEMO,
            registry_rows=catalog,
            now=None,
        )
        elapsed_ms = (time.perf_counter() - started) * 1000
        fleet = report["fleet_facts"]["computations"]
        total_fleet = sum(int(v or 0) for v in fleet.values())
        fleet_counts[str(scale)] = total_fleet
        failures = sweep_invariant_failures(report)
        results[str(scale)] = {
            "sources": scale,
            "evaluated": report["evaluated_sources"],
            "sweep_ms": round(elapsed_ms, 1),
            "per_source_ms": round(elapsed_ms / max(scale, 1), 4),
            "fleet_fact_computations": fleet,
            "total_fleet_computations": total_fleet,
            "counts_by_state": report["counts_by_state"],
            "invariant_failures": failures,
            "errors": report["errors"],
        }
    out["scales"] = results

    # ---- THE invariant ----------------------------------------------
    # Fleet computations must not grow with the population. Measured as a
    # count, not inferred from a curve.
    out["fleet_computations_by_scale"] = fleet_counts
    out["fleet_facts_are_o1_per_sweep"] = len(set(fleet_counts.values())) == 1
    out["fleet_computations_per_sweep"] = sorted(set(fleet_counts.values()))

    # Had the hoist not happened, this would be 2 x sources.
    out["computations_avoided_at_5000"] = (
        5000 * max(fleet_counts.values()) - max(fleet_counts.values())
        if fleet_counts
        else 0
    )

    out["all_scales_invariant_clean"] = all(
        not results[str(scale)]["invariant_failures"] for scale in SCALES
    )
    out["synthetic_sources_are_only_registered"] = all(
        results[str(scale)]["counts_by_state"]["registered"] == scale
        for scale in SCALES
    )
    out["no_synthetic_source_became_authorized"] = all(
        results[str(scale)]["counts_by_state"]["live_opted_in"] == 0
        and results[str(scale)]["counts_by_state"]["authorized_for_live"] == 0
        for scale in SCALES
    )
finally:
    session.close()

socket.socket = _real_socket  # type: ignore[misc,assignment]
out["network_attempts_during_this_phase"] = _NETWORK["attempts"]
out["rows_written"] = 0
out["not_measured"] = [
    "fact resolution cost at millions of payload and attempt rows",
    "concurrent worker contention",
    "any database engine other than the configured one",
]
print(json.dumps(out, sort_keys=True, default=str))
