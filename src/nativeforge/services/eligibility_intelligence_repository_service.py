"""Gate 174N: persist normalized requirements and tenant eligibility matches."""

from __future__ import annotations

import datetime as dt
import json
from typing import Any

import sqlalchemy as sa

from nativeforge.services.eligibility_requirement_model_service import (
    ELIGIBILITY_MODEL_VERSION,
)
from nativeforge.services.intelligence_sql_dialect_service import insert_or_replace_rows

SCHEMA_VERSION = "nf_eligibility_intelligence_repository_v1"

REQUIREMENTS = "nf_opportunity_eligibility_requirements"
PROFILES = "nf_organization_capability_profiles"
MATCHES = "nf_tenant_eligibility_matches"


def _json(value: Any) -> str:
    return json.dumps(value, default=str, sort_keys=True)


def _now(value: Any = None) -> dt.datetime:
    return value if isinstance(value, dt.datetime) else dt.datetime.now(dt.UTC)


def write_requirements(
    connection: sa.engine.Connection,
    *,
    requirements: list[dict[str, Any]],
    now: Any = None,
) -> int:
    if not requirements:
        return 0
    stamp = _now(now)
    canonical_ids = sorted({str(r["canonical_id"]) for r in requirements})
    placeholders = ", ".join(f":c{i}" for i in range(len(canonical_ids)))
    connection.execute(
        sa.text(
            f"UPDATE {REQUIREMENTS} SET is_current = 0, superseded_at = :stamp "
            f"WHERE is_current = 1 AND canonical_id IN ({placeholders})"
        ),
        {"stamp": stamp, **{f"c{i}": v for i, v in enumerate(canonical_ids)}},
    )
    rows = [
        {
            "requirement_id": r["requirement_id"],
            "canonical_id": r["canonical_id"],
            "requirement_kind": r["requirement_kind"],
            "polarity": r["polarity"],
            "normalized_value_json": _json(r.get("normalized_value")),
            "original_text": r["original_text"],
            "applies_to_entity_classes_json": _json(
                r.get("applies_to_entity_classes") or []
            ),
            "evidence_ids_json": _json(r.get("evidence_ids") or []),
            "document_ref": r.get("document_ref"),
            "section_ref": r.get("section_ref"),
            "page_ref": r.get("page_ref"),
            "source_id": r.get("source_id"),
            "raw_payload_sha256": r.get("raw_payload_sha256"),
            "confidence_class": r.get("confidence_class"),
            "is_structural": 1 if r.get("is_structural") else 0,
            "is_addressable": 1 if r.get("is_addressable") else 0,
            "model_version": r.get("model_version") or ELIGIBILITY_MODEL_VERSION,
            "superseded_at": None,
            "is_current": 1,
            "created_at": stamp,
        }
        for r in requirements
    ]
    insert_or_replace_rows(
        connection,
        table=REQUIREMENTS,
        columns=(
            "requirement_id",
            "canonical_id",
            "requirement_kind",
            "polarity",
            "normalized_value_json",
            "original_text",
            "applies_to_entity_classes_json",
            "evidence_ids_json",
            "document_ref",
            "section_ref",
            "page_ref",
            "source_id",
            "raw_payload_sha256",
            "confidence_class",
            "is_structural",
            "is_addressable",
            "model_version",
            "superseded_at",
            "is_current",
            "created_at",
        ),
        rows=rows,
        primary_key="requirement_id",
    )
    return len(rows)


def write_capability_profile(
    connection: sa.engine.Connection,
    *,
    profile: dict[str, Any],
    now: Any = None,
) -> int:
    stamp = _now(now)
    org_id = str(profile["organization_id"])
    connection.execute(
        sa.text(
            f"UPDATE {PROFILES} SET is_current = 0, superseded_at = :stamp "
            "WHERE is_current = 1 AND organization_id = :oid"
        ),
        {"stamp": stamp, "oid": org_id},
    )
    row = {
        "profile_id": profile["profile_id"],
        "organization_id": org_id,
        "profile_version": profile["profile_version"],
        "profile_schema_version": profile.get("profile_schema_version") or "2026.09.1",
        "content_digest": profile["content_digest"],
        "fields_json": _json(profile.get("fields") or {}),
        "answered_count": int(profile.get("answered_count") or 0),
        "unanswered_count": int(profile.get("unanswered_count") or 0),
        "authority_verification_performed": 0,
        "superseded_at": None,
        "is_current": 1,
        "recorded_at": profile.get("recorded_at") or stamp,
        "created_at": stamp,
    }
    insert_or_replace_rows(
        connection,
        table=PROFILES,
        columns=tuple(row.keys()),
        rows=[row],
        primary_key="profile_id",
    )
    return 1


def write_matches(
    connection: sa.engine.Connection,
    *,
    matches: list[dict[str, Any]],
    now: Any = None,
) -> int:
    if not matches:
        return 0
    stamp = _now(now)
    keys = sorted({(str(m["canonical_id"]), str(m["tenant_id"])) for m in matches})
    for canonical_id, tenant_id in keys:
        connection.execute(
            sa.text(
                f"UPDATE {MATCHES} SET is_current = 0 "
                "WHERE is_current = 1 AND canonical_id = :cid AND tenant_id = :tid"
            ),
            {"cid": canonical_id, "tid": tenant_id},
        )
    rows = [
        {
            "match_id": m["match_id"],
            "canonical_id": m["canonical_id"],
            "tenant_id": m["tenant_id"],
            "organization_id": m["organization_id"],
            "profile_version": m["profile_version"],
            "model_version": m.get("model_version") or ELIGIBILITY_MODEL_VERSION,
            "eligibility_result": m["eligibility_result"],
            "reason": m.get("reason") or "",
            "satisfied_count": int(m.get("satisfied_count") or 0),
            "unsatisfied_count": int(m.get("unsatisfied_count") or 0),
            "unknown_count": int(m.get("unknown_count") or 0),
            "review_count": int(m.get("review_count") or 0),
            "applied_exclusion_count": int(m.get("applied_exclusion_count") or 0),
            "requirement_count": int(m.get("requirement_count") or 0),
            "conditions_to_obtain_json": _json(m.get("conditions_to_obtain") or []),
            "review_required": 1 if m.get("review_required") else 0,
            "consumed_global_normalization": 1,
            "evaluated_at": m.get("evaluated_at") or stamp,
            "is_current": 1,
            "created_at": stamp,
        }
        for m in matches
    ]
    insert_or_replace_rows(
        connection,
        table=MATCHES,
        columns=tuple(rows[0].keys()),
        rows=rows,
        primary_key="match_id",
    )
    return len(rows)


def load_current_requirements(
    connection: sa.engine.Connection, *, canonical_id: str
) -> list[dict[str, Any]]:
    rows = connection.execute(
        sa.text(
            f"SELECT requirement_id, requirement_kind, polarity, normalized_value_json, "
            f"original_text, applies_to_entity_classes_json, evidence_ids_json "
            f"FROM {REQUIREMENTS} WHERE canonical_id = :cid AND is_current = 1"
        ),
        {"cid": canonical_id},
    ).fetchall()
    out: list[dict[str, Any]] = []
    for row in rows:
        out.append(
            {
                "requirement_id": row[0],
                "requirement_kind": row[1],
                "polarity": row[2],
                "normalized_value": json.loads(row[3]),
                "original_text": row[4],
                "applies_to_entity_classes": json.loads(row[5] or "[]"),
                "evidence_ids": json.loads(row[6] or "[]"),
                "canonical_id": canonical_id,
            }
        )
    return out


def load_current_match(
    connection: sa.engine.Connection,
    *,
    canonical_id: str,
    tenant_id: str,
) -> dict[str, Any] | None:
    row = connection.execute(
        sa.text(
            f"SELECT eligibility_result, reason, conditions_to_obtain_json, "
            f"review_required, profile_version, unknown_count "
            f"FROM {MATCHES} WHERE canonical_id = :cid AND tenant_id = :tid "
            "AND is_current = 1"
        ),
        {"cid": canonical_id, "tid": tenant_id},
    ).fetchone()
    if not row:
        return None
    return {
        "eligibility_result": row[0],
        "reason": row[1],
        "conditions_to_obtain": json.loads(row[2] or "[]"),
        "review_required": bool(row[3]),
        "profile_version": row[4],
        "unknown_count": row[5],
    }
