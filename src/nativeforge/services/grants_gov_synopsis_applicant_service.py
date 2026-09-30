"""Grants.gov fetchOpportunity synopsis/forecast → canonical applicant eligibility (V1).

Authoritative source fields (verified on fixture ``grants_gov_fetch_opportunity_362648``):

| Source path | Semantics |
|-------------|-----------|
| ``synopsis.applicantTypes[]`` | Structured eligible applicant type codes + descriptions |
| ``synopsis.applicantEligibilityDesc`` | Additional eligibility prose |
| ``synopsis.synopsisDesc`` | Merged into eligibility_text when desc is thin |
| ``forecast.applicantTypes[]`` | Forecast applicant types (merged) |
| ``forecast.applicantEligibilityDesc`` | Forecast eligibility prose |

Canonical targets: ``eligible_applicant_codes``, ``eligibility_text``.

Code semantics for Gate 173: ``native_eligibility_code_classification_service``
(07/11/08 direct tribal; 99/25 requires_reading).
"""

from __future__ import annotations

import re
from typing import Any

from nativeforge.services.grants_gov_eligibility_parser_service import (
    parse_grants_gov_opportunity_eligibility,
)
from nativeforge.services.native_eligibility_code_classification_service import (
    DIRECT_TRIBAL_CODES,
    NATIVE_RECALL_CODES,
    REQUIRES_READING_CODES,
)

APPLICANT_ENRICHMENT_VERSION = "nf_grants_gov_synopsis_applicant_v1"
PARSER_NAME = "grants_gov_fetch_opportunity_synopsis_applicant"

_CODE_TOKEN = re.compile(r"^\d{1,2}$")


def applicant_code_mapping_reference() -> dict[str, Any]:
    return {
        "version": APPLICANT_ENRICHMENT_VERSION,
        "direct_tribal_codes": dict(DIRECT_TRIBAL_CODES),
        "requires_reading_codes": dict(REQUIRES_READING_CODES),
        "native_recall_codes": sorted(NATIVE_RECALL_CODES),
        "authority": "native_eligibility_code_classification_service + Grants.gov applicantTypes.id",
    }


def normalize_applicant_type_ids(raw_ids: list[str] | None) -> str | None:
    """Deterministic comma-separated Grants.gov applicant type ids."""
    if not raw_ids:
        return None
    cleaned: list[str] = []
    for raw in raw_ids:
        token = str(raw or "").strip()
        if not token or not _CODE_TOKEN.match(token):
            continue
        cleaned.append(token.zfill(2) if len(token) == 1 else token)
    unique = sorted(set(cleaned))
    return ",".join(unique) if unique else None


def map_detail_applicant_to_canonical(detail: dict[str, Any] | None) -> dict[str, Any]:
    parsed = parse_grants_gov_opportunity_eligibility(detail)
    codes = normalize_applicant_type_ids(list(parsed.get("applicant_type_ids") or []))
    text = str(parsed.get("eligibility_text") or "").strip()
    return {
        "enrichment_version": APPLICANT_ENRICHMENT_VERSION,
        "source_fields": {
            "applicant_type_ids": parsed.get("applicant_type_ids"),
            "applicant_types_json": parsed.get("applicant_types_json"),
            "eligibility_text_source": parsed.get("eligibility_text_source"),
        },
        "eligible_applicant_codes": codes,
        "eligibility_text": text or None,
        "applicant_types_text": parsed.get("applicant_types_text"),
        "code_mapping": applicant_code_mapping_reference(),
    }


def applicant_record_has_signal(record: dict[str, Any]) -> bool:
    return bool(
        record.get("eligible_applicant_codes") or record.get("eligibility_text")
    )
