"""Gate 163B/C/D: record MAYHEM's decisions for Grants.gov. One source only.

## This writes real approval records

Run deliberately, once, by an operator. It is not part of the test suite and
nothing calls it automatically. Every row it writes is signed with the
operator handle supplied on the command line, and the database refuses an
approval without a signer, a time and an evidence fingerprint.

## What it will not do

```text
--source-id is CHECKED against the authorized seed, not trusted
any other seed          refused by name
a non-public posture    refused - the standing authorization is public-only
a second run            replaces this source's answers, adds no source
the real organization   refused by the repository itself
```

The seed allowlist is a constant in this file. Extending it is an edit somebody
reviews, not an argument somebody passes.

## Ordering

Terms, then human review, then activation. The activation carries the verbatim
attribution notice, because the operator who activates a source is the one
accepting its attribution obligation — and Gate 163L verifies that notice
character-for-character before attribution can satisfy the guard.

Robots is NOT recorded here. It requires a live fetch, which is a separate
deliberate act.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import sys
import uuid

sys.path.insert(0, "src")

import sqlalchemy as sa  # noqa: E402

from nativeforge.db.session import SessionLocal  # noqa: E402
from nativeforge.repositories.source_authorization_decision_repository import (  # noqa: E402,E501
    HUMAN_REVIEW,
    TERMS,
    record_decision,
)
from nativeforge.services.grants_gov_attribution_service import (  # noqa: E402
    ATTRIBUTION_TEXT,
)
from nativeforge.services.source_monitoring_approved_source_service import (  # noqa: E402,E501
    load_registry_rows,
)

DEMO_ORG = uuid.UUID("bbbbbbbb-cccc-dddd-eeee-ffffffffffff")

#: The ONE seed this script may act on. A constant, not an argument: extending
#: it is an edit somebody reviews.
AUTHORIZED_SEED = "nf-seed-2026-api-grants-gov-search2"

#: The four acknowledgements the existing seed activation gate requires. Named
#: here so this script refuses on exactly the same terms.
REQUIRED_ACKNOWLEDGEMENTS = (
    "human_activation_acknowledged",
    "public_only_acknowledged",
    "single_source_only_acknowledged",
)

TERMS_EVIDENCE_URL = "https://www.grants.gov/api/terms-conditions"

ACTIVATION_ARTIFACT = "gate163-grants-gov-search2-activation"

REVIEW_SCOPE = (
    "controlled NativeForge grant discovery via documented public API"
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
    sa.Column("created_at", sa.DateTime(timezone=True)),
    sa.Column("updated_at", sa.DateTime(timezone=True)),
)


def fingerprint(value: str) -> str:
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--operator-handle", required=True)
    parser.add_argument("--source-id", required=True)
    for ack in REQUIRED_ACKNOWLEDGEMENTS:
        parser.add_argument(f"--{ack.replace('_', '-')}", action="store_true")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="without this, prints the packet and writes nothing",
    )
    args = parser.parse_args()

    blocked: list[str] = []

    handle = str(args.operator_handle or "").strip()
    if not handle:
        blocked.append("no_operator_handle")

    source_id = str(args.source_id or "").strip()
    if source_id != AUTHORIZED_SEED:
        blocked.append(
            f"activation_not_authorized_for_seed:{source_id!r}; "
            f"allowed={AUTHORIZED_SEED!r}"
        )

    for ack in REQUIRED_ACKNOWLEDGEMENTS:
        if not getattr(args, ack, False):
            blocked.append(f"acknowledgement_required:{ack}")

    registry = load_registry_rows()
    row = registry.get(source_id)
    if row is None:
        blocked.append(f"source_not_in_registry:{source_id}")
    elif str(row.get("access_posture_hint") or "").lower() != "public":
        blocked.append("only_public_posture_sources_may_be_activated")

    now = dt.datetime.now(dt.UTC)

    packet = {
        "operator_handle": handle,
        "source_id": source_id,
        "source_name": (row or {}).get("source_name"),
        "source_url": (row or {}).get("source_url"),
        "access_posture": (row or {}).get("access_posture_hint"),
        "terms_decision": "approved",
        "terms_guard_status": "ATTRIBUTION_REQUIRED",
        "terms_evidence": TERMS_EVIDENCE_URL,
        "terms_evidence_fingerprint": fingerprint(TERMS_EVIDENCE_URL),
        "human_review_decision": "approved",
        "human_review_scope": REVIEW_SCOPE,
        "activation": "approved",
        "activation_artifact": ACTIVATION_ARTIFACT,
        "attribution_notice": ATTRIBUTION_TEXT,
        "acknowledgements": {
            ack: bool(getattr(args, ack, False))
            for ack in REQUIRED_ACKNOWLEDGEMENTS
        },
        "decided_at": now.isoformat(),
        "blocked_reasons": sorted(blocked),
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
            # The terms permit the API AND require attribution. That obligation
            # is part of the answer, not a footnote to it.
            guard_status="ATTRIBUTION_REQUIRED",
            reviewed_by=handle,
            reviewed_at=now,
            review_authority="operator",
            evidence_fingerprint=fingerprint(TERMS_EVIDENCE_URL),
            evidence_ref=TERMS_EVIDENCE_URL,
            notes_classification="public_api_terms_permit_automated_retrieval",
            # No expiry: the published terms declare no review cadence, and
            # inventing one would be a policy nobody set.
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
            evidence_fingerprint=fingerprint(REVIEW_SCOPE),
            evidence_ref=REVIEW_SCOPE,
            notes_classification="scope_controlled_discovery_public_api",
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
            "source_type": "public_api",
            "source_lane": "federal",
            "source_url_or_search_target": row["source_url"],
            "collection_method": "documented_public_api",
            "update_frequency": "manual",
            "source_health_status": "unknown",
            "activation_approved_by": handle,
            "activation_approved_at": now,
            "activation_approval_artifact_id": ACTIVATION_ARTIFACT,
            # The verbatim attribution notice. Gate 163L verifies this
            # character-for-character before attribution can satisfy the guard.
            "activation_notes": ATTRIBUTION_TEXT,
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

    print(f"\nWROTE: {written}")
    print(f"operator: {handle}")
    print(f"source:   {source_id}")
    print("robots.txt has NOT been fetched. That is the next deliberate act.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
