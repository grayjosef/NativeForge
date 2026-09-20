"""Gate 166 phase: the live evidence is unchanged, and still authorized.

Gate 166 rewired how authorization is DERIVED. The one real live collection
must come through that change untouched: same bytes, same hash, same single
attempt, and still traceable to an authorization - now a derived one.

The check that matters is not "are there zero unauthorized rows" in isolation.
Before Gate 163 that was true because nothing live had ever happened, and a
verifier that cannot tell those apart has stopped measuring its claim. So each
live row is traced to the derived authorized set, and the count of live rows is
asserted to be NON-zero as well - a phase reporting "0 unauthorized" about 0
rows proves nothing.

Makes no network request.
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

import sqlalchemy as sa  # noqa: E402

from nativeforge.db.session import SessionLocal  # noqa: E402
from nativeforge.services.source_authority_service import (  # noqa: E402
    derive_authorized_source_ids,
)

DEMO = uuid.UUID("bbbbbbbb-cccc-dddd-eeee-ffffffffffff")

#: Everything Gate 163 collected over the wire. Pinned as literals: if Gate
#: 166 disturbed the evidence, comparing it against itself would not notice.
#:
#: BOTH rows, named. The first draft pinned only the search2 collection and
#: reported the evidence changed - because the robots preflight is also a live
#: fetch and also carries an authorization. A pin that describes part of a
#: population fails honestly, which is how this was caught, but it was the
#: instrument that was wrong and not the data.
EXPECTED_LIVE_EVIDENCE: dict[str, int] = {
    # the search2 collection
    "eb4cc7cb76d278b9f4ab9aad7375ed0481faa6ff5827786452dc74491c0f1712": 11131,
    # the robots.txt preflight - 403, which RFC 9309 2.3.1 reads as unavailable
    "f249b63cb2fcb66b47e86f906c98f8fd912e82dd035b4e53d7e72fc1960cfd16": 42,
}

out: dict[str, object] = {}
session = SessionLocal()
try:
    authorized = derive_authorized_source_ids(connection=session, organization_id=DEMO)
    out["derived_authorized_source_ids"] = sorted(authorized)

    payloads = (
        session.execute(
            sa.text(
                "SELECT source_id, authorized_source_id, payload_sha256, "
                "payload_size_bytes, live_fetch_performed "
                "FROM nf_source_collection_raw_payloads "
                "WHERE live_fetch_performed = 1"
            )
        )
        .mappings()
        .all()
    )
    attempts = (
        session.execute(
            sa.text(
                "SELECT source_id, authorized_source_id, transport_kind, "
                "raw_payload_sha256, bytes_received "
                "FROM nf_source_collection_execution_attempts "
                "WHERE transport_kind = 'live'"
            )
        )
        .mappings()
        .all()
    )

    out["live_payload_rows"] = len(payloads)
    out["live_attempts"] = len(attempts)

    # A row with no authorized_source_id, or one naming a source the DATA does
    # not authorize, is unauthorized. Both shapes are counted.
    unauthorized_rows = [
        dict(row)
        for row in payloads
        if not row.get("authorized_source_id")
        or str(row.get("authorized_source_id")) not in authorized
    ]
    unauthorized_attempts = [
        dict(row)
        for row in attempts
        if not row.get("authorized_source_id")
        or str(row.get("authorized_source_id")) not in authorized
    ]
    out["unauthorized_live_rows"] = len(unauthorized_rows)
    out["unauthorized_live_attempts"] = len(unauthorized_attempts)

    # "Zero unauthorized" is only meaningful over a non-empty population.
    out["live_evidence_exists"] = bool(payloads) and bool(attempts)
    out["every_live_row_traces_to_a_derived_authorization"] = bool(
        payloads
        and attempts
        and not unauthorized_rows
        and not unauthorized_attempts
    )

    observed = {
        str(row.get("payload_sha256") or ""): int(row.get("payload_size_bytes") or 0)
        for row in payloads
    }
    out["live_payload_sha256"] = sorted(observed)
    out["live_payload_bytes"] = sorted(observed.values())
    # Hash AND size, per row. Matching the set of hashes alone would miss a
    # row whose recorded size drifted from the bytes it names.
    out["live_evidence_unchanged_by_gate166"] = observed == EXPECTED_LIVE_EVIDENCE
    out["live_evidence_expected"] = EXPECTED_LIVE_EVIDENCE
    out["live_evidence_observed"] = observed
finally:
    session.close()

socket.socket = _real_socket  # type: ignore[misc,assignment]
out["network_attempts_during_this_phase"] = _NETWORK["attempts"]
out["rows_written"] = 0
print(json.dumps(out, sort_keys=True, default=str))
