"""Gate 171F: record the operator's decisions for an approved source.

## The allowlist is DATA, and that is the point of this gate

Gate 163 held its one authorized seed as a module constant and said so
plainly: extending it should be an edit somebody reviews. At one source that
was right. At three it stops scaling, and at a thousand it is the thing Gate
166 removed - a source identity that only code can grant.

So the allowlist here is `fixtures/source_authorization/gate171_operator_
approval.json`: the operator's approval, on disk, naming exact ids. The safety
property is unchanged - a source id absent from that file is refused - but
adding one is a reviewable change to a tracked data file rather than a code
edit and a deploy.

A source id passed on the command line is CHECKED against that file. It is
never trusted.

## What is written, and what is not

```text
written     terms decision, human review decision, adapter binding,
            activation row with the verbatim attribution notice
not written robots (needs a live fetch - a separate deliberate act)
            live_fetch opt-in (a separate deliberate act)
```

Nothing here opens a socket.
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
from typing import Any

sys.path.insert(0, "src")

_NETWORK = {"attempts": 0}
_real_socket = socket.socket


class _Refused(socket.socket):
    def __init__(self, *a, **k):  # noqa: ANN002, ANN003
        _NETWORK["attempts"] += 1
        raise OSError("recording a decision makes no network request")


socket.socket = _Refused  # type: ignore[misc,assignment]

import sqlalchemy as sa  # noqa: E402

from nativeforge.db.session import SessionLocal  # noqa: E402
from nativeforge.repositories.source_authorization_decision_repository import (  # noqa: E402,E501
    HUMAN_REVIEW,
    TERMS,
    record_decision,
)
from nativeforge.services.source_monitoring_approved_source_service import (  # noqa: E402,E501
    load_registry_rows,
)

REPO = pathlib.Path(__file__).resolve().parents[1]
APPROVAL_FILE = (
    REPO / "fixtures" / "source_authorization" / "gate171_operator_approval.json"
)

DEMO_ORG = uuid.UUID("bbbbbbbb-cccc-dddd-eeee-ffffffffffff")

REQUIRED_ACKNOWLEDGEMENTS = (
    "human_activation_acknowledged",
    "public_only_acknowledged",
    "bounded_single_request_acknowledged",
)

ACTIVE_SOURCES = sa.Table(
    "nf_active_opportunity_sources",
    sa.MetaData(),
    sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
    sa.Column("organization_id", sa.Uuid(as_uuid=True)),
    sa.Column("source_id", sa.Text()),
    sa.Column("source_name", sa.Text()),
    sa.Column("source_type", sa.Text()),
    sa.Column("source_lane", sa.Text()),
    sa.Column("source_url_or_search_target", sa.Text()),
    sa.Column("collection_method", sa.Text()),
    sa.Column("update_frequency", sa.Text()),
    sa.Column("source_health_status", sa.Text()),
    sa.Column("activation_approved_by", sa.Text()),
    sa.Column("activation_approved_at", sa.DateTime(timezone=True)),
    sa.Column("activation_approval_artifact_id", sa.Text()),
    sa.Column("activation_notes", sa.Text()),
    sa.Column("disabled_at", sa.DateTime(timezone=True)),
    sa.Column("disabled_by", sa.Text()),
    sa.Column("disabled_reason", sa.Text()),
    sa.Column("created_at", sa.DateTime(timezone=True)),
    sa.Column("updated_at", sa.DateTime(timezone=True)),
)


def fingerprint(value: str) -> str:
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()


def load_approval() -> dict[str, Any]:
    return json.loads(APPROVAL_FILE.read_text(encoding="utf-8"))


def approved_entry(approval: dict[str, Any], source_id: str) -> dict | None:
    for entry in approval.get("approved_sources") or []:
        if str(entry.get("source_id")) == source_id:
            return entry
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--operator-handle", required=True)
    parser.add_argument("--source-id", required=True)
    for ack in REQUIRED_ACKNOWLEDGEMENTS:
        parser.add_argument(f"--{ack.replace('_', '-')}", action="store_true")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    blocked: list[str] = []
    handle = str(args.operator_handle or "").strip()
    source_id = str(args.source_id or "").strip()

    approval = load_approval()
    entry = approved_entry(approval, source_id)
    if entry is None:
        blocked.append(f"source_not_in_the_operator_approval_file:{source_id!r}")
    elif not entry.get("live_fetch_approved"):
        blocked.append(f"source_present_but_not_approved:{source_id!r}")

    if handle != str(approval.get("approved_operator") or ""):
        blocked.append(
            f"operator_handle_does_not_match_the_approval:{handle!r}"
        )

    registry = load_registry_rows()
    row = registry.get(source_id)
    if row is None:
        blocked.append(f"source_not_in_registry:{source_id}")
    elif entry is not None and str(row.get("source_url")) != str(
        entry.get("source_url")
    ):
        # The approval names a URL. A registry row that points somewhere else
        # is not the source that was approved, whatever it is called.
        blocked.append("registry_url_does_not_match_the_approved_url")

    posture = str((row or {}).get("access_posture_hint") or "")
    if posture != "public":
        blocked.append(f"non_public_posture_refused:{posture!r}")

    missing_acks = [
        ack for ack in REQUIRED_ACKNOWLEDGEMENTS if not getattr(args, ack, False)
    ]
    if missing_acks:
        blocked.append(f"missing_acknowledgements:{sorted(missing_acks)}")

    now = dt.datetime.now(dt.UTC)
    attribution = str((entry or {}).get("attribution_notice") or "")
    adapter_key = str((entry or {}).get("adapter_key") or "")
    if not attribution:
        blocked.append("approved_source_without_an_attribution_notice")
    if not adapter_key:
        blocked.append("approved_source_without_an_adapter_binding")

    review_scope = (
        "controlled NativeForge grant discovery, one bounded request, "
        f"adapter {adapter_key}"
    )
    activation_artifact = f"gate171-{source_id}-activation"

    packet = {
        "purpose": "gate171_source_decisions",
        "source_id": source_id,
        "source_name": (row or {}).get("source_name"),
        "source_url": (row or {}).get("source_url"),
        "adapter_binding": adapter_key,
        "access_posture": posture,
        "operator_handle": handle,
        "approval_file": str(APPROVAL_FILE.relative_to(REPO)),
        "attribution_notice": attribution,
        "acknowledgements": {
            ack: bool(getattr(args, ack, False))
            for ack in REQUIRED_ACKNOWLEDGEMENTS
        },
        "decided_at": now.isoformat(),
        "writes": ["terms", "human_review", "activation_with_adapter_binding"],
        "does_not_write": ["robots", "live_fetch_opt_in"],
        "blocked_reasons": sorted(set(blocked)),
        "would_write": not blocked,
        "apply": bool(args.apply),
    }
    print(json.dumps(packet, indent=2, sort_keys=True))

    if blocked:
        print("\nREFUSED - nothing written")
        return 1
    if not args.apply:
        print("\nDRY RUN - pass --apply to write these decisions")
        return 0

    session = SessionLocal()
    written: list[str] = []
    try:
        terms = record_decision(
            connection=session,
            organization_id=DEMO_ORG,
            source_id=source_id,
            decision_kind=TERMS,
            decision="approved",
            guard_status="ATTRIBUTION_REQUIRED",
            reviewed_by=handle,
            reviewed_at=now,
            review_authority="operator",
            evidence_fingerprint=fingerprint(str(APPROVAL_FILE.name)),
            evidence_ref=str(APPROVAL_FILE.relative_to(REPO)),
            notes_classification="operator_approved_public_source_bounded_request",
            expires_at=None,
            fact_status="tenant_supplied",
            now=now,
        )
        if not terms["recorded"]:
            print(f"\nTERMS REFUSED: {terms['blocked_reasons']}")
            session.rollback()
            return 1
        written.append("terms")

        review = record_decision(
            connection=session,
            organization_id=DEMO_ORG,
            source_id=source_id,
            decision_kind=HUMAN_REVIEW,
            decision="approved",
            guard_status="NOT_APPLICABLE",
            reviewed_by=handle,
            reviewed_at=now,
            review_authority="operator",
            evidence_fingerprint=fingerprint(review_scope),
            evidence_ref=review_scope,
            notes_classification="scope_controlled_discovery_bounded_request",
            expires_at=None,
            fact_status="tenant_supplied",
            now=now,
        )
        if not review["recorded"]:
            print(f"\nHUMAN REVIEW REFUSED: {review['blocked_reasons']}")
            session.rollback()
            return 1
        written.append("human_review")

        existing = session.execute(
            sa.select(ACTIVE_SOURCES).where(
                sa.and_(
                    ACTIVE_SOURCES.c.organization_id == DEMO_ORG,
                    ACTIVE_SOURCES.c.source_id == source_id,
                )
            )
        ).first()
        values = {
            "source_id": source_id,
            "source_name": row["source_name"],
            "source_type": str(entry.get("shape") or "unknown").lower(),
            "source_lane": "federal",
            "source_url_or_search_target": row["source_url"],
            # The adapter binding lives HERE rather than in the seed CSV, so a
            # source can be re-bound to a corrected adapter without editing a
            # fixture that 82 tests count the rows of.
            "collection_method": adapter_key,
            "update_frequency": "manual",
            "source_health_status": "unknown",
            "activation_approved_by": handle,
            "activation_approved_at": now,
            "activation_approval_artifact_id": activation_artifact,
            "activation_notes": attribution,
            "disabled_at": None,
            "disabled_by": None,
            "disabled_reason": None,
            "updated_at": now,
        }
        if existing is not None:
            session.execute(
                sa.update(ACTIVE_SOURCES)
                .where(
                    sa.and_(
                        ACTIVE_SOURCES.c.organization_id == DEMO_ORG,
                        ACTIVE_SOURCES.c.source_id == source_id,
                    )
                )
                .values(**values)
            )
        else:
            session.execute(
                sa.insert(ACTIVE_SOURCES).values(
                    id=uuid.uuid4(),
                    organization_id=DEMO_ORG,
                    created_at=now,
                    **values,
                )
            )
        written.append("activation")
        session.commit()
    except Exception as exc:  # noqa: BLE001 - report and write nothing
        session.rollback()
        print(f"\nWRITE FAILED: {type(exc).__name__}: {exc}")
        return 1
    finally:
        session.close()

    socket.socket = _real_socket  # type: ignore[misc,assignment]
    print(f"\nWROTE: {written}")
    print(f"operator:        {handle}")
    print(f"source:          {source_id}")
    print(f"adapter binding: {adapter_key}")
    print(f"network attempts during this script: {_NETWORK['attempts']}")
    print("robots.txt has NOT been fetched. That is the next deliberate act.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
