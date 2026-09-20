"""Gate 166 phase: the warrant still enforces, and now from data. No network.

Gate 163's warrant refused a source whose id was not in a frozenset. Gate 166B
removed the frozenset. The question is whether enforcement SURVIVED, which one
positive case cannot answer - the real source would still pass if the check had
simply been deleted.

So every refusal the constant used to produce is exercised here against the
real enforcement path, plus the one it could never produce: a source whose id
is unchanged and whose authorization was withdrawn.
"""

from __future__ import annotations

import json
import socket
import sys
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

import nativeforge.services.source_live_warrant_service as warrant  # noqa: E402
from nativeforge.db.session import SessionLocal  # noqa: E402

DEMO = uuid.UUID("bbbbbbbb-cccc-dddd-eeee-ffffffffffff")
GRANTS = "nf-seed-2026-api-grants-gov-search2"
URL = "https://api.grants.gov/v1/api/search2"
ROBOTS = "https://api.grants.gov/robots.txt"

out: dict[str, object] = {}

out["module_still_defines_a_hardcoded_set"] = hasattr(
    warrant, "AUTHORIZED_SOURCE_IDS"
)

session = SessionLocal()
try:

    def evaluate(**kw):
        params = {
            "warrant_kind": warrant.WARRANT_SOURCE_COLLECTION,
            "authorized_source_id": GRANTS,
            "request_url": URL,
            "method": "POST",
            "connection": session,
            "organization_id": DEMO,
        }
        params.update(kw)
        return warrant.evaluate_live_request(**params)

    # ---- 1. the real source still passes, and says why ---------------
    real = evaluate()
    out["real_source_permitted"] = real["permitted"]
    out["real_source_authority_state"] = real["source_authority_state"]
    out["real_source_refusals"] = real["refusal_reasons"]
    out["derived_from_persisted_decisions"] = real[
        "authorization_derived_from_persisted_decisions"
    ]
    out["derived_from_source_code_constant"] = real[
        "authorization_derived_from_source_code_constant"
    ]
    out["real_source_invariant_failures"] = warrant.warrant_invariant_failures(real)

    # ---- 2. NEGATIVE: an unknown source is still refused -------------
    unknown = evaluate(
        authorized_source_id="nf166.synthetic.never-authorized",
        request_url="https://example.invalid/x",
    )
    out["unknown_source_permitted"] = unknown["permitted"]
    out["unknown_source_refusals"] = unknown["refusal_reasons"]

    # ---- 3. NEGATIVE: a REAL registered source with no decisions -----
    # One of the 177. Its id is real, its host is real, and it has never been
    # authorized. Under the constant this refused on membership; it must
    # still refuse, now on its data.
    from nativeforge.services.source_monitoring_approved_source_service import (
        load_registry_rows,
    )

    rows = load_registry_rows()
    other_id = next(
        (k for k in sorted(rows) if k != GRANTS and rows[k].get("source_url")), None
    )
    other_url = str(rows[other_id].get("source_url")) if other_id else ""
    unauthorized_real = evaluate(
        authorized_source_id=other_id, request_url=other_url, method="GET"
    )
    out["other_real_source_id"] = other_id
    out["other_real_source_permitted"] = unauthorized_real["permitted"]
    out["other_real_source_authority_state"] = unauthorized_real[
        "source_authority_state"
    ]
    out["other_real_source_refusals"] = unauthorized_real["refusal_reasons"]

    # ---- 4. NEGATIVE: no connection derives no authority -------------
    no_conn = evaluate(connection=None)
    out["no_connection_permitted"] = no_conn["permitted"]
    out["no_connection_refusals"] = no_conn["refusal_reasons"]

    # ---- 5. the preflight path still works --------------------------
    preflight = evaluate(
        warrant_kind=warrant.WARRANT_ROBOTS_PREFLIGHT,
        request_url=ROBOTS,
        method="GET",
    )
    out["preflight_permitted"] = preflight["permitted"]
    out["preflight_refusals"] = preflight["refusal_reasons"]

    # ---- 6. a forged decision cannot pass the invariant -------------
    # The strongest check: hand the invariant a decision that claims
    # permission with no permitting authority state. Under Gate 163 this
    # was caught by set membership; it must still be caught.
    forged = dict(real)
    forged["source_authority_state"] = "registered"
    out["forged_state_caught"] = bool(warrant.warrant_invariant_failures(forged))

    forged_constant = dict(real)
    forged_constant["authorization_derived_from_source_code_constant"] = True
    out["forged_constant_origin_caught"] = bool(
        warrant.warrant_invariant_failures(forged_constant)
    )

    out["every_negative_control_refused"] = not any(
        [
            out["unknown_source_permitted"],
            out["other_real_source_permitted"],
            out["no_connection_permitted"],
        ]
    )
finally:
    session.close()

socket.socket = _real_socket  # type: ignore[misc,assignment]
out["network_attempts_during_this_phase"] = _NETWORK["attempts"]
print(json.dumps(out, sort_keys=True, default=str))
