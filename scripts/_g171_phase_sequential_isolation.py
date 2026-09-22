"""Gate 171G: one verifier's leftovers must not decide another's answer.

Gate 171's battery produced a lineage failure in Gate 168 that passed
standalone, passed inside Gate 167, and did not reproduce afterwards. Four
mechanisms were tested and rejected with evidence: the 0056 index regression
(the sequence passes on the pre-0057 schema), cleanup orphans (zero dangling
pointers, zero orphan versions, counts consistent), replay on accumulated
state (the chain held across repeated runs), and created_at ties (microsecond
timestamps, distinct).

What the investigation DID establish is that the phase had no way to say what
state it started from, so a failure could not be told apart from a stale
fixture after the fact. That is the gap this phase closes permanently.

It encodes the battery's shape without the two-hour suite:

```text
167 owns its setup and its cleanup   ->  168 sets up the same fixture again
                                          and asserts lineage
```

Both runs must start clean, both chains must be well-formed, and the
supersession links must agree with the timestamp order. A failure here names
which of those broke instead of leaving a bare False.

Writes fixture rows and removes them through the cleanup phase that owns them.
No network.
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
        raise OSError("gate171 sequential isolation makes no network request")


socket.socket = _Refused  # type: ignore[misc,assignment]

REPO = pathlib.Path(__file__).resolve().parents[1]
PYTHON = str(REPO / ".venv" / "bin" / "python")

CLEANUP = "scripts/_g167_phase_cleanup.py"
FIRST_WRITE = "scripts/_g167_phase_first_write.py"
SEMANTICS = "scripts/_g167_phase_graph_semantics.py"

#: The lineage facts that must hold identically in both positions.
LINEAGE_FACTS = (
    "g_started_from_a_clean_fixture",
    "g_previous_versions_retained",
    "g_lineage_is_a_chain",
    "g_current_pointer_is_newest",
    "g_exactly_one_chain_root",
    "g_timestamp_order_matches_supersession_order",
)


def run(script: str) -> dict:
    """Run a phase in its OWN process, as a verifier does.

    In-process reuse would share SQLAlchemy state and ContextVars between the
    two positions, which is precisely the contamination this phase exists to
    detect. A separate interpreter per step is the honest simulation.
    """
    result = subprocess.run(  # noqa: S603
        [PYTHON, script],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        timeout=900,
    )
    last = (result.stdout or "").strip().splitlines()
    for line in reversed(last):
        if line.startswith("{"):
            return json.loads(line)
    return {"_no_report": True, "_stderr": (result.stderr or "")[-400:]}


out: dict[str, object] = {"schema_version": "nf_gate171_sequential_isolation_v1"}

# ---- position 1: as Gate 167 runs it ------------------------------
run(CLEANUP)
run(FIRST_WRITE)
first = run(SEMANTICS)
out["position_1_as_gate167"] = {name: first.get(name) for name in LINEAGE_FACTS}
out["position_1_version_count"] = first.get("g_version_count")

# ---- the cleanup Gate 167 ends with -------------------------------
cleaned = run(CLEANUP)
out["cleanup_rows_removed"] = cleaned.get("rows_removed")
out["cleanup_fixture_residue"] = cleaned.get("fixture_residue")
out["cleanup_kept_the_real_opportunity"] = cleaned.get("real_opportunity_present")

# ---- position 2: as Gate 168 runs it, against 167's leftovers -----
run(FIRST_WRITE)
second = run(SEMANTICS)
out["position_2_as_gate168"] = {name: second.get(name) for name in LINEAGE_FACTS}
out["position_2_version_count"] = second.get("g_version_count")

# ---- the invariant ------------------------------------------------
out["both_positions_started_clean"] = bool(
    first.get("g_started_from_a_clean_fixture")
    and second.get("g_started_from_a_clean_fixture")
)
out["both_positions_agree"] = all(
    first.get(name) == second.get(name) for name in LINEAGE_FACTS
)
out["disagreeing_facts"] = sorted(
    name for name in LINEAGE_FACTS if first.get(name) != second.get(name)
)
out["lineage_holds_in_both_positions"] = all(
    bool(report.get(name))
    for report in (first, second)
    for name in (
        "g_lineage_is_a_chain",
        "g_current_pointer_is_newest",
        "g_exactly_one_chain_root",
        "g_timestamp_order_matches_supersession_order",
    )
)
out["sequential_lineage_isolation"] = bool(
    out["both_positions_started_clean"]
    and out["both_positions_agree"]
    and out["lineage_holds_in_both_positions"]
    and int(out["cleanup_fixture_residue"] or 0) == 0
)

# Leave the graph as this phase found it.
final = run(CLEANUP)
out["final_fixture_residue"] = final.get("fixture_residue")
out["final_real_opportunity_present"] = final.get("real_opportunity_present")

socket.socket = _real_socket  # type: ignore[misc,assignment]
out["network_attempts_during_this_phase"] = _NETWORK["attempts"]
print(json.dumps(out, sort_keys=True, default=str))
