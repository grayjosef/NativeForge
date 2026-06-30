"""Grants.gov applicant-type taxonomy → recognition_requirement (primary structured signal)."""

from __future__ import annotations

import json
import re
from typing import Any

from nativeforge.services.sc_pilot_fixture_loader_service import RECOGNITION_REQUIREMENTS

SCHEMA_VERSION = "nf_grants_gov_applicant_type_recognition_v1"

TYPE_FED_TRIBAL_GOV = "07"
TYPE_NONFED_TRIBAL_ORG = "11"
TYPE_NONPROFIT_501C3 = "12"
TYPE_NONPROFIT_NO_501C3 = "13"
TYPE_OTHERS = "25"
TYPE_UNRESTRICTED = "99"

_GOV_TYPE_IDS = frozenset({"01", "02", "03", "04", "05", "06"})
_TRIBAL_TYPE_IDS = frozenset({TYPE_FED_TRIBAL_GOV, TYPE_NONFED_TRIBAL_ORG})
_NONPROFIT_TYPE_IDS = frozenset({TYPE_NONPROFIT_501C3, TYPE_NONPROFIT_NO_501C3})

_APPLICANT_TYPES_PREFIX_RE = re.compile(
    r"^Applicant types:\s*(.+?)(?:\n\n|\n(?=[A-Z])|\Z)",
    re.DOTALL | re.MULTILINE,
)

_LABEL_TO_ID: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"Native American tribal governments \(Federally recognized\)", re.I), TYPE_FED_TRIBAL_GOV),
    (
        re.compile(
            r"Native American tribal organizations \(other than Federally recognized",
            re.I,
        ),
        TYPE_NONFED_TRIBAL_ORG,
    ),
    (re.compile(r"Nonprofits having a 501\(c\)\(3\)", re.I), TYPE_NONPROFIT_501C3),
    (re.compile(r"Nonprofits that do not have a 501\(c\)\(3\)", re.I), TYPE_NONPROFIT_NO_501C3),
    (re.compile(r"^Unrestricted", re.I), TYPE_UNRESTRICTED),
    (re.compile(r"Others \(see text field", re.I), TYPE_OTHERS),
    (re.compile(r"^State governments", re.I), "01"),
    (re.compile(r"^County governments", re.I), "02"),
    (re.compile(r"^City or township governments", re.I), "03"),
    (re.compile(r"^Special district governments", re.I), "04"),
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _normalize_type_ids(raw: object) -> list[str]:
    if not raw:
        return []
    if isinstance(raw, list):
        out: list[str] = []
        for item in raw:
            if isinstance(item, dict):
                tid = str(item.get("id") or "").strip()
            else:
                tid = str(item).strip()
            if tid and tid not in out:
                out.append(tid)
        return out
    return []


def infer_applicant_type_ids_from_labels(labels: list[str]) -> list[str]:
    ids: list[str] = []
    for label in labels:
        for pattern, type_id in _LABEL_TO_ID:
            if pattern.search(label) and type_id not in ids:
                ids.append(type_id)
                break
    return ids


def parse_applicant_type_labels_from_eligibility_text(eligibility_text: str) -> list[str]:
    match = _APPLICANT_TYPES_PREFIX_RE.match(eligibility_text.strip())
    if not match:
        return []
    return [part.strip() for part in match.group(1).split(";") if part.strip()]


def resolve_grant_applicant_type_ids(grant: dict[str, Any]) -> list[str]:
    """Structured IDs from grant fields or backfill from eligibility_text prefix."""
    for key in ("applicant_type_ids", "grants_gov_applicant_type_ids"):
        ids = _normalize_type_ids(grant.get(key))
        if ids:
            return ids

    json_blob = grant.get("applicant_types_json")
    if json_blob:
        ids = _normalize_type_ids(json_blob)
        if ids:
            return ids

    labels = parse_applicant_type_labels_from_eligibility_text(
        str(grant.get("eligibility_text") or "")
    )
    return infer_applicant_type_ids_from_labels(labels)


def _gov_only(type_ids: frozenset[str]) -> bool:
    if not type_ids:
        return False
    if type_ids & (_TRIBAL_TYPE_IDS | _NONPROFIT_TYPE_IDS | {TYPE_UNRESTRICTED, TYPE_OTHERS}):
        return False
    return type_ids <= _GOV_TYPE_IDS or type_ids == frozenset({"01"})


def derive_recognition_from_applicant_type_ids(
    type_ids: list[str],
    *,
    grant: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """
    Map Grants.gov applicant type IDs to recognition_requirement + condition hints.

    Returns None when types are absent or not resolvable without guessing.
    """
    if not type_ids:
        return None

    ids = frozenset(type_ids)
    has_07 = TYPE_FED_TRIBAL_GOV in ids
    has_11 = TYPE_NONFED_TRIBAL_ORG in ids
    has_12 = TYPE_NONPROFIT_501C3 in ids
    has_13 = TYPE_NONPROFIT_NO_501C3 in ids
    has_25 = TYPE_OTHERS in ids
    has_99 = TYPE_UNRESTRICTED in ids

    if _gov_only(ids):
        return _result("unknown", requires_501c3=False)

    if has_25 and not (has_07 or has_11 or has_12 or has_13 or has_99):
        if grant is not None:
            from nativeforge.services.recognition_requirement_derivation_service import (
                _derive_from_text_body,
                _derive_from_others_eligibility_body,
            )

            body_req = _derive_from_others_eligibility_body(grant)
            if body_req is None:
                body_req = _derive_from_text_body(grant, skip_state_ok_boilerplate=True)
            if body_req:
                return _result(body_req)
        return None

    if has_07 and has_11:
        return _result("state_ok")

    if has_07 and not has_11 and (has_12 or has_13):
        return _result(
            "federal_required_for_tribal_pathway",
            requires_501c3=has_12,
            dual_pathway={"nonprofit_alternative": True},
        )

    if has_07 and not has_11:
        return _result("federal_required")

    if has_11 and not has_07:
        return _result("state_ok")

    if has_12 and not has_07 and not has_11:
        return _result("open_nonprofit", requires_501c3=True)

    if (has_13 or has_99) and not has_07 and not has_11:
        return _result("open_nonprofit", requires_501c3=False)

    return None


def _result(
    requirement: str,
    *,
    requires_501c3: bool | None = None,
    dual_pathway: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if requirement not in RECOGNITION_REQUIREMENTS:
        requirement = "unknown"
    payload: dict[str, Any] = {
        "recognition_requirement": requirement,
        "recognition_requirement_source": "applicant_types",
    }
    if requires_501c3 is not None:
        payload["requires_501c3_from_applicant_types"] = requires_501c3
    if dual_pathway:
        payload["dual_pathway_from_applicant_types"] = dual_pathway
    return _json_safe(payload)


def derive_recognition_from_grant_applicant_types(
    grant: dict[str, Any],
) -> dict[str, Any] | None:
    type_ids = resolve_grant_applicant_type_ids(grant)
    if not type_ids:
        return None
    result = derive_recognition_from_applicant_type_ids(type_ids, grant=grant)
    if result is None:
        return None
    result = dict(result)
    result["applicant_type_ids"] = type_ids
    return _json_safe(result)
