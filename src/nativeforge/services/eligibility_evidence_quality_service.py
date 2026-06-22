"""Sprint 340: detect placeholder, empty, and insufficient eligibility evidence."""

from __future__ import annotations

import json
import re
from typing import Any

SCHEMA_VERSION = "nf_eligibility_evidence_quality_v1"

_PLACEHOLDER_RE = re.compile(
    r"^open to eligible applicants per program guidelines\.?$",
    re.IGNORECASE,
)
_SMALL_BUSINESS_ONLY_RE = re.compile(
    r"only united states small business|only.*small business concerns?\b|\bsbc[s]?\b.*only",
    re.IGNORECASE,
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def is_placeholder_eligibility(eligibility_text: str | None) -> bool:
    text = str(eligibility_text or "").strip()
    return bool(text and _PLACEHOLDER_RE.match(text))


def is_empty_eligibility(eligibility_text: str | None) -> bool:
    return not str(eligibility_text or "").strip()


def has_substantive_eligibility(eligibility_text: str | None) -> bool:
    text = str(eligibility_text or "").strip()
    if not text or is_placeholder_eligibility(text):
        return False
    return len(text) >= 40


def has_insufficient_eligibility_evidence(grant: dict[str, Any]) -> bool:
    """True when source eligibility cannot support a confident irrelevant label."""
    elig = str(grant.get("eligibility_text") or "")
    if is_empty_eligibility(elig) or is_placeholder_eligibility(elig):
        return True
    derived = grant.get("derived_evidence_codes") or grant.get("explicit_source_evidence") or []
    if not derived and not has_substantive_eligibility(elig):
        return True
    return False


def has_positive_irrelevant_evidence(raw: dict[str, Any]) -> bool:
    """Positive source proof that a grant is not tribally relevant (required for irrelevant)."""
    elig = str(raw.get("eligibility_text") or "").strip()
    if is_empty_eligibility(elig) or is_placeholder_eligibility(elig):
        return False
    if raw.get("applicant_types_include_tribal") is None:
        return False
    low = elig.lower()
    if _SMALL_BUSINESS_ONLY_RE.search(elig):
        return True
    if raw.get("applicant_types_include_tribal") is False:
        if "small business" in low and not re.search(r"trib|indian|native|indigenous", low):
            return True
        if re.search(r"tribal governments? are not eligible", low):
            return True
        if re.search(r"state departments? of transportation", low) and not re.search(
            r"trib|indian|native", low
        ):
            return True
    return False


def build_eligibility_evidence_quality_contract() -> dict[str, Any]:
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "placeholder_pattern": "open to eligible applicants per program guidelines",
            "insufficient_never_irrelevant": True,
            "preview_only": True,
        }
    )
