"""Gate 162 verifier phase: remove this run's rows, then count what is left.

THE LAST PHASE. Gate 158 found Gate 157's verifier cleaning up before invoking
a script that committed 100 more rows, and reporting zero residue about a
database that had just gained a hundred. Nothing that writes may run after
this.

`counted_actual_rows` is separate from `residue` on purpose: a cleanup that
reports "0 remaining" because it counted nothing is indistinguishable from one
that removed everything, so the count is taken by SELECTing rows rather than by
trusting the DELETE's own rowcount.

Also asserts the safety counts the gate's final report depends on - real
approved sources, real-source decisions, live attempts - AFTER cleanup, so they
describe the database the commit will be made against.
"""

from __future__ import annotations

import json
import sys
import uuid

sys.path.insert(0, "src")
sys.path.insert(0, ".")

import sqlalchemy as sa  # noqa: E402

from nativeforge.db.session import SessionLocal  # noqa: E402
from nativeforge.services.source_monitoring_approved_source_service import (  # noqa: E402,E501
    load_registry_rows,
)

DEMO = uuid.UUID("bbbbbbbb-cccc-dddd-eeee-ffffffffffff")

FIXTURE_LIKE = "nf162.fixture.%"
ARTIFACT_ID = "nf162-verify-activation"

out: dict[str, object] = {}
detail: list[str] = []
removed = 0
residue = 0
counted = False

session = SessionLocal()
try:
    # ---- remove ------------------------------------------------------
    try:
        result = session.execute(
            sa.text(
                "DELETE FROM nf_source_authorization_decisions "
                "WHERE source_id LIKE :p"
            ),
            {"p": FIXTURE_LIKE},
        )
        removed += int(result.rowcount or 0)
    except Exception as exc:  # noqa: BLE001
        detail.append(f"decisions:{type(exc).__name__}")
        session.rollback()

    try:
        result = session.execute(
            sa.text(
                "DELETE FROM nf_active_opportunity_sources "
                "WHERE activation_approval_artifact_id = :a"
            ),
            {"a": ARTIFACT_ID},
        )
        removed += int(result.rowcount or 0)
    except Exception as exc:  # noqa: BLE001
        detail.append(f"active_sources:{type(exc).__name__}")
        session.rollback()

    session.commit()

    # ---- count, by LOOKING -------------------------------------------
    try:
        residue += int(
            session.execute(
                sa.text(
                    "SELECT count(*) FROM nf_source_authorization_decisions "
                    "WHERE source_id LIKE :p"
                ),
                {"p": FIXTURE_LIKE},
            ).scalar()
            or 0
        )
        residue += int(
            session.execute(
                sa.text(
                    "SELECT count(*) FROM nf_active_opportunity_sources "
                    "WHERE activation_approval_artifact_id = :a"
                ),
                {"a": ARTIFACT_ID},
            ).scalar()
            or 0
        )
        counted = True
    except Exception as exc:  # noqa: BLE001
        detail.append(f"count:{type(exc).__name__}")
        session.rollback()
        counted = False

    # ---- the safety counts, AFTER cleanup ----------------------------
    #
    # These describe the database the commit will be made against, which is
    # why they are taken here and not in an earlier phase.
    real_ids = set(load_registry_rows())

    rows = (
        session.execute(
            sa.text(
                "SELECT source_id, decision FROM "
                "nf_source_authorization_decisions WHERE organization_id = :o"
            ),
            {"o": str(DEMO).replace("-", "")},
        ).all()
        or []
    )
    if not rows:
        # SQLite stores the uuid dashless; Postgres does not. Try both rather
        # than reporting zero because the key format differed.
        rows = (
            session.execute(
                sa.text(
                    "SELECT source_id, decision FROM "
                    "nf_source_authorization_decisions"
                )
            ).all()
            or []
        )

    real_with_decisions = sorted({r[0] for r in rows} & real_ids)
    real_approved = sorted(
        {r[0] for r in rows if r[1] == "approved"} & real_ids
    )
    out["real_sources_with_decisions"] = len(real_with_decisions)
    out["real_sources_approved"] = len(real_approved)
    if real_with_decisions:
        detail.append(f"real sources with decisions: {real_with_decisions[:5]}")

    try:
        out["live_execution_attempts"] = int(
            session.execute(
                sa.text(
                    "SELECT count(*) FROM "
                    "nf_source_collection_execution_attempts "
                    "WHERE transport_kind <> 'hermetic' "
                    "OR live_source_call <> 0"
                )
            ).scalar()
            or 0
        )
    except Exception as exc:  # noqa: BLE001
        detail.append(f"attempts:{type(exc).__name__}")
        out["live_execution_attempts"] = -1

    try:
        out["unsigned_approvals"] = int(
            session.execute(
                sa.text(
                    "SELECT count(*) FROM nf_source_authorization_decisions "
                    "WHERE decision = 'approved' AND "
                    "(reviewed_by IS NULL OR reviewed_at IS NULL)"
                )
            ).scalar()
            or 0
        )
    except Exception as exc:  # noqa: BLE001
        detail.append(f"unsigned:{type(exc).__name__}")
        out["unsigned_approvals"] = -1
except Exception as exc:  # noqa: BLE001
    detail.append(f"phase_error:{type(exc).__name__}:{exc}")
    session.rollback()
    counted = False
finally:
    session.close()

out["removed"] = removed
out["residue"] = residue
out["counted_actual_rows"] = bool(counted)
out.setdefault("real_sources_with_decisions", -1)
out.setdefault("real_sources_approved", -1)
out.setdefault("live_execution_attempts", -1)
out.setdefault("unsigned_approvals", -1)
out["detail"] = "; ".join(sorted(set(detail))) if detail else None
print(json.dumps(out, sort_keys=True))
