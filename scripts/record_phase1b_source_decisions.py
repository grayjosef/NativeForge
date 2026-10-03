"""Phase 1B: record MAYHEM's decisions for the six authorized surfaces.

## This writes real approval records

Run deliberately by an operator. Nothing calls it automatically and it is not
part of the test suite. Every row is signed with the operator handle supplied
on the command line, and the database refuses an approval without a signer, a
time and an evidence fingerprint.

## Why a second script instead of extending Gate 163's

`record_gate163_grants_gov_decisions.py` records one historical decision about
one source, and its allowlist is a constant precisely so that extending it is
a reviewed edit. Rewriting it to carry six more sources would overwrite the
provenance of the first. It stays exactly as it was.

## What it will not do

```text
--source-id is CHECKED against the Phase 1B allowlist, not trusted
any other seed          refused by name
a non-public posture    refused
USAspending             not in the allowlist, by instruction
Federal Register        not in the allowlist, by instruction
California statewide    not in the allowlist - no evidenced endpoint
the real organizations  never addressed; these rows are demo-org scoped
```

The allowlist below is the exact set Mayhem authorized on 2026-10-03, and
nothing else can be passed into it.

## Terms and attribution are per source, because the obligations are

The five Grants.gov lanes target `api.grants.gov/v1/api/search2` - the same
endpoint, publisher and terms as the source Gate 163 already authorized - so
they carry the same `ATTRIBUTION_REQUIRED` status and the same verbatim
notice. That notice is verified character-for-character before attribution can
satisfy the guard, which is why it is reused rather than retyped.

Denali is different and the difference is not cosmetic. Wave 1 verified its
`robots.txt` as `User-Agent: * / Disallow:` - an empty Disallow, everything
permitted - and checked it before collecting anything. What Wave 1 did NOT
establish is any attribution obligation. No attribution notice for Denali
exists anywhere in this repository.

So Denali is recorded with the robots evidence it actually has and **no
invented attribution notice**. If the warrant then refuses it for an
unsatisfied attribution fact, that refusal is the correct answer and is
reported rather than engineered around. Writing a plausible "Source: Denali
Commission" line would be fabricating a legal obligation nobody verified.
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
    ATTRIBUTION_TEXT as GRANTS_GOV_ATTRIBUTION_TEXT,
)
from nativeforge.services.source_monitoring_approved_source_service import (  # noqa: E402,E501
    load_registry_rows,
)

DEMO_ORG = uuid.UUID("bbbbbbbb-cccc-dddd-eeee-ffffffffffff")

GRANTS_GOV_TERMS_URL = "https://www.grants.gov/api/terms-conditions"
DENALI_ROBOTS_URL = "https://www.denali.gov/robots.txt"

REVIEW_SCOPE = "controlled NativeForge grant discovery via documented public API"

#: The exact surfaces Mayhem authorized, and the evidence each carries.
#:
#: A constant, not an argument. USAspending, Federal Register and California
#: are absent deliberately: the first two are explicitly withheld and the
#: third has no evidenced endpoint.
AUTHORIZED: dict[str, dict[str, object]] = {
    "nf-seed-2026-api-grants-gov-forecast": {
        "terms_notes": "public_api_terms_permit_automated_retrieval",
        "terms_guard_status": "ATTRIBUTION_REQUIRED",
        "terms_evidence": GRANTS_GOV_TERMS_URL,
        "attribution_notice": GRANTS_GOV_ATTRIBUTION_TEXT,
        "artifact": "phase1b-grants-gov-forecast-activation",
    },
    "nf-seed-2026-api-grants-gov-hud-onap": {
        "terms_notes": "public_api_terms_permit_automated_retrieval",
        "terms_guard_status": "ATTRIBUTION_REQUIRED",
        "terms_evidence": GRANTS_GOV_TERMS_URL,
        "attribution_notice": GRANTS_GOV_ATTRIBUTION_TEXT,
        "artifact": "phase1b-hud-onap-assistance-listing-activation",
    },
    "nf-seed-2026-api-grants-gov-ihs": {
        "terms_notes": "public_api_terms_permit_automated_retrieval",
        "terms_guard_status": "ATTRIBUTION_REQUIRED",
        "terms_evidence": GRANTS_GOV_TERMS_URL,
        "attribution_notice": GRANTS_GOV_ATTRIBUTION_TEXT,
        "artifact": "phase1b-ihs-agency-activation",
    },
    "nf-seed-2026-api-grants-gov-epa": {
        "terms_notes": "public_api_terms_permit_automated_retrieval",
        "terms_guard_status": "ATTRIBUTION_REQUIRED",
        "terms_evidence": GRANTS_GOV_TERMS_URL,
        "attribution_notice": GRANTS_GOV_ATTRIBUTION_TEXT,
        "artifact": "phase1b-epa-agency-activation",
    },
    "nf-seed-2026-api-grants-gov-cdfi": {
        "terms_notes": "public_api_terms_permit_automated_retrieval",
        "terms_guard_status": "ATTRIBUTION_REQUIRED",
        "terms_evidence": GRANTS_GOV_TERMS_URL,
        "attribution_notice": GRANTS_GOV_ATTRIBUTION_TEXT,
        "artifact": "phase1b-cdfi-agency-activation",
    },
    "nf-seed-2026-api-denali-wp-posts": {
        "terms_notes": "robots_txt_empty_disallow_verified_wave1",
        # Wave 1 verified an empty Disallow before collecting. No attribution
        # obligation was established, so none is asserted here.
        "terms_guard_status": "NO_REVIEW_REQUIRED",
        "terms_evidence": DENALI_ROBOTS_URL,
        "attribution_notice": "",
        "artifact": "phase1b-denali-wp-posts-activation",
    },
}

REQUIRED_ACKNOWLEDGEMENTS = (
    "human_activation_acknowledged",
    "public_only_acknowledged",
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
    spec = AUTHORIZED.get(source_id)
    if spec is None:
        blocked.append(
            f"activation_not_authorized_for_seed:{source_id!r}; "
            f"allowed={sorted(AUTHORIZED)!r}"
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
    spec = spec or {}
    terms_evidence = str(spec.get("terms_evidence") or "")

    packet = {
        "phase": "1B",
        "operator_handle": handle,
        "source_id": source_id,
        "source_name": (row or {}).get("source_name"),
        "source_url": (row or {}).get("source_url"),
        "access_posture": (row or {}).get("access_posture_hint"),
        "adapter_key": (row or {}).get("adapter_key"),
        "terms_decision": "approved",
        "terms_guard_status": spec.get("terms_guard_status"),
        "terms_evidence": terms_evidence,
        "terms_evidence_fingerprint": fingerprint(terms_evidence),
        "human_review_decision": "approved",
        "human_review_scope": REVIEW_SCOPE,
        "activation": "approved",
        "activation_artifact": spec.get("artifact"),
        "attribution_notice": spec.get("attribution_notice"),
        "attribution_obligation_evidenced": bool(spec.get("attribution_notice")),
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
    try:
        connection = session.connection()
        from nativeforge.db.rls import apply_org_rls_gucs

        apply_org_rls_gucs(session, DEMO_ORG, "demo")

        terms = record_decision(
            connection=session,
            organization_id=DEMO_ORG,
            source_id=source_id,
            decision_kind=TERMS,
            decision="approved",
            guard_status=str(spec.get("terms_guard_status")),
            reviewed_by=handle,
            reviewed_at=now,
            review_authority="operator",
            evidence_fingerprint=fingerprint(terms_evidence),
            evidence_ref=terms_evidence,
            notes_classification=str(spec.get("terms_notes")),
            # No expiry: neither publisher declares a review cadence, and
            # inventing one would be a policy nobody set.
            expires_at=None,
            fact_status="tenant_supplied",
            now=now,
        )
        if not terms["recorded"]:
            print(f"\nTERMS REFUSED: {terms['blocked_reasons']}")
            session.rollback()
            return 1

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

        existing = connection.execute(
            sa.select(ACTIVE_SOURCES.c.id).where(
                sa.and_(
                    ACTIVE_SOURCES.c.organization_id == DEMO_ORG,
                    ACTIVE_SOURCES.c.source_id == source_id,
                )
            )
        ).first()
        values = {
            "organization_id": DEMO_ORG,
            "source_id": source_id,
            "source_name": (row or {}).get("source_name"),
            "source_type": "api",
            "source_lane": str((row or {}).get("adapter_key") or ""),
            "source_url_or_search_target": (row or {}).get("source_url"),
            "collection_method": "bounded_operator_collection",
            "update_frequency": "operator_initiated",
            "source_health_status": "unknown",
            "activation_approved_by": handle,
            "activation_approved_at": now,
            "activation_approval_artifact_id": str(spec.get("artifact")),
            "activation_notes": str(spec.get("attribution_notice") or ""),
            "updated_at": now,
        }
        if existing is None:
            connection.execute(
                sa.insert(ACTIVE_SOURCES).values(
                    id=uuid.uuid4(), created_at=now, **values
                )
            )
            action = "inserted"
        else:
            connection.execute(
                sa.update(ACTIVE_SOURCES)
                .where(ACTIVE_SOURCES.c.id == existing[0])
                .values(**values)
            )
            action = "updated"

        session.commit()
        print(f"\nWROTE decisions and {action} the active-source row")
        return 0
    except Exception as exc:  # noqa: BLE001
        session.rollback()
        print(f"\nFAILED - rolled back: {type(exc).__name__}: {exc}")
        return 1
    finally:
        session.close()


if __name__ == "__main__":
    raise SystemExit(main())
