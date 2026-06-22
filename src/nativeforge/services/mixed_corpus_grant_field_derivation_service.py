"""Sprint 332: derive mixed-corpus classification fields from real source text."""

from __future__ import annotations

import json
import re
from typing import Any

from nativeforge.services.grants_gov_eligibility_parser_service import (
    parse_grants_gov_synopsis_eligibility,
)

SCHEMA_VERSION = "nf_mixed_corpus_grant_field_derivation_v1"

_SET_ASIDE_RE = re.compile(r"\bset[- ]asides?\b", re.IGNORECASE)
_PRIORITY_RE = re.compile(
    r"(priority|preference|points).{0,80}(trib|indian)|(trib|indian).{0,80}(priority|preference|points)",
    re.IGNORECASE | re.DOTALL,
)
_UNRESTRICTED_RE = re.compile(r"unrestricted|open to any type", re.IGNORECASE)
_TRIBAL_TYPE_RE = re.compile(
    r"native american tribal|federally recognized tribe",
    re.IGNORECASE,
)
_NATIVE_SERVING_RE = re.compile(r"native[- ]serving", re.IGNORECASE)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _source_blob(grant: dict[str, Any], synopsis: dict[str, Any] | None = None) -> str:
    parts = [str(grant.get("eligibility_text") or "")]
    if synopsis:
        parts.append(str(synopsis.get("synopsisDesc") or ""))
        parts.append(str(synopsis.get("applicantEligibilityDesc") or ""))
    elif grant.get("synopsis"):
        parts.append(str(grant.get("synopsis") or ""))
    return "\n".join(p for p in parts if p)


def derive_tribe_eligible_broad(
    grant: dict[str, Any],
    *,
    synopsis: dict[str, Any] | None = None,
    tribal_type_present: bool = False,
    applicant_type_count: int = 0,
) -> bool:
    """True when tribes can apply among broad entity types (guard input)."""
    elig = str(grant.get("eligibility_text") or "")
    if _UNRESTRICTED_RE.search(elig):
        return True
    if tribal_type_present and applicant_type_count > 2:
        return True
    blob = _source_blob(grant, synopsis).lower()
    if "indian tribe" in blob and "state" in blob:
        return True
    if grant.get("tribal_eligible") is True and not grant.get("tribal_set_aside"):
        return True
    return False


def derive_mixed_corpus_grant_fields(
    grant: dict[str, Any],
    *,
    synopsis: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Augment grant dict with classification fields derived only from source text."""
    out = dict(grant)
    syn = synopsis or {}
    if not syn and out.get("synopsis"):
        syn = {"synopsisDesc": out.get("synopsis")}

    parsed = parse_grants_gov_synopsis_eligibility(syn if syn else None)
    blob = _source_blob(out, syn if syn else None)
    low = blob.lower()

    types = syn.get("applicantTypes") or []
    tribal_type_present = any(
        _TRIBAL_TYPE_RE.search(str(t.get("description") or "")) for t in types
    )

    out["tribal_set_aside"] = bool(
        _SET_ASIDE_RE.search(blob) and re.search(r"trib|indian|native", low)
    )
    out["tribal_priority_points"] = bool(_PRIORITY_RE.search(blob))

    if parsed.get("eligibility_text") and not out.get("eligibility_text"):
        out["eligibility_text"] = parsed["eligibility_text"]
    if parsed.get("tribal_eligible") is not None:
        out["tribal_eligible"] = parsed["tribal_eligible"]

    tags = list(out.get("eligibility_tags") or parsed.get("eligibility_tags") or [])
    if _NATIVE_SERVING_RE.search(blob) and not out.get("tribal_eligible"):
        if "native_serving_nonprofit" not in tags:
            tags.append("native_serving_nonprofit")
    if ("urban indian" in low or "ihs service" in low) and not out.get("tribal_eligible"):
        if "ihs_service_population" not in tags:
            tags.append("ihs_service_population")
    out["eligibility_tags"] = tags

    if tribal_type_present:
        out["applicant_types_include_tribal"] = True
    elif _UNRESTRICTED_RE.search(str(out.get("eligibility_text") or "")):
        out["applicant_types_include_tribal"] = None
    elif out.get("applicant_types_include_tribal") is None:
        out["applicant_types_include_tribal"] = False

    if out.get("tribal_eligible") and not tribal_type_present:
        out["applicant_types_include_tribal"] = False

    out["tribe_eligible_broad"] = derive_tribe_eligible_broad(
        out,
        synopsis=syn if syn else None,
        tribal_type_present=tribal_type_present,
        applicant_type_count=len(types),
    )
    return _json_safe(out)


def build_mixed_corpus_field_derivation_contract() -> dict[str, Any]:
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "derived_from_source_text_only": True,
            "never_synthesized": True,
            "preview_only": True,
        }
    )
