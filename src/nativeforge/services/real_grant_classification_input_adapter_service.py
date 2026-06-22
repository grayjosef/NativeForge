"""Sprint 323: adapt real ingested grant payloads to Stage 6 classifier input."""

from __future__ import annotations

import json
import re
from typing import Any

SCHEMA_VERSION = "nf_real_grant_classification_input_adapter_v1"

_TRIBAL_TYPE_RE = re.compile(
    r"native american tribal|federally recognized tribe|indian tribe|tribal government",
    re.IGNORECASE,
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def derive_explicit_source_evidence(grant: dict[str, Any]) -> list[str]:
    """Evidence codes ONLY from fields present in the real source payload."""
    codes: list[str] = []
    if grant.get("tribal_set_aside") is True:
        codes.append("tribal_set_aside_in_source")
    if grant.get("tribal_eligible") is True:
        codes.append("tribal_eligible_in_source")
    elig = str(grant.get("eligibility_text") or "")
    if grant.get("applicant_types_include_tribal") is True or _TRIBAL_TYPE_RE.search(elig):
        codes.append("applicant_types_tribal_in_source")
    tags = grant.get("eligibility_tags") or []
    structural = {
        "tribal_eligible",
        "tribal_government",
        "federally_recognized_tribe",
        "native_serving_nonprofit",
    }
    if structural & {str(t) for t in tags}:
        codes.append("eligibility_tag_structural_in_source")
    if grant.get("native_only_mandate") is True:
        codes.append("native_only_mandate_in_source")
    return sorted(set(codes))


def adapt_grant_to_classification_input(grant: dict[str, Any]) -> dict[str, Any]:
    """Map real grant → classifier raw input; evidence derived, never invented."""
    evidence = derive_explicit_source_evidence(grant)
    applicant_tribal = grant.get("applicant_types_include_tribal")
    if applicant_tribal is None and _TRIBAL_TYPE_RE.search(
        str(grant.get("eligibility_text") or "")
    ):
        applicant_tribal = True
    return _json_safe(
        {
            "fixture_key": str(grant.get("grant_id") or grant.get("opportunity_number")),
            "opportunity_title": str(
                grant.get("opportunity_title") or grant.get("title") or ""
            ),
            "tribal_eligible": bool(grant.get("tribal_eligible")),
            "tribal_set_aside": bool(grant.get("tribal_set_aside")),
            "tribal_priority_points": bool(grant.get("tribal_priority_points")),
            "applicant_types_include_tribal": applicant_tribal,
            "eligibility_tags": list(grant.get("eligibility_tags") or []),
            "explicit_source_evidence": evidence,
            "eligibility_text": str(grant.get("eligibility_text") or ""),
            "source_seed_id": grant.get("source_seed_id"),
            "real_fetch": grant.get("real_fetch"),
            "from_real_source_text": True,
        }
    )
