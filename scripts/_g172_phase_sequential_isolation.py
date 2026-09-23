"""Gate 172AD: one health run must not decide the next one's answer.

Gate 171 produced a lineage failure that passed standalone, failed in the
battery, and never reproduced. Four mechanisms were ruled out with evidence
and the root cause was NOT found - that remains an open unknown and is not
rewritten here.

What that episode did establish is the shape of the risk: a phase that runs
against inherited state can describe leftovers while looking like it described
what it just did. So this phase proves the source-health equivalent directly.

```text
fixture A  ->  cleanup A owns  ->  fixture B
```

B's health must equal standalone B, field for field. Each run is a SEPARATE
PROCESS, because in-process reuse shares SQLAlchemy state and ContextVars -
exactly the contamination this exists to detect.

It also runs the Gate 171 verifier's own isolation phase, so the carried-
forward `sequential_lineage_isolation` fact is measured here rather than
quoted from a previous gate.
"""

from __future__ import annotations

import json
import pathlib
import socket
import subprocess
import sys

sys.path.insert(0, "src")
sys.path.insert(0, ".")

_NETWORK = {"attempts": 0}
_real_socket = socket.socket


class _Refused(socket.socket):
    def __init__(self, *a, **k):  # noqa: ANN002, ANN003
        _NETWORK["attempts"] += 1
        raise OSError("gate172 sequential isolation makes no network request")


socket.socket = _Refused  # type: ignore[misc,assignment]

REPO = pathlib.Path(__file__).resolve().parents[1]
PYTHON = str(REPO / ".venv" / "bin" / "python")

#: A tiny driver that computes one fixture's health in its own interpreter.
#: Written to a temp file rather than imported, so nothing is shared.
DRIVER = '''
import datetime as dt
import json
import os
import sys

os.chdir(__REPO__)
sys.path.insert(0, "src")

from nativeforge.services.source_fleet_read_model_service import (
    build_fleet_health,
    build_source_row,
)

FIXTURES = {
    "A": dict(
        source_id="nf172.iso.a",
        adapter_key="federal_register_documents_json",
        authorization_state="live_opted_in",
        activation_state="activated",
        consecutive_failures=0,
        payload_count=1,
        observation_count=20,
        canonical_count=20,
        robots_body_retained=True,
        records_read=20,
        previous_record_counts=[20, 21, 19, 20],
    ),
    "B": dict(
        source_id="nf172.iso.b",
        adapter_key="bia_program_page_html",
        authorization_state="live_opted_in",
        activation_state="activated",
        consecutive_failures=2,
        payload_count=1,
        observation_count=1,
        canonical_count=1,
        robots_body_retained=False,
        records_read=1,
        previous_record_counts=[1, 1, 1, 1],
    ),
}

now = dt.datetime(2026, 9, 23, 12, 0, tzinfo=dt.UTC)
which = sys.argv[1]
row = build_source_row(
    last_attempt_at=now - dt.timedelta(hours=1),
    last_success_at=now - dt.timedelta(hours=1),
    last_payload_at=now - dt.timedelta(hours=1),
    last_observation_at=now - dt.timedelta(hours=1),
    last_useful_change_at=now - dt.timedelta(hours=2),
    now=now,
    fleet_globals={
        "backlog_health": "ok",
        "scheduler_health": "ok",
        "worker_health": "ok",
    },
    **FIXTURES[which],
)
fleet = build_fleet_health(rows=[row], computed_at=now, now=now, registered_sources=1)
# Only the facts that must be stable. Timestamps of the RUN are not among them.
print(json.dumps({
    "source_id": row["source_id"],
    "operational_state": row["operational_state"],
    "dimensions": {k: v for k, v in row.items() if k.endswith("_health")},
    "known_gaps": row["known_gaps"],
    "counts_by_state": fleet["counts_by_state"],
    "self_health_ok": fleet["self_health_ok"],
}, sort_keys=True))
'''.replace("__REPO__", repr(str(REPO)))


def run_driver(which: str) -> dict:
    """One fixture, one interpreter."""
    import tempfile

    with tempfile.NamedTemporaryFile(
        "w", suffix=".py", delete=False, encoding="utf-8"
    ) as handle:
        handle.write(DRIVER)
        path = handle.name
    try:
        result = subprocess.run(  # noqa: S603
            [PYTHON, path, which],
            cwd=str(REPO),
            capture_output=True,
            text=True,
            timeout=300,
        )
        for line in reversed((result.stdout or "").strip().splitlines()):
            if line.startswith("{"):
                return json.loads(line)
        return {"_no_report": True, "_stderr": (result.stderr or "")[-300:]}
    finally:
        pathlib.Path(path).unlink(missing_ok=True)


def run_phase(script: str) -> dict:
    result = subprocess.run(  # noqa: S603
        [PYTHON, script],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        timeout=1800,
    )
    for line in reversed((result.stdout or "").strip().splitlines()):
        if line.startswith("{"):
            return json.loads(line)
    return {"_no_report": True, "_stderr": (result.stderr or "")[-300:]}


out: dict[str, object] = {"schema_version": "nf_gate172_sequential_isolation_v1"}

# ---- B alone, as the control ---------------------------------------
standalone_b = run_driver("B")

# ---- A, then cleanup, then B ---------------------------------------
sequential_a = run_driver("A")
cleanup = run_phase("scripts/_g167_phase_cleanup.py")
sequential_b = run_driver("B")

out["standalone_b"] = standalone_b
out["sequential_a"] = sequential_a
out["sequential_b"] = sequential_b
out["cleanup_fixture_residue"] = cleanup.get("fixture_residue")
out["cleanup_kept_the_real_opportunity"] = cleanup.get("real_opportunity_present")

differences = sorted(
    key
    for key in set(standalone_b) | set(sequential_b)
    if standalone_b.get(key) != sequential_b.get(key)
)
out["differing_fields"] = differences
out["b_is_identical_after_a"] = not differences
out["a_and_b_are_different_fixtures"] = (
    sequential_a.get("operational_state") != sequential_b.get("operational_state")
    or sequential_a.get("known_gaps") != sequential_b.get("known_gaps")
)
out["each_run_was_a_separate_process"] = True

# ---- Gate 171's own isolation, measured not quoted ------------------
lineage = run_phase("scripts/_g171_phase_sequential_isolation.py")
out["gate171_lineage_phase"] = {
    key: lineage.get(key)
    for key in (
        "sequential_lineage_isolation",
        "both_positions_started_clean",
        "both_positions_agree",
        "disagreeing_facts",
        "final_fixture_residue",
    )
}
out["sequential_lineage_isolation"] = bool(
    lineage.get("sequential_lineage_isolation")
)
out["gate171_root_cause"] = (
    "UNKNOWN - four mechanisms ruled out with evidence in Gate 171 and the "
    "cause was never identified. This gate measures the regression, it does "
    "not claim the cause was found."
)

out["source_health_sequential_isolation"] = bool(
    out["b_is_identical_after_a"]
    and out["a_and_b_are_different_fixtures"]
    and int(out["cleanup_fixture_residue"] or 0) == 0
    and out["sequential_lineage_isolation"]
)

socket.socket = _real_socket  # type: ignore[misc,assignment]
out["network_attempts_during_this_phase"] = _NETWORK["attempts"]
print(json.dumps(out, sort_keys=True, default=str))
