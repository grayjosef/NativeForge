"""Gate 165C: measured scale hot spots. Reads only; no network, no writes.

"The registry is re-read per call" is a claim; a count is a measurement. So is
"one authorization is expensive" - and knowing WHICH part is expensive is what
turns it into a recommendation rather than a complaint.

The projection arithmetic is deliberately explicit. An earlier version of this
probe multiplied the WHOLE per-source cost by the registry growth factor and
produced 12.7 hours for a 5,000-source sweep. That was wrong: registry growth
only inflates the CSV-parse component, which is under 2% of the per-source
cost. The corrected model is below, with each component named.
"""

from __future__ import annotations

import cProfile
import io
import json
import pstats
import sys
import time
import uuid

sys.path.insert(0, "src")
sys.path.insert(0, ".")

import nativeforge.services.source_monitoring_approved_source_service as registry  # noqa: E402

calls = {"n": 0}
_original = registry.load_registry_rows


def _counted():
    calls["n"] += 1
    return _original()


registry.load_registry_rows = _counted

from nativeforge.db.session import SessionLocal  # noqa: E402
from nativeforge.services.source_live_authorization_service import (  # noqa: E402
    authorize_source_for_live_access,
)

DEMO = uuid.UUID("bbbbbbbb-cccc-dddd-eeee-ffffffffffff")
AUTHORIZED = "nf-seed-2026-api-grants-gov-search2"

out: dict[str, object] = {}
session = SessionLocal()
try:
    rows = _original()
    out["registry_rows"] = len(rows)

    start = time.perf_counter()
    for _ in range(20):
        _original()
    parse_ms = (time.perf_counter() - start) / 20 * 1000
    out["one_csv_parse_ms"] = round(parse_ms, 3)

    calls["n"] = 0
    start = time.perf_counter()
    authorize_source_for_live_access(
        connection=session, organization_id=DEMO, source_id=AUTHORIZED
    )
    one_ms = (time.perf_counter() - start) * 1000
    out["registry_parses_per_authorization"] = calls["n"]
    out["one_authorization_ms"] = round(one_ms, 1)
    out["csv_share_of_one_authorization_ms"] = round(parse_ms * calls["n"], 2)
    out["csv_share_pct"] = round(parse_ms * calls["n"] / max(one_ms, 0.001) * 100, 1)

    # ---- where does the rest of the time go? --------------------------
    profiler = cProfile.Profile()
    profiler.enable()
    authorize_source_for_live_access(
        connection=session, organization_id=DEMO, source_id=AUTHORIZED
    )
    profiler.disable()
    stream = io.StringIO()
    pstats.Stats(profiler, stream=stream).sort_stats("cumulative").print_stats(14)
    lines = [
        line.strip()
        for line in stream.getvalue().splitlines()
        if "nativeforge" in line or "sqlalchemy" in line
    ]
    out["hot_frames"] = lines[:10]

    # ---- the corrected projection --------------------------------------
    fixed_ms = one_ms - (parse_ms * calls["n"])  # everything but the CSV
    out["non_csv_per_source_ms"] = round(fixed_ms, 1)

    def sweep_seconds(source_count: int) -> float:
        # CSV parse scales with registry size; the rest is per-source work
        # that does not grow with the registry.
        grown_parse = parse_ms * (source_count / max(len(rows), 1))
        per_source = fixed_ms + grown_parse * calls["n"]
        return round(per_source * source_count / 1000, 1)

    out["projected_full_sweep_seconds"] = {
        "10_sources": sweep_seconds(10),
        "100_sources": sweep_seconds(100),
        "1000_sources": sweep_seconds(1000),
        "5000_sources": sweep_seconds(5000),
    }
    out["projection_model"] = (
        "per_source = (authorization cost excluding CSV) + "
        "(CSV parse scaled to registry size) * (parses per authorization). "
        "Only the CSV component grows with the registry; the rest is per-source "
        "work. Measured on a 178-row registry against a database holding 2 "
        "payloads and 1 attempt - the fact-resolution cost will grow with "
        "collection volume too, which this model does NOT capture and which is "
        "reported as UNKNOWN."
    )
    out["what_this_does_not_measure"] = [
        "fact-resolution cost as payload and attempt tables grow to millions",
        "concurrent worker contention",
        "SQLite write-lock behaviour under parallel collection",
        "any production database engine",
    ]
finally:
    session.close()

print(json.dumps(out, indent=2, sort_keys=True))
