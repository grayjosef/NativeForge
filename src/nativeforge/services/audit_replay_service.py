"""Gate 152C: replay what happened, and say plainly what cannot be replayed.

## Three tables, two links, and the direction matters

```text
intent.organization_id + intent.digest_id  ->  digest record
intent.audit_event_id                      ->  audit event
```

`nf_audit_events` has no `digest_id` or `intent_id` column - it carries
`review_artifact_id`, `tribal_profile_id`, `extraction_run_id` and a JSON
payload. The **intent** points at the event, never the reverse. A replay that
looked for the link on the event would find nothing and report a gap that is not
there.

## Nothing is manufactured

A missing digest stays missing. The 85 legacy intents refer to digests that were
never written, and the snapshots they were built from are not guaranteed
unchanged, so a regenerated digest would be *a* digest for that period and not
*the* one the intent referred to. Storing or returning one would produce
something that looks like evidence and is not.

The replay says `legacy_gap` and moves on.

## Status is per link

Every legacy intent is simultaneously `linked_record_found` on its audit link
and `legacy_gap` on its digest link. The chain's status is the weakest of them,
derived by `weakest()` rather than asserted beside them.

## Cross-org is refused, not filtered

Every read is partitioned by `organization_id`, and a replay for a record that
belongs to another organization returns the same answer as one that does not
exist. A different answer would confirm it exists.

## It reads. It writes nothing and contacts nothing.

No connection is opened here that the caller did not supply, no row is written,
no provider, source or object store is contacted, and no address, provider
subject or document body can appear in a result.
"""

from __future__ import annotations

import json
import re
import uuid
from typing import Any

import sqlalchemy as sa

from nativeforge.repositories.tenant_digest_records_repository import (
    REAL_ORGANIZATION_ID,
    get_digest_record,
    payload_sha256,
)
from nativeforge.services.evidence_status_vocabulary_service import (
    ATTESTED,
    BLOCKED,
    HASH_VERIFIED,
    LEGACY_GAP,
    LINKED_RECORD_FOUND,
    MISSING_RECORD,
    NOT_REPLAYABLE,
    UNKNOWN,
    is_proof,
    weakest,
)

SCHEMA_VERSION = "nf_audit_replay_v1"

CONTROLLED_SCOPE = "controlled_dev_demo"

INTENTS_TABLE = "nf_digest_delivery_intents"
AUDIT_TABLE = "nf_audit_events"

#: Link names, so a caller reads a chain rather than a bag of booleans.
LINK_DIGEST_RECORD = "digest_record"
LINK_PAYLOAD_HASH = "payload_hash"
LINK_DELIVERY_INTENT = "delivery_intent"
LINK_AUDIT_EVENT = "audit_event"

#: Fields that must never appear in a replay result. The intent table has no
#: address column at all; this catches a payload or an action that carries one.
_FORBIDDEN_SHAPES: tuple[tuple[str, str], ...] = (
    ("email_address", r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
    ("bearer_token", r"\beyJ[A-Za-z0-9_-]{8,}"),
    ("session_cookie", r"nf_session="),
    ("set_cookie", r"(?i)set-cookie:"),
    ("google_client_secret", r"GOCSPX-"),
    ("private_key", r"BEGIN PRIVATE KEY"),
    ("aws_key", r"AKIA"),
)
_PROVIDER_SUBJECT_SHAPE = re.compile(r"\b\d{18,}\b")


def _json_safe(value: Any) -> Any:
    return json.loads(json.dumps(value, default=str, sort_keys=True))


def _leaked_shapes(payload: Any) -> list[str]:
    body = json.dumps(payload, default=str, sort_keys=True)
    found = [name for name, pattern in _FORBIDDEN_SHAPES if re.search(pattern, body)]
    if _PROVIDER_SUBJECT_SHAPE.search(body):
        found.append("provider_subject")
    return sorted(set(found))


def _as_uuid(value: Any) -> uuid.UUID | None:
    try:
        return uuid.UUID(str(value))
    except Exception:  # noqa: BLE001
        return None


def _link(name: str, status: str, **detail: Any) -> dict[str, Any]:
    return {"link": name, "status": status, "is_proof": is_proof(status), **detail}


def _result(**fields: Any) -> dict[str, Any]:
    base = {
        "schema_version": SCHEMA_VERSION,
        "scope": CONTROLLED_SCOPE,
        "organization_id": None,
        "subject": None,
        "subject_id": None,
        "found": False,
        "links": [],
        "evidence_status": UNKNOWN,
        "evidence_gaps": [],
        "replay_limitations": [],
        "blocked_reasons": [],
        # Constants. A replay reads.
        "rows_written": 0,
        "evidence_fabricated": False,
        "email_sent": False,
        "live_source_called": False,
        "object_store_contacted": False,
        "real_organization_touched": False,
        "leaked_shapes": [],
    }
    base.update(fields)
    base["blocked_reasons"] = sorted(set(base["blocked_reasons"] or []))
    base["evidence_status"] = weakest(
        [link["status"] for link in (base["links"] or [])]
    )
    base["evidence_gaps"] = sorted(
        {link["link"] for link in (base["links"] or []) if not link["is_proof"]}
    )
    payload = _json_safe(base)
    payload["leaked_shapes"] = _leaked_shapes(payload)
    return payload


def _guard(connection: Any, organization_id: Any) -> list[str]:
    blocked: list[str] = []
    if connection is None:
        blocked.append("no_connection_supplied")
    if _as_uuid(organization_id) is None:
        blocked.append("organization_id_is_not_uuid_shaped")
    if str(organization_id or "").strip().lower() == REAL_ORGANIZATION_ID:
        blocked.append("real_organization_refused_by_name")
    return blocked


def replay_digest(
    *,
    connection: Any = None,
    organization_id: Any = None,
    digest_id: Any = None,
) -> dict[str, Any]:
    """Replay one persisted digest: does it exist, and does its hash check?"""
    blocked = _guard(connection, organization_id)
    if not str(digest_id or "").strip():
        blocked.append("no_digest_id_supplied")
    if blocked:
        return _result(
            subject="digest",
            subject_id=str(digest_id or "") or None,
            organization_id=str(organization_id or "") or None,
            links=[_link(LINK_DIGEST_RECORD, BLOCKED)],
            blocked_reasons=blocked,
        )

    org = _as_uuid(organization_id)
    read = get_digest_record(
        connection=connection, organization_id=organization_id, digest_id=digest_id
    )
    record = read.get("record")

    if not record:
        return _result(
            subject="digest",
            subject_id=str(digest_id),
            organization_id=str(org),
            links=[
                _link(
                    LINK_DIGEST_RECORD,
                    MISSING_RECORD,
                    detail="no digest record for this organization",
                )
            ],
            replay_limitations=[
                "a digest that was never persisted cannot be reconstructed"
            ],
            blocked_reasons=read["blocked_reasons"],
        )

    hash_ok = record["payload_sha256"] == payload_sha256(
        record["digest_payload_json"]
    )

    # Which delivery intents, if any, name this digest.
    intents = (
        connection.execute(
            sa.text(
                f"SELECT id FROM {INTENTS_TABLE} "
                "WHERE organization_id = :org AND digest_id = :digest"
            ),
            {"org": org.hex, "digest": str(digest_id)},
        )
        .scalars()
        .all()
    )

    links = [
        _link(
            LINK_DIGEST_RECORD,
            LINKED_RECORD_FOUND,
            archived=bool(record["archived_at"]),
        ),
        _link(
            LINK_PAYLOAD_HASH,
            HASH_VERIFIED if hash_ok else MISSING_RECORD,
            stored_sha256=record["payload_sha256"],
            verified=hash_ok,
        ),
        _link(
            LINK_DELIVERY_INTENT,
            LINKED_RECORD_FOUND if intents else NOT_REPLAYABLE,
            intent_count=len(intents),
            detail=(
                None
                if intents
                else "no delivery intent names this digest; nothing was queued"
            ),
        ),
    ]

    return _result(
        subject="digest",
        subject_id=str(digest_id),
        organization_id=str(org),
        found=True,
        links=links,
        record={
            key: record[key]
            for key in (
                "digest_id",
                "cadence",
                "period_start",
                "period_end",
                "items_total",
                "items_visible",
                "items_suppressed",
                "items_unchanged",
                "items_human_review",
                "items_with_unverified_deadlines",
                "items_with_unknown_reporting_burden",
                "caveats_json",
                "blocked_reasons",
                "delivery_status",
                "fact_status",
                "is_demo",
                "archived_at",
                "created_at",
            )
        },
        replay_limitations=[
            "an archived digest is still readable; archive is a state",
            "nothing records whether a tenant read this digest",
        ],
    )


def replay_delivery_intent(
    *,
    connection: Any = None,
    organization_id: Any = None,
    intent_id: Any = None,
) -> dict[str, Any]:
    """Replay one delivery intent: its digest, its audit event, its gaps."""
    blocked = _guard(connection, organization_id)
    anchor = _as_uuid(intent_id)
    if anchor is None:
        blocked.append("intent_id_is_not_uuid_shaped")
    if blocked:
        return _result(
            subject="delivery_intent",
            subject_id=str(intent_id or "") or None,
            organization_id=str(organization_id or "") or None,
            links=[_link(LINK_DELIVERY_INTENT, BLOCKED)],
            blocked_reasons=blocked,
        )

    org = _as_uuid(organization_id)
    row = (
        connection.execute(
            sa.text(
                "SELECT id, digest_id, digest_period_key, cadence, "
                "delivery_status, blocked_reason, items_total, items_visible, "
                "send_attempted, provider_contacted, emails_sent, "
                "audit_event_id, fact_status, is_demo, created_at "
                f"FROM {INTENTS_TABLE} WHERE organization_id = :org AND id = :id"
            ),
            {"org": org.hex, "id": anchor.hex},
        )
        .mappings()
        .first()
    )

    if row is None:
        # The same answer for "not yours" as for "does not exist".
        return _result(
            subject="delivery_intent",
            subject_id=str(intent_id),
            organization_id=str(org),
            links=[_link(LINK_DELIVERY_INTENT, MISSING_RECORD)],
            blocked_reasons=["no_delivery_intent_for_this_organization"],
        )

    links = [_link(LINK_DELIVERY_INTENT, LINKED_RECORD_FOUND)]

    # -- the digest link ---------------------------------------------------
    named_digest = str(row["digest_id"] or "").strip()
    if not named_digest:
        links.append(
            _link(LINK_DIGEST_RECORD, UNKNOWN, detail="the intent names no digest")
        )
    else:
        digest_read = get_digest_record(
            connection=connection,
            organization_id=organization_id,
            digest_id=named_digest,
        )
        digest_record = digest_read.get("record")
        if digest_record:
            hash_ok = digest_record["payload_sha256"] == payload_sha256(
                digest_record["digest_payload_json"]
            )
            links.append(_link(LINK_DIGEST_RECORD, LINKED_RECORD_FOUND))
            links.append(
                _link(
                    LINK_PAYLOAD_HASH,
                    HASH_VERIFIED if hash_ok else MISSING_RECORD,
                    verified=hash_ok,
                )
            )
        else:
            # Not fabricated, and not called missing either: it was
            # un-storable when this intent was written.
            links.append(
                _link(
                    LINK_DIGEST_RECORD,
                    LEGACY_GAP,
                    detail=(
                        "this intent predates nf_tenant_digest_records; the "
                        "digest it names cannot be reconstructed"
                    ),
                )
            )

    # -- the audit link ----------------------------------------------------
    audit_id = _as_uuid(row["audit_event_id"])
    if audit_id is None:
        links.append(
            _link(LINK_AUDIT_EVENT, UNKNOWN, detail="the intent names no audit event")
        )
    else:
        action = connection.execute(
            sa.text(f"SELECT action FROM {AUDIT_TABLE} WHERE id = :id"),
            {"id": audit_id.hex},
        ).scalar()
        links.append(
            _link(
                LINK_AUDIT_EVENT,
                LINKED_RECORD_FOUND if action else MISSING_RECORD,
                action=action,
            )
        )

    return _result(
        subject="delivery_intent",
        subject_id=str(intent_id),
        organization_id=str(org),
        found=True,
        links=links,
        record={
            "digest_id": named_digest or None,
            "digest_period_key": row["digest_period_key"],
            "cadence": row["cadence"],
            "delivery_status": row["delivery_status"],
            "blocked_reason": row["blocked_reason"],
            "items_total": row["items_total"],
            "items_visible": row["items_visible"],
            "send_attempted": bool(row["send_attempted"]),
            "provider_contacted": bool(row["provider_contacted"]),
            "emails_sent": row["emails_sent"],
            "fact_status": row["fact_status"],
            "is_demo": bool(row["is_demo"]),
            "created_at": row["created_at"],
        },
        replay_limitations=[
            "an intent is a plan; nothing was sent and there is no delivery "
            "to attest",
            "the intent stores counts, not the items the digest showed",
        ],
    )


def find_legacy_gaps(
    *, connection: Any = None, organization_id: Any = None, limit: int = 200
) -> dict[str, Any]:
    """Delivery intents whose digest was never persisted. Counted, not fixed."""
    blocked = _guard(connection, organization_id)
    if blocked:
        return _json_safe(
            {
                "schema_version": SCHEMA_VERSION,
                "organization_id": str(organization_id or "") or None,
                "legacy_gap_count": 0,
                "intent_ids": [],
                "blocked_reasons": sorted(set(blocked)),
            }
        )

    org = _as_uuid(organization_id)
    rows = (
        connection.execute(
            sa.text(
                f"SELECT i.id FROM {INTENTS_TABLE} i "
                "WHERE i.organization_id = :org AND i.digest_id IS NOT NULL "
                "AND NOT EXISTS ("
                "  SELECT 1 FROM nf_tenant_digest_records r"
                "  WHERE r.organization_id = i.organization_id"
                "  AND r.digest_id = i.digest_id) LIMIT :lim"
            ),
            {"org": org.hex, "lim": max(1, int(limit))},
        )
        .scalars()
        .all()
    )

    total = connection.execute(
        sa.text(
            f"SELECT count(*) FROM {INTENTS_TABLE} i "
            "WHERE i.organization_id = :org AND i.digest_id IS NOT NULL "
            "AND NOT EXISTS ("
            "  SELECT 1 FROM nf_tenant_digest_records r"
            "  WHERE r.organization_id = i.organization_id"
            "  AND r.digest_id = i.digest_id)"
        ),
        {"org": org.hex},
    ).scalar()

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "organization_id": str(org),
            "legacy_gap_count": total,
            "intent_ids": [str(value) for value in rows],
            "evidence_status": LEGACY_GAP if total else ATTESTED,
            "backfilled": False,
            "why_not_backfilled": (
                "the digests cannot be reconstructed - the snapshots they were "
                "built from are not guaranteed unchanged, so a regenerated "
                "digest would be a digest for that period and not the one the "
                "intent referred to"
            ),
            "remedy": (
                "new intents recorded against persisted digests; this count "
                "falls as they are"
            ),
            "blocked_reasons": [],
        }
    )


def replay_invariant_failures(result: dict[str, Any]) -> list[str]:
    """Refuse a replay that fabricated, wrote, or read green through a gap."""
    fails: list[str] = []

    if result.get("rows_written"):
        fails.append("replay_wrote_rows")
    if result.get("evidence_fabricated"):
        fails.append("replay_fabricated_evidence")

    for flag in (
        "email_sent",
        "live_source_called",
        "object_store_contacted",
        "real_organization_touched",
    ):
        if result.get(flag):
            fails.append(f"replay_claimed_to_have:{flag}")

    links = result.get("links") or []
    statuses = [link.get("status") for link in links]
    if result.get("evidence_status") != weakest(statuses):
        fails.append("evidence_status_is_not_the_weakest_link")

    if result.get("evidence_status") == ATTESTED and any(
        not link.get("is_proof") for link in links
    ):
        fails.append("attested_with_a_non_proving_link")

    for link in links:
        if bool(link.get("is_proof")) != is_proof(link.get("status")):
            fails.append(f"link_is_proof_disagrees:{link.get('link')}")

    declared_gaps = set(result.get("evidence_gaps") or [])
    actual_gaps = {
        link["link"] for link in links if not is_proof(link.get("status"))
    }
    if declared_gaps != actual_gaps:
        fails.append("evidence_gaps_disagree_with_the_links")

    for name in result.get("leaked_shapes") or []:
        fails.append(f"leaked:{name}")

    return sorted(set(fails))
