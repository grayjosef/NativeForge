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

#: The ONLY real sources permitted to carry terms / human-review / activation
#: decisions. Gate 163 activated exactly one, signed by MAYHEM.
#:
#: A LITERAL, deliberately. Gate 166B removed the code's constant, so the
#: authoritative set is now DERIVED from the signed decision and activation
#: rows. Deriving this pin the same way would make the check follow the data,
#: so signing a fourth decision would silently widen what this permits. Pinned
#: here and cross-checked against the derived set below, so drift in either
#: direction fails.
ALLOWED_REAL_DECISION_SOURCES: frozenset[str] = frozenset(
    {"nf-seed-2026-api-grants-gov-search2"}
)
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
                "DELETE FROM nf_source_authorization_decisions WHERE source_id LIKE :p"
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
                "SELECT source_id, decision, reviewed_by, reviewed_at FROM "
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
                    "SELECT source_id, decision, reviewed_by, reviewed_at FROM "
                    "nf_source_authorization_decisions"
                )
            ).all()
            or []
        )

    real_with_decisions = sorted({r[0] for r in rows} & real_ids)
    real_approved = sorted({r[0] for r in rows if r[1] == "approved"} & real_ids)

    # Reported, because the raw numbers are what a reader wants to see.
    out["real_sources_with_decisions"] = len(real_with_decisions)
    out["real_sources_approved"] = len(real_approved)

    # Asserted, narrowed. Gate 163 gave exactly one real source signed
    # decisions on purpose, so "no real source has a decision" would now refuse
    # reality. The safety property is that no UNAPPROVED one does.
    unapproved_with_decisions = sorted(
        set(real_with_decisions) - ALLOWED_REAL_DECISION_SOURCES
    )
    unapproved_approved = sorted(set(real_approved) - ALLOWED_REAL_DECISION_SOURCES)
    out["unapproved_real_sources_with_decisions"] = len(unapproved_with_decisions)
    out["unapproved_real_sources_approved"] = len(unapproved_approved)
    if unapproved_with_decisions:
        detail.append(
            f"UNAPPROVED real sources with decisions: {unapproved_with_decisions[:5]}"
        )

    # Counting the allowed one separately is not permitting it silently.
    allowed_seen = sorted(set(real_with_decisions) & ALLOWED_REAL_DECISION_SOURCES)
    out["allowed_real_sources_with_decisions"] = len(allowed_seen)
    out["at_most_one_real_source_is_allowed"] = bool(
        len(ALLOWED_REAL_DECISION_SOURCES) == 1
    )

    signed = {r[0] for r in rows if r[2] and r[3]}
    unsigned_allowed = sorted(set(allowed_seen) - signed)
    out["allowed_real_source_decisions_are_signed"] = not unsigned_allowed
    if unsigned_allowed:
        detail.append(
            f"an allowed real source has an unsigned decision: {unsigned_allowed}"
        )

    # The literal pin above and the authority under test must agree.
    #
    # Gate 166B removed `AUTHORIZED_SOURCE_IDS`: no constant authorizes a
    # source any more, the signed rows do. The key is RENAMED rather than
    # reused, because what it measures changed - a check still called
    # `the_code_authorizes...` while reading the database would be the
    # substring-vs-meaning defect this campaign keeps finding.
    try:
        from nativeforge.services.source_authority_service import (
            derive_authorized_source_ids,
        )

        derived = derive_authorized_source_ids(
            connection=session, organization_id=DEMO
        )
        out["the_data_authorizes_exactly_the_pinned_set"] = bool(
            derived == ALLOWED_REAL_DECISION_SOURCES
        )
        if derived != ALLOWED_REAL_DECISION_SOURCES:
            detail.append(
                "the DERIVED authorized set drifted from the pinned set: "
                f"{sorted(derived)}"
            )
    except Exception as exc:  # noqa: BLE001 - an underivable set authorizes nothing
        out["the_data_authorizes_exactly_the_pinned_set"] = False
        detail.append(f"authorized_set:{type(exc).__name__}")

    # Reported, not required to be zero: Gate 163's authorized collection is a
    # live attempt that legitimately exists.
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

    # Asserted. Composed from the canonical classifier rather than a second
    # SQL definition: it resolves eight linkages per row, where a
    # `WHERE authorized_source_id IS NOT NULL` would check one of them.
    try:
        from nativeforge.repositories.source_collection_execution_attempt_repository import (  # noqa: E501
            count_attempts,
        )

        attempts = count_attempts(connection=session, organization_id=DEMO)
        out["unauthorized_live_execution_attempts"] = int(
            attempts.get("unauthorized_live_attempts") or 0
        )
        out["authorized_live_execution_attempts"] = int(
            attempts.get("authorized_live_attempts") or 0
        )
        out["unsigned_live_execution_attempts"] = int(
            attempts.get("unsigned_live_attempts") or 0
        )
        out["live_attempts_outside_the_authorized_set"] = int(
            attempts.get("live_rows_outside_authorized_set") or 0
        )
        if attempts.get("unauthorized_detail"):
            detail.append(
                f"unauthorized live attempts: {attempts['unauthorized_detail']}"
            )
    except Exception as exc:  # noqa: BLE001 - an unclassifiable row is not authorized
        detail.append(f"live_attempt_classification:{type(exc).__name__}")
        out["unauthorized_live_execution_attempts"] = -1

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
out.setdefault("unapproved_real_sources_with_decisions", -1)
out.setdefault("unapproved_real_sources_approved", -1)
out.setdefault("allowed_real_sources_with_decisions", -1)
out.setdefault("at_most_one_real_source_is_allowed", False)
out.setdefault("allowed_real_source_decisions_are_signed", False)
out.setdefault("the_data_authorizes_exactly_the_pinned_set", False)
out.setdefault("real_sources_approved", -1)
out.setdefault("live_execution_attempts", -1)
out.setdefault("unauthorized_live_execution_attempts", -1)
out.setdefault("authorized_live_execution_attempts", -1)
out.setdefault("unsigned_live_execution_attempts", -1)
out.setdefault("live_attempts_outside_the_authorized_set", -1)
out.setdefault("unsigned_approvals", -1)
out["detail"] = "; ".join(sorted(set(detail))) if detail else None
print(json.dumps(out, sort_keys=True))
