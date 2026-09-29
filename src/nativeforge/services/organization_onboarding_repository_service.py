"""Gate 177: thin SQL persistence for profile versions and authority evidence."""

from __future__ import annotations

import datetime as dt
import json
from typing import Any

import sqlalchemy as sa

from nativeforge.services.organization_profile_service import (
    build_profile_version,
    profile_invariant_failures,
    revise_profile,
)
from nativeforge.services.tribal_authority_evidence_service import (
    evidence_invariant_failures,
    grade_evidence_set,
)
from nativeforge.services.tribal_authority_model_service import (
    AFFILIATION_UNVERIFIED,
    AUTHORITY_UNVERIFIED,
    IDENTITY_UNVERIFIED,
)

PROFILES = "nf_organization_profile_versions"
EVIDENCE = "nf_tribal_authority_evidence"
GRANTS = "nf_tribal_authority_grants"

SCHEMA_VERSION = "nf_organization_onboarding_repository_v1"


def _parse_dt(value: Any) -> Any:
    if value is None or value == "":
        return None
    if isinstance(value, dt.datetime):
        return value
    if isinstance(value, str):
        z = value.strip().replace("Z", "+00:00")
        try:
            return dt.datetime.fromisoformat(z)
        except ValueError:
            return value
    return value


def _profile_row_to_dict(row: sa.RowMapping) -> dict[str, Any]:
    values = json.loads(row["values_json"] or "{}")
    phrase_res = json.loads(row["phrase_resolutions_json"] or "{}")
    return {
        "profile_version_id": row["profile_version_id"],
        "organization_id": row["organization_id"],
        "version_ordinal": row["version_ordinal"],
        "supersedes_version_id": row["supersedes_version_id"],
        "entity_type": row["entity_type"],
        "values": values,
        "phrase_resolutions": phrase_res,
        "review_required": bool(row["review_required"]),
        "unresolved_phrases": [],
        "changed_by": row["changed_by"],
        "changed_at": (
            row["changed_at"].isoformat()
            if isinstance(row["changed_at"], dt.datetime)
            else row["changed_at"]
        ),
        "reason": row["reason"],
        "is_demo": bool(row["is_demo"]),
        "model_version": row["model_version"],
    }


def load_latest_profile(
    connection: sa.engine.Connection, *, organization_id: str
) -> dict[str, Any] | None:
    row = (
        connection.execute(
            sa.text(
                f"SELECT * FROM {PROFILES} WHERE organization_id = :org "
                f"ORDER BY version_ordinal DESC LIMIT 1"
            ),
            {"org": organization_id},
        )
        .mappings()
        .first()
    )
    return _profile_row_to_dict(row) if row else None


def list_profile_versions(
    connection: sa.engine.Connection, *, organization_id: str, limit: int = 50
) -> list[dict[str, Any]]:
    rows = (
        connection.execute(
            sa.text(
                f"SELECT profile_version_id, version_ordinal, changed_at, "
                f"changed_by, review_required, entity_type "
                f"FROM {PROFILES} WHERE organization_id = :org "
                f"ORDER BY version_ordinal DESC LIMIT :lim"
            ),
            {"org": organization_id, "lim": int(limit)},
        )
        .mappings()
        .all()
    )
    return [dict(r) for r in rows]


def persist_profile_version(
    connection: sa.engine.Connection, *, version: dict[str, Any]
) -> dict[str, Any]:
    failures = profile_invariant_failures(version)
    if failures:
        return {"persisted": False, "failures": failures}

    values = version.get("values") or {}
    phrase_res = version.get("phrase_resolutions") or {}
    unresolved = version.get("unresolved_phrases") or []
    changed_at = _parse_dt(version.get("changed_at")) or dt.datetime.now(dt.UTC)

    connection.execute(
        sa.text(
            f"INSERT INTO {PROFILES} "
            f"(profile_version_id, organization_id, version_ordinal, "
            f"supersedes_version_id, entity_type, values_json, "
            f"phrase_resolutions_json, unresolved_phrase_count, review_required, "
            f"changed_by, changed_at, reason, is_demo, model_version) "
            f"VALUES (:pid, :org, :ord, :sup, :etype, :vals, :phrases, :ucount, "
            f":review, :by, :at, :reason, :demo, :mv)"
        ),
        {
            "pid": version["profile_version_id"],
            "org": version["organization_id"],
            "ord": version["version_ordinal"],
            "sup": version.get("supersedes_version_id"),
            "etype": version.get("entity_type") or values.get("entity_type"),
            "vals": json.dumps(values, sort_keys=True),
            "phrases": json.dumps(phrase_res, sort_keys=True),
            "ucount": len(unresolved),
            "review": 1 if version.get("review_required") else 0,
            "by": version.get("changed_by"),
            "at": changed_at,
            "reason": version.get("reason"),
            "demo": 1 if version.get("is_demo") else 0,
            "mv": version.get("model_version"),
        },
    )
    return {"persisted": True, "profile_version_id": version["profile_version_id"]}


def submit_profile_revision(
    connection: sa.engine.Connection,
    *,
    organization_id: str,
    changes: dict[str, Any],
    changed_by: str,
    reason: str | None,
    is_demo: bool,
) -> dict[str, Any]:
    current = load_latest_profile(connection, organization_id=organization_id)
    if current is None:
        version = build_profile_version(
            organization_id=organization_id,
            values=changes,
            changed_by=changed_by,
            reason=reason,
            is_demo=is_demo,
        )
        result = persist_profile_version(connection, version=version)
        return {"accepted": result.get("persisted"), "version": version, **result}

    revised = revise_profile(
        current=current,
        changes=changes,
        changed_by=changed_by,
        reason=reason,
    )
    if not revised.get("accepted"):
        return revised
    version = revised["version"]
    result = persist_profile_version(connection, version=version)
    return {"accepted": result.get("persisted"), "version": version, **result}


def load_evidence_for_subject(
    connection: sa.engine.Connection,
    *,
    organization_id: str,
    subject_identity_id: str,
) -> list[dict[str, Any]]:
    rows = (
        connection.execute(
            sa.text(
                f"SELECT * FROM {EVIDENCE} WHERE organization_id = :org "
                f"AND subject_identity_id = :sub ORDER BY recorded_at DESC"
            ),
            {"org": organization_id, "sub": subject_identity_id},
        )
        .mappings()
        .all()
    )
    out: list[dict[str, Any]] = []
    for row in rows:
        out.append(
            {
                "evidence_id": row["evidence_id"],
                "evidence_type": row["evidence_type"],
                "organization_id": row["organization_id"],
                "subject_identity_id": row["subject_identity_id"],
                "issuer": row["issuer"],
                "source_ref": row["source_ref"],
                "artifact_ref": row["artifact_ref"],
                "reviewer": row["reviewer"],
                "decision": row["decision"],
                "decided_at": row["decided_at"],
                "recorded_at": row["recorded_at"],
                "expires_at": row["expires_at"],
                "reason": row["reason"],
                "establishes_identity": bool(row["establishes_identity"]),
                "establishes_affiliation": bool(row["establishes_affiliation"]),
                "establishes_authority": bool(row["establishes_authority"]),
                "is_demo": bool(row["is_demo"]),
                "model_version": row["model_version"],
            }
        )
    return out


def persist_evidence(
    connection: sa.engine.Connection, *, evidence: dict[str, Any]
) -> dict[str, Any]:
    failures = evidence_invariant_failures(evidence)
    if failures:
        return {"persisted": False, "failures": failures}

    recorded_at = _parse_dt(evidence.get("recorded_at")) or dt.datetime.now(dt.UTC)
    decided_at = _parse_dt(evidence.get("decided_at"))
    expires_at = _parse_dt(evidence.get("expires_at"))

    connection.execute(
        sa.text(
            f"INSERT INTO {EVIDENCE} "
            f"(evidence_id, evidence_type, organization_id, subject_identity_id, "
            f"issuer, source_ref, artifact_ref, reviewer, decision, decided_at, "
            f"recorded_at, expires_at, reason, establishes_identity, "
            f"establishes_affiliation, establishes_authority, is_demo, model_version) "
            f"VALUES (:eid, :etype, :org, :sub, :issuer, :sref, :aref, :rev, "
            f":dec, :dat, :rec, :exp, :reason, :ei, :ea, :eauth, :demo, :mv) "
            f"ON CONFLICT(evidence_id) DO NOTHING"
        ),
        {
            "eid": evidence["evidence_id"],
            "etype": evidence["evidence_type"],
            "org": evidence["organization_id"],
            "sub": evidence["subject_identity_id"],
            "issuer": evidence.get("issuer"),
            "sref": evidence.get("source_ref"),
            "aref": evidence.get("artifact_ref"),
            "rev": evidence.get("reviewer"),
            "dec": evidence["decision"],
            "dat": decided_at,
            "rec": recorded_at,
            "exp": expires_at,
            "reason": evidence.get("reason"),
            "ei": 1 if evidence.get("establishes_identity") else 0,
            "ea": 1 if evidence.get("establishes_affiliation") else 0,
            "eauth": 1 if evidence.get("establishes_authority") else 0,
            "demo": 1 if evidence.get("is_demo") else 0,
            "mv": evidence.get("model_version"),
        },
    )
    return {"persisted": True, "evidence_id": evidence["evidence_id"]}


def load_authority_grant(
    connection: sa.engine.Connection,
    *,
    organization_id: str,
    identity_id: str,
) -> dict[str, Any] | None:
    row = (
        connection.execute(
            sa.text(
                f"SELECT * FROM {GRANTS} WHERE organization_id = :org "
                f"AND identity_id = :ident AND revoked_at IS NULL "
                f"ORDER BY created_at DESC LIMIT 1"
            ),
            {"org": organization_id, "ident": identity_id},
        )
        .mappings()
        .first()
    )
    return dict(row) if row else None


def build_authority_dimension_status(
    connection: sa.engine.Connection,
    *,
    organization_id: str,
    subject_identity_id: str,
) -> dict[str, Any]:
    evidence = load_evidence_for_subject(
        connection,
        organization_id=organization_id,
        subject_identity_id=subject_identity_id,
    )
    graded = grade_evidence_set(evidence=evidence)
    grant = load_authority_grant(
        connection,
        organization_id=organization_id,
        identity_id=subject_identity_id,
    )
    identity_status = str(grant["identity_status"]) if grant else IDENTITY_UNVERIFIED
    affiliation_status = (
        str(grant["affiliation_status"]) if grant else AFFILIATION_UNVERIFIED
    )
    authority_status = str(grant["authority_status"]) if grant else AUTHORITY_UNVERIFIED
    return {
        "schema_version": SCHEMA_VERSION,
        "organization_id": organization_id,
        "subject_identity_id": subject_identity_id,
        "identity_status": identity_status,
        "affiliation_status": affiliation_status,
        "authority_status": authority_status,
        "verified": None,
        "evidence_grade": graded,
        "authority_grant": grant,
        "review_pending": graded.get("pending_count", 0) > 0
        or graded.get("review_required"),
    }
