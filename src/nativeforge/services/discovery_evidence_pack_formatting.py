"""Pure helpers for Discovery evidence packs (hashing, sections, warnings)."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any

from nativeforge.domain.enums import (
    EvidencePackSectionType,
    EvidencePackWarningSeverity,
    EvidencePackWarningType,
)


def evidence_dt(v: object | None) -> str | None:
    if v is None:
        return None
    if isinstance(v, datetime):
        return v.isoformat()
    return str(v)


def digest_json_blob(blob: object | None) -> str | None:
    if blob is None:
        return None
    try:
        raw = json.dumps(blob, sort_keys=True, default=str).encode()
    except TypeError:
        return None
    return hashlib.sha256(raw).hexdigest()


def evidence_warn(
    warning_type: EvidencePackWarningType,
    severity: EvidencePackWarningSeverity,
    title: str,
    rationale: str,
    recommended_action: str,
) -> dict[str, Any]:
    return {
        "warning_type": warning_type.value,
        "severity": severity.value,
        "title": title,
        "rationale": rationale,
        "recommended_action": recommended_action,
    }


def evidence_section(
    section_type: EvidencePackSectionType,
    title: str,
    summary: str,
    records: list[Any],
    warnings: list[dict[str, Any]],
    *,
    generated_at: str,
) -> dict[str, Any]:
    return {
        "section_type": section_type.value,
        "title": title,
        "summary": summary,
        "records": records,
        "warnings": warnings,
        "generated_at": generated_at,
    }
