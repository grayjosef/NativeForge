"""Gate 170O: change intelligence health against the real graph. No network.

Backfills change events first - idempotently - because the write path types
changes when it CREATES a version, so anything written before Gate 170 has
none.

Six conditions cannot be read from a row. They are passed in from the phases
that measured them, and this phase names which those are rather than deriving
them from whatever happens to be stored.
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
        raise OSError("gate170 makes no network request")


PYTHON = ".venv/bin/python"


def phase(path: str) -> dict:
    proc = subprocess.run(  # noqa: S603
        [PYTHON, path], capture_output=True, text=True, timeout=5400
    )
    line = proc.stdout.strip().splitlines()[-1] if proc.stdout.strip() else ""
    try:
        return json.loads(line)
    except Exception:  # noqa: BLE001
        return {"phase_did_not_report": True, "stderr": proc.stderr[-300:]}


semantics = phase("scripts/_g170_phase_semantics.py")
rebuild = phase("scripts/_g170_phase_rebuild.py")
scale = phase("scripts/_g170_phase_scale.py")

socket.socket = _Refused  # type: ignore[misc,assignment]

from nativeforge.db.session import SessionLocal  # noqa: E402
from nativeforge.repositories.opportunity_change_repository import (  # noqa: E402
    backfill_change_events,
)
from nativeforge.services.opportunity_change_read_model_service import (  # noqa: E402
    HEALTH_CONDITIONS,
    build_change_health,
    build_customer_change_feed,
    change_health_invariant_failures,
    read_model_invariant_failures,
)

upstream_network = (
    int(semantics.get("network_attempts_during_this_phase") or 0)
    + int(rebuild.get("network_attempts_during_this_phase") or 0)
    + int(scale.get("network_attempts_during_this_phase") or 0)
)

diff_deterministic = bool(
    semantics.get("d_direction_produces_different_types")
    and semantics.get("d_every_case_named_a_rule")
    and semantics.get("e_shape_travels_with_the_event")
)
events_idempotent = bool(
    semantics.get("l_replay_is_a_true_noop")
    and semantics.get("l_noop_inserted_nothing")
    and rebuild.get("second_rebuild_wrote_nothing")
)
amendment_not_recurrence = bool(
    semantics.get("f_amendment_same_canonical")
    and semantics.get("f_amendment_created_no_new_canonical")
    and semantics.get("f_recurrence_is_a_different_canonical")
)
corroboration = bool(semantics.get("h_one_semantic_event_not_two"))
unchanged_noop = bool(scale.get("unchanged_observation_noop"))
replay_deterministic = bool(rebuild.get("rebuild_is_deterministic"))

out: dict[str, object] = {
    "measured_inputs": {
        "diff_deterministic": diff_deterministic,
        "change_events_idempotent": events_idempotent,
        "amendment_not_recurrence": amendment_not_recurrence,
        "multi_source_corroboration_supported": corroboration,
        "unchanged_observation_noop": unchanged_noop,
        "replay_deterministic": replay_deterministic,
    },
    "input_sources": {
        "diff_deterministic": "_g170_phase_semantics.py",
        "change_events_idempotent": "_g170_phase_semantics.py + _g170_phase_rebuild.py",
        "amendment_not_recurrence": "_g170_phase_semantics.py",
        "multi_source_corroboration_supported": "_g170_phase_semantics.py",
        "unchanged_observation_noop": "_g170_phase_scale.py",
        "replay_deterministic": "_g170_phase_rebuild.py",
    },
    "upstream_phase_network_attempts": upstream_network,
}

session = SessionLocal()
try:
    out["change_backfill"] = backfill_change_events(connection=session)

    health = build_change_health(
        connection=session,
        diff_deterministic=diff_deterministic,
        events_idempotent=events_idempotent,
        amendment_not_recurrence=amendment_not_recurrence,
        corroboration_supported=corroboration,
        unchanged_noop=unchanged_noop,
        replay_deterministic=replay_deterministic,
        network_requests=upstream_network,
    )
    out["change_intelligence_ready"] = health["change_intelligence_ready"]
    out["conditions"] = health["conditions"]
    out["named_gaps"] = health["named_gaps"]
    out["notes"] = health["notes"]
    out["health_invariant_failures"] = change_health_invariant_failures(health)
    out["conditions_measured"] = len(health["conditions"])
    out["every_condition_in_the_vocabulary"] = sorted(health["conditions"]) == sorted(
        HEALTH_CONDITIONS
    )

    # ---- negative controls on the health judgement itself -------------
    forged = dict(health)
    forged["conditions"] = dict(health["conditions"])
    forged["conditions"]["materiality_rules_named"] = False
    forged["change_intelligence_ready"] = True
    out["forged_readiness_is_caught"] = bool(
        change_health_invariant_failures(forged)
    )

    unmeasured = build_change_health(connection=session)
    out["unmeasured_conditions_are_named_not_assumed"] = bool(
        not unmeasured["change_intelligence_ready"]
        and any("was_not_measured" in g for g in unmeasured["named_gaps"])
    )

    # ---- the customer-safe feed over the REAL graph -------------------
    feed = build_customer_change_feed(connection=session, limit=25)
    out["customer_feed_count"] = feed["change_count"]
    out["customer_safe"] = feed["customer_safe"]
    out["forbidden_markers_found"] = feed["forbidden_markers_found"]
    out["read_model_invariant_failures"] = read_model_invariant_failures(feed)
    out["notifications_sent"] = feed["notifications_sent"]
finally:
    session.close()

socket.socket = _real_socket  # type: ignore[misc,assignment]
out["network_attempts_during_this_phase"] = _NETWORK["attempts"]
print(json.dumps(out, sort_keys=True, default=str))
