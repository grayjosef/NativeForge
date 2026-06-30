"""Sprint 308: parse Grants.gov applicantTypes + applicantEligibilityDesc."""

from __future__ import annotations

import json
import re
from typing import Any

from nativeforge.services.source_connectors.grants_gov_shaped import (
    _infer_tribal_signals_from_eligibility_body,
)

SCHEMA_VERSION = "nf_grants_gov_eligibility_parser_v2"

_TRIBAL_TYPE_IDS = frozenset({"07", "11"})
_THIN_ELIGIBILITY_DESC_RE = re.compile(
    r"^(see section|see the |refer to the |for eligibility information)",
    re.IGNORECASE,
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", " ", text).replace("&sect;", "§").strip()


def parse_grants_gov_synopsis_eligibility(
    synopsis: dict[str, Any] | None,
) -> dict[str, Any]:
    syn = synopsis or {}
    applicant_types = [
        x for x in (syn.get("applicantTypes") or []) if isinstance(x, dict)
    ]
    type_labels = [
        str(x.get("description") or "").strip()
        for x in applicant_types
        if str(x.get("description") or "").strip()
    ]
    applicant_types_text = "; ".join(type_labels)
    eligibility_desc = _strip_html(str(syn.get("applicantEligibilityDesc") or ""))
    synopsis_desc = _strip_html(str(syn.get("synopsisDesc") or ""))

    parts: list[str] = []
    if applicant_types_text:
        parts.append(f"Applicant types: {applicant_types_text}")
    if eligibility_desc:
        parts.append(eligibility_desc)
    thin_desc = (
        not eligibility_desc
        or len(eligibility_desc) < 80
        or bool(_THIN_ELIGIBILITY_DESC_RE.match(eligibility_desc.strip()))
    )
    if thin_desc and synopsis_desc:
        parts.append(synopsis_desc)
    eligibility_text = "\n\n".join(parts)

    tribal_from_types = any(
        str(x.get("id") or "") in _TRIBAL_TYPE_IDS
        or "native american tribal" in str(x.get("description") or "").lower()
        for x in applicant_types
    )
    body = "\n".join(parts)
    tribal_from_body, tags = _infer_tribal_signals_from_eligibility_body(body)
    tribal_eligible = tribal_from_types or tribal_from_body

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "applicant_types_text": applicant_types_text,
            "applicant_type_ids": [
                str(x.get("id") or "").strip()
                for x in applicant_types
                if str(x.get("id") or "").strip()
            ],
            "applicant_types_json": applicant_types,
            "applicant_eligibility_desc": eligibility_desc,
            "synopsis_desc_included": thin_desc and bool(synopsis_desc),
            "eligibility_text": eligibility_text,
            "tribal_eligible": tribal_eligible,
            "eligibility_tags": tags,
        }
    )
