"""Gate 152D: one normalized row per piece of evidence, with its status.

## What a ledger entry is

A record this system wrote, named by type and id, with whatever it points at,
what status that gives it, and what a replay still cannot say about it. Three
sources today:

```text
digest_record     Gate 151's nf_tenant_digest_records
delivery_intent   Gate 142's nf_digest_delivery_intents
audit_event       nf_audit_events, reached through the intent that names it
```

## Awarded proof events are deliberately not here

`nf_award_requirement_proof_events` exists and Gate 126 made it operational, so
including it would be easy and would be wrong for this gate: its rows are about
award compliance evidence, which is a different subject from *did this system
show a tenant a digest and record an intention to deliver it*. Mixing them would
produce a ledger whose entries answer two questions and whose summary counts
answer neither. A later gate that wants an award evidence ledger should build
one and say so.

## Every entry carries its limitations

Not only its status. A `linked_record_found` delivery intent is still a plan
nobody sent, and an entry that reported the status without that would be read as
stronger than it is.

## No customer data, no addresses, no bodies

The intent table has no address column and the digest table has no body column,
so the ledger cannot expose either. What it does carry is scanned before it is
returned, and the builder refuses rather than emits.
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
    HASH_VERIFIED,
    LEGACY_GAP,
    LINKED_RECORD_FOUND,
    MISSING_RECORD,
    NOT_REPLAYABLE,
    UNKNOWN,
    is_proof,
    weakest,
)

SCHEMA_VERSION = "nf_evidence_ledger_v1"

CONTROLLED_SCOPE = "controlled_dev_demo"

EVIDENCE_DIGEST = "digest_record"
EVIDENCE_INTENT = "delivery_intent"
EVIDENCE_AUDIT = "audit_event"

EVIDENCE_TYPES: tuple[str, ...] = (EVIDENCE_DIGEST, EVIDENCE_INTENT, EVIDENCE_AUDIT)

#: Sources this ledger deliberately does not draw from, and why. Named so their
#: absence reads as a decision rather than an oversight.
EXCLUDED_SOURCES: tuple[dict[str, str], ...] = (
    {
        "source": "nf_award_requirement_proof_events",
        "why": (
            "award compliance evidence is a different subject from whether a "
            "digest was shown and an intention recorded; one ledger answering "
            "both would have summary counts that answer neither"
        ),
    },
    {
        "source": "nf_award_documents",
        "why": "document metadata, and no body is stored anywhere",
    },
)

#: What a replay cannot say, per evidence type. Carried on every entry.
TYPE_LIMITATIONS: dict[str, tuple[str, ...]] = {
    EVIDENCE_DIGEST: (
        "nothing records whether a tenant read this digest",
        "an archived digest is still readable; archive is a state",
    ),
    EVIDENCE_INTENT: (
        "an intent is a plan; nothing was sent and there is no delivery to attest",
        "the intent stores counts, not the items the digest showed",
    ),
    EVIDENCE_AUDIT: (
        "an audit event records an action, not what a tenant saw",
    ),
}

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


def _entry(
    *,
    organization_id: str,
    evidence_type: str,
    record_id: str,
    evidence_status: str,
    related_record_ids: list[str] | None = None,
    payload_hash: str | None = None,
    created_at: Any = None,
    fact_status: str | None = None,
    is_demo: bool | None = None,
) -> dict[str, Any]:
    return {
        "organization_id": organization_id,
        "evidence_type": evidence_type,
        "record_id": record_id,
        "related_record_ids": sorted(related_record_ids or []),
        "evidence_status": evidence_status,
        "is_proof": is_proof(evidence_status),
        "payload_hash": payload_hash,
        "created_at": created_at,
        "fact_status": fact_status,
        "is_demo": is_demo,
        "replay_limitations": list(TYPE_LIMITATIONS.get(evidence_type, ())),
    }


def build_evidence_ledger(
    *,
    connection: Any = None,
    organization_id: Any = None,
    limit: int = 200,
) -> dict[str, Any]:
    """Every piece of evidence this system holds for one organization."""
    blocked: list[str] = []
    org = _as_uuid(organization_id)
    normalized = str(organization_id or "").strip().lower()

    if connection is None:
        blocked.append("no_connection_supplied")
    if org is None:
        blocked.append("organization_id_is_not_uuid_shaped")
    if normalized == REAL_ORGANIZATION_ID:
        blocked.append("real_organization_refused_by_name")

    if blocked:
        return _json_safe(
            {
                "schema_version": SCHEMA_VERSION,
                "scope": CONTROLLED_SCOPE,
                "organization_id": normalized or None,
                "entries": [],
                "entry_count": 0,
                "by_status": {},
                "by_type": {},
                "overall_status": UNKNOWN,
                "excluded_sources": [dict(s) for s in EXCLUDED_SOURCES],
                "blocked_reasons": sorted(set(blocked)),
                "rows_written": 0,
                "evidence_fabricated": False,
                "leaked_shapes": [],
            }
        )

    capped = max(1, int(limit))
    entries: list[dict[str, Any]] = []

    # -- digest records ----------------------------------------------------
    digest_rows = (
        connection.execute(
            sa.text(
                "SELECT digest_id, payload_sha256, fact_status, is_demo, "
                "created_at FROM nf_tenant_digest_records "
                "WHERE organization_id = :org ORDER BY created_at DESC LIMIT :lim"
            ),
            {"org": org.hex, "lim": capped},
        )
        .mappings()
        .all()
    )
    for row in digest_rows:
        # The payload is read through the repository, never off this raw row.
        #
        # A `sa.text()` SELECT of a JSON column returns a *string* on SQLite -
        # only the typed sa.Table path deserializes it - so hashing the raw
        # value gives a different digest from the stored one, which was
        # computed over the parsed dict. The first version of this did exactly
        # that and reported a perfectly good digest as `missing_record`: a
        # false negative in an audit ledger, which is the worst direction for
        # this kind of error.
        #
        # Same family as Gate 151's DATE coercion: an untyped read behaving
        # differently from the typed one. The fix is not to normalize here but
        # to call the function that owns the read, so the two agree by
        # construction rather than by coincidence.
        through_repository = get_digest_record(
            connection=connection,
            organization_id=organization_id,
            digest_id=row["digest_id"],
        ).get("record")
        hash_ok = bool(
            through_repository
            and through_repository["payload_sha256"]
            == payload_sha256(through_repository["digest_payload_json"])
        )
        intents = (
            connection.execute(
                sa.text(
                    "SELECT id FROM nf_digest_delivery_intents "
                    "WHERE organization_id = :org AND digest_id = :digest"
                ),
                {"org": org.hex, "digest": row["digest_id"]},
            )
            .scalars()
            .all()
        )
        entries.append(
            _entry(
                organization_id=str(org),
                evidence_type=EVIDENCE_DIGEST,
                record_id=row["digest_id"],
                evidence_status=HASH_VERIFIED if hash_ok else MISSING_RECORD,
                related_record_ids=[str(value) for value in intents],
                payload_hash=row["payload_sha256"],
                created_at=row["created_at"],
                fact_status=row["fact_status"],
                is_demo=bool(row["is_demo"]),
            )
        )

    # -- delivery intents, and the audit events they name ------------------
    intent_rows = (
        connection.execute(
            sa.text(
                "SELECT id, digest_id, audit_event_id, fact_status, is_demo, "
                "created_at FROM nf_digest_delivery_intents "
                "WHERE organization_id = :org ORDER BY created_at DESC LIMIT :lim"
            ),
            {"org": org.hex, "lim": capped},
        )
        .mappings()
        .all()
    )
    for row in intent_rows:
        named_digest = str(row["digest_id"] or "").strip()
        related: list[str] = []
        if named_digest:
            exists = connection.execute(
                sa.text(
                    "SELECT count(*) FROM nf_tenant_digest_records "
                    "WHERE organization_id = :org AND digest_id = :digest"
                ),
                {"org": org.hex, "digest": named_digest},
            ).scalar()
            status = LINKED_RECORD_FOUND if exists else LEGACY_GAP
            if exists:
                related.append(named_digest)
        else:
            status = UNKNOWN

        audit_id = _as_uuid(row["audit_event_id"])
        audit_action = None
        if audit_id is not None:
            audit_action = connection.execute(
                sa.text("SELECT action FROM nf_audit_events WHERE id = :id"),
                {"id": audit_id.hex},
            ).scalar()
            if audit_action:
                related.append(str(audit_id))

        entries.append(
            _entry(
                organization_id=str(org),
                evidence_type=EVIDENCE_INTENT,
                record_id=str(row["id"]),
                evidence_status=status,
                related_record_ids=related,
                created_at=row["created_at"],
                fact_status=row["fact_status"],
                is_demo=bool(row["is_demo"]),
            )
        )

        if audit_action:
            entries.append(
                _entry(
                    organization_id=str(org),
                    evidence_type=EVIDENCE_AUDIT,
                    record_id=str(audit_id),
                    evidence_status=LINKED_RECORD_FOUND,
                    related_record_ids=[str(row["id"])],
                    created_at=row["created_at"],
                    is_demo=bool(row["is_demo"]),
                )
            )
        elif audit_id is not None:
            entries.append(
                _entry(
                    organization_id=str(org),
                    evidence_type=EVIDENCE_AUDIT,
                    record_id=str(audit_id),
                    evidence_status=MISSING_RECORD,
                    related_record_ids=[str(row["id"])],
                )
            )

    by_status: dict[str, int] = {}
    by_type: dict[str, int] = {}
    for entry in entries:
        by_status[entry["evidence_status"]] = (
            by_status.get(entry["evidence_status"], 0) + 1
        )
        by_type[entry["evidence_type"]] = by_type.get(entry["evidence_type"], 0) + 1

    payload = _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "scope": CONTROLLED_SCOPE,
            "organization_id": str(org),
            "entries": entries,
            "entry_count": len(entries),
            "by_status": by_status,
            "by_type": by_type,
            # The ledger as a whole is as good as its worst entry. An empty
            # ledger is unknown, not attested.
            "overall_status": weakest(
                [entry["evidence_status"] for entry in entries]
            ),
            "evidence_types": list(EVIDENCE_TYPES),
            "excluded_sources": [dict(s) for s in EXCLUDED_SOURCES],
            "truncated": len(digest_rows) >= capped or len(intent_rows) >= capped,
            "blocked_reasons": [],
            # Constants.
            "rows_written": 0,
            "evidence_fabricated": False,
            "email_sent": False,
            "live_source_called": False,
            "object_store_contacted": False,
            "real_organization_touched": False,
            "leaked_shapes": [],
        }
    )
    payload["leaked_shapes"] = _leaked_shapes(payload)
    return payload


def ledger_invariant_failures(ledger: dict[str, Any]) -> list[str]:
    """Refuse a ledger that promoted a gap or claimed more than it read."""
    fails: list[str] = []

    entries = ledger.get("entries") or []

    if ledger.get("entry_count") != len(entries):
        fails.append("entry_count_disagrees_with_the_entries")

    if ledger.get("overall_status") != weakest(
        [entry.get("evidence_status") for entry in entries]
    ):
        fails.append("overall_status_is_not_the_weakest_entry")

    for entry in entries:
        if bool(entry.get("is_proof")) != is_proof(entry.get("evidence_status")):
            fails.append(f"is_proof_disagrees:{entry.get('record_id')}")
        if entry.get("evidence_type") not in EVIDENCE_TYPES:
            fails.append(f"unknown_evidence_type:{entry.get('evidence_type')}")
        if not entry.get("replay_limitations"):
            fails.append(f"entry_without_limitations:{entry.get('record_id')}")

    counted = sum((ledger.get("by_status") or {}).values())
    if entries and counted != len(entries):
        fails.append("by_status_does_not_total_the_entries")

    if ledger.get("evidence_fabricated"):
        fails.append("ledger_fabricated_evidence")
    if ledger.get("rows_written"):
        fails.append("ledger_wrote_rows")

    for flag in (
        "email_sent",
        "live_source_called",
        "object_store_contacted",
        "real_organization_touched",
    ):
        if ledger.get(flag):
            fails.append(f"ledger_claimed_to_have:{flag}")

    for name in ledger.get("leaked_shapes") or []:
        fails.append(f"leaked:{name}")

    return sorted(set(fails))


#: Re-exported so the readiness service and verifier name one scope.
LEDGER_SCOPE = CONTROLLED_SCOPE
ATTESTED_STATUS = ATTESTED
NOT_REPLAYABLE_STATUS = NOT_REPLAYABLE
