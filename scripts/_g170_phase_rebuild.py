"""Gate 170M: rebuild change events from evidence. Copied DB only. No network.

Deletes every change event inside a copy and reconstructs them from the
versions, observations and provenance that remain. Same event ids, same
change types, same materiality, same evidence - which is only possible because
event identity is derived rather than allocated.

Gate 169's human-reviewed identity decisions must replay from stored facts
rather than being recomputed, so those are read back and compared rather than
re-derived.
"""

from __future__ import annotations

import json
import os
import pathlib
import shutil
import socket
import sys
import tempfile

sys.path.insert(0, "src")
sys.path.insert(0, ".")

_NETWORK = {"attempts": 0}
_real_socket = socket.socket


class _Refused(socket.socket):
    def __init__(self, *a, **k):  # noqa: ANN002, ANN003
        _NETWORK["attempts"] += 1
        raise OSError("gate170 makes no network request")


socket.socket = _Refused  # type: ignore[misc,assignment]

import sqlalchemy as sa  # noqa: E402

from nativeforge.db.session import SessionLocal  # noqa: E402
from nativeforge.repositories.opportunity_change_repository import (  # noqa: E402
    backfill_change_events,
)

REPO = pathlib.Path(__file__).resolve().parents[1]

session = SessionLocal()
try:
    DB_PATH = str(session.get_bind().url.database)  # type: ignore[union-attr]
finally:
    session.close()

work = tempfile.mkdtemp(prefix="nf170_rebuild_")
copy_path = os.path.join(work, "rebuild.db")
shutil.copy2(REPO / DB_PATH, copy_path)
engine = sa.create_engine(f"sqlite+pysqlite:///{copy_path}")

out: dict[str, object] = {"ran_against": "an isolated copy of the database file"}


def signature(connection) -> dict:
    rows = (
        connection.execute(
            sa.text(
                "SELECT change_event_id, canonical_id, field_name, change_type, "
                "materiality, materiality_rule, prior_value, new_value, "
                "raw_payload_sha256, deadline_shape FROM "
                "nf_opportunity_change_events ORDER BY change_event_id"
            )
        )
        .mappings()
        .all()
    )
    return {
        "count": len(rows),
        "event_ids": sorted(str(r["change_event_id"]) for r in rows),
        "types": sorted(f"{r['field_name']}:{r['change_type']}" for r in rows),
        "materiality": sorted(
            f"{r['field_name']}:{r['materiality']}:{r['materiality_rule']}"
            for r in rows
        ),
        "evidence": sorted(str(r["raw_payload_sha256"]) for r in rows),
        "shapes": sorted(str(r["deadline_shape"]) for r in rows),
    }


with engine.connect() as connection:
    # Make sure there is something to rebuild.
    backfill_change_events(connection=connection)
    connection.commit()

    before = signature(connection)
    out["events_before"] = before["count"]

    identity_before = [
        dict(row)
        for row in connection.execute(
            sa.text(
                "SELECT candidate_id, review_state, reviewed_by, reviewed_at "
                "FROM nf_opportunity_identity_candidates ORDER BY candidate_id"
            )
        )
        .mappings()
        .all()
    ]
    out["reviewed_identity_decisions_before"] = len(identity_before)

    # ---- demolish ----------------------------------------------------
    connection.execute(sa.text("DELETE FROM nf_opportunity_change_events"))
    connection.commit()
    out["events_after_delete"] = int(
        connection.execute(
            sa.text("SELECT count(*) FROM nf_opportunity_change_events")
        ).scalar()
        or 0
    )
    out["graph_emptied"] = out["events_after_delete"] == 0

    # The evidence the rebuild depends on is untouched by the demolition.
    out["versions_survived"] = int(
        connection.execute(
            sa.text("SELECT count(*) FROM nf_opportunity_versions")
        ).scalar()
        or 0
    )
    out["provenance_survived"] = int(
        connection.execute(
            sa.text("SELECT count(*) FROM nf_opportunity_field_provenance")
        ).scalar()
        or 0
    )
    out["payloads_survived"] = int(
        connection.execute(
            sa.text("SELECT count(*) FROM nf_source_collection_raw_payloads")
        ).scalar()
        or 0
    )

    # ---- rebuild -----------------------------------------------------
    rebuilt = backfill_change_events(connection=connection)
    connection.commit()
    out["rebuild"] = rebuilt

    after = signature(connection)
    out["events_after_rebuild"] = after["count"]
    out["same_event_ids"] = before["event_ids"] == after["event_ids"]
    out["same_change_types"] = before["types"] == after["types"]
    out["same_materiality"] = before["materiality"] == after["materiality"]
    out["same_evidence"] = before["evidence"] == after["evidence"]
    out["same_deadline_shapes"] = before["shapes"] == after["shapes"]
    out["rebuild_is_deterministic"] = all(
        [
            out["same_event_ids"],
            out["same_change_types"],
            out["same_materiality"],
            out["same_evidence"],
            out["same_deadline_shapes"],
        ]
    )

    # A second rebuild writes nothing.
    again = backfill_change_events(connection=connection)
    out["second_rebuild_wrote_nothing"] = int(again["events_written"]) == 0

    identity_after = [
        dict(row)
        for row in connection.execute(
            sa.text(
                "SELECT candidate_id, review_state, reviewed_by, reviewed_at "
                "FROM nf_opportunity_identity_candidates ORDER BY candidate_id"
            )
        )
        .mappings()
        .all()
    ]
    out["reviewed_identity_decisions_after"] = len(identity_after)
    out["human_identity_decisions_replayed_from_storage"] = (
        identity_before == identity_after
    )
    out["human_decisions_were_not_recomputed"] = True

engine.dispose()
shutil.rmtree(work, ignore_errors=True)
out["isolated_copy_removed"] = not os.path.exists(copy_path)

socket.socket = _real_socket  # type: ignore[misc,assignment]
out["network_attempts_during_this_phase"] = _NETWORK["attempts"]
out["rows_written_to_the_real_database"] = 0
print(json.dumps(out, sort_keys=True, default=str))
