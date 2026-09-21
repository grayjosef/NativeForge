"""Gate 169S: identity health against the real graph. Reads only, no network.

Backfills blocking keys first - idempotently - because the write path only
builds them when it CREATES an opportunity, so anything that existed before
Gate 169 has none. Then judges the graph.

The three conditions that cannot be read from a row are passed in from the
phases that measured them, and this phase says which those are rather than
inventing them.
"""

from __future__ import annotations

import json
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
        raise OSError("gate169 makes no network request")


PYTHON = ".venv/bin/python"


def phase(path: str) -> dict:
    """Run a phase and read its last line. Before the socket is blocked."""
    proc = subprocess.run(  # noqa: S603
        [PYTHON, path], capture_output=True, text=True, timeout=3600
    )
    line = proc.stdout.strip().splitlines()[-1] if proc.stdout.strip() else ""
    try:
        return json.loads(line)
    except Exception:  # noqa: BLE001
        return {"phase_did_not_report": True, "stderr": proc.stderr[-300:]}


# The measured inputs, gathered before this process refuses sockets - the
# subprocesses block their own.
decisions = phase("scripts/_g169_phase_decisions.py")
scale = phase("scripts/_g169_phase_scale.py")
graph = phase("scripts/_g169_phase_graph.py")

socket.socket = _Refused  # type: ignore[misc,assignment]

from nativeforge.db.session import SessionLocal  # noqa: E402
from nativeforge.repositories.opportunity_identity_repository import (  # noqa: E402
    backfill_blocking_keys,
)
from nativeforge.services.identity_resolution_health_service import (  # noqa: E402
    HEALTH_CONDITIONS,
    build_identity_health,
    identity_health_invariant_failures,
)

controls_clean = bool(
    decisions.get("all_decisions_as_expected")
    and decisions.get("no_silent_merge")
    and decisions.get("every_decision_named_a_reason")
    and decisions.get("all_invariants_clean")
)
bounded = bool(scale.get("no_n_squared_scan"))
replay = bool(
    graph.get("r_derived_decision_replays_identically")
    and graph.get("r_human_decision_is_persisted_not_recomputed")
)

out: dict[str, object] = {
    "measured_inputs": {
        "false_positive_controls_clean": controls_clean,
        "candidate_generation_bounded": bounded,
        "identity_replay_deterministic": replay,
    },
    "input_sources": {
        "false_positive_controls_clean": "_g169_phase_decisions.py",
        "candidate_generation_bounded": "_g169_phase_scale.py",
        "identity_replay_deterministic": "_g169_phase_graph.py",
    },
}

session = SessionLocal()
try:
    out["blocking_backfill"] = backfill_blocking_keys(connection=session)
    health = build_identity_health(
        connection=session,
        controls_clean=controls_clean,
        candidate_generation_bounded=bounded,
        replay_deterministic=replay,
    )
    out["identity_resolution_ready"] = health["identity_resolution_ready"]
    out["conditions"] = health["conditions"]
    out["named_gaps"] = health["named_gaps"]
    out["notes"] = health["notes"]
    out["health_invariant_failures"] = identity_health_invariant_failures(health)
    out["conditions_measured"] = len(health["conditions"])
    out["every_condition_in_the_vocabulary"] = sorted(health["conditions"]) == sorted(
        HEALTH_CONDITIONS
    )

    # ---- a NEGATIVE control on the health judgement itself ----------
    #
    # A health service that cannot be caught claiming readiness is a health
    # service nobody has tested.
    forged = dict(health)
    forged["conditions"] = dict(health["conditions"])
    forged["conditions"]["no_illegal_l4_settled_merges"] = False
    forged["identity_resolution_ready"] = True
    out["forged_readiness_is_caught"] = bool(
        identity_health_invariant_failures(forged)
    )

    unmeasured = build_identity_health(
        connection=session,
        controls_clean=None,
        candidate_generation_bounded=None,
        replay_deterministic=None,
    )
    out["unmeasured_conditions_are_named_not_assumed"] = bool(
        not unmeasured["identity_resolution_ready"]
        and any("was_not_measured" in g for g in unmeasured["named_gaps"])
    )
finally:
    session.close()

socket.socket = _real_socket  # type: ignore[misc,assignment]
out["network_attempts_during_this_phase"] = _NETWORK["attempts"]
out["upstream_phase_network_attempts"] = {
    "decisions": decisions.get("network_attempts_during_this_phase"),
    "scale": scale.get("network_attempts_during_this_phase"),
    "graph": graph.get("network_attempts_during_this_phase"),
}
print(json.dumps(out, sort_keys=True, default=str))
