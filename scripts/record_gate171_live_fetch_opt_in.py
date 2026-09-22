"""Gate 171F: the live-fetch opt-in for an approved source. A separate act.

Terms, human review and activation say a source MAY be used. This says the
operator is opting in to a live request right now. Gate 163 kept the two apart
and this keeps them apart for the same reason: a standing approval that
automatically means "fetch now" is not a checkpoint.

## A correction to Gate 163's stated model

Gate 163's preflight runner documents that a robots preflight "does NOT need
live-fetch opt-in". That is no longer true, and appears not to have been true
since the authority ladder was built: `resolve_source_authority` reports
`governance_complete` only when all THREE decision kinds are signed, and the
warrant refuses on `governance_complete` regardless of warrant kind. The
observed refusal was `source_id_is_not_an_authorized_source:activated`.

The behaviour is the safer of the two, so this gate records the opt-in rather
than loosening the warrant. The stale sentence is noted where it lives.

Reads the operator approval file. Opens no socket.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import pathlib
import socket
import sys
import uuid

sys.path.insert(0, "src")

_NETWORK = {"attempts": 0}
_real_socket = socket.socket


class _Refused(socket.socket):
    def __init__(self, *a, **k):  # noqa: ANN002, ANN003
        _NETWORK["attempts"] += 1
        raise OSError("recording an opt-in makes no network request")


socket.socket = _Refused  # type: ignore[misc,assignment]

from nativeforge.db.session import SessionLocal  # noqa: E402
from nativeforge.repositories.source_authorization_decision_repository import (  # noqa: E402,E501
    LIVE_FETCH,
    record_decision,
)

REPO = pathlib.Path(__file__).resolve().parents[1]
APPROVAL_FILE = (
    REPO / "fixtures" / "source_authorization" / "gate171_operator_approval.json"
)
DEMO_ORG = uuid.UUID("bbbbbbbb-cccc-dddd-eeee-ffffffffffff")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-id", required=True)
    parser.add_argument("--operator-handle", required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    source_id = str(args.source_id or "").strip()
    handle = str(args.operator_handle or "").strip()
    approval = json.loads(APPROVAL_FILE.read_text(encoding="utf-8"))

    blocked: list[str] = []
    entry = next(
        (
            e
            for e in approval.get("approved_sources") or []
            if str(e.get("source_id")) == source_id
        ),
        None,
    )
    if entry is None:
        blocked.append(f"source_not_in_the_operator_approval_file:{source_id!r}")
    elif not entry.get("live_fetch_approved"):
        blocked.append(f"live_fetch_not_approved_for:{source_id!r}")
    if handle != str(approval.get("approved_operator") or ""):
        blocked.append(f"operator_handle_does_not_match_the_approval:{handle!r}")

    packet = {
        "purpose": "gate171_live_fetch_opt_in",
        "source_id": source_id,
        "operator_handle": handle,
        "approval_file": str(APPROVAL_FILE.relative_to(REPO)),
        "request_budget": (entry or {}).get("request_budget"),
        "blocked_reasons": sorted(set(blocked)),
        "would_write": not blocked,
        "apply": bool(args.apply),
    }
    print(json.dumps(packet, indent=2, sort_keys=True))

    if blocked:
        print("\nREFUSED - nothing written")
        return 1
    if not args.apply:
        print("\nDRY RUN - pass --apply to record the opt-in")
        return 0

    session = SessionLocal()
    try:
        now = dt.datetime.now(dt.UTC)
        fingerprint = hashlib.sha256(
            f"gate171:live_fetch_opt_in:{source_id}:{handle}".encode()
        ).hexdigest()
        written = record_decision(
            connection=session,
            organization_id=DEMO_ORG,
            source_id=source_id,
            decision_kind=LIVE_FETCH,
            decision="approved",
            # Migration 0052 requires exactly this for a live_fetch row: the
            # opt-in says nothing about terms, and recording a terms status
            # here would imply it had.
            guard_status="NOT_APPLICABLE",
            reviewed_by=f"operator:{handle}",
            reviewed_at=now,
            review_authority="gate171_human_activation",
            evidence_fingerprint=fingerprint,
            evidence_ref="gate171:operator_live_fetch_opt_in",
            notes_classification="unclassified",
            fact_status="tenant_supplied",
            now=now,
        )
        if written.get("blocked_reasons"):
            print(f"\nREFUSED: {written['blocked_reasons']}")
            session.rollback()
            return 1
        session.commit()
    except Exception as exc:  # noqa: BLE001
        session.rollback()
        print(f"\nWRITE FAILED: {type(exc).__name__}: {exc}")
        return 1
    finally:
        session.close()

    socket.socket = _real_socket  # type: ignore[misc,assignment]
    print(f"\nRECORDED live_fetch opt-in for {source_id}")
    print(f"network attempts during this script: {_NETWORK['attempts']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
