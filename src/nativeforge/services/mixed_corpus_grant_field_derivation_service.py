"""Sprint 332: derive mixed-corpus classification fields from real source text."""

from __future__ import annotations

import json
import re
from typing import Any

from nativeforge.services.grants_gov_eligibility_parser_service import (
    parse_grants_gov_synopsis_eligibility,
)
from nativeforge.services.real_grant_classification_input_adapter_service import (
    _TRIBAL_TYPE_RE,
)

SCHEMA_VERSION = "nf_mixed_corpus_grant_field_derivation_v1"

_SET_ASIDE_RE = re.compile(r"\bset[- ]asides?\b", re.IGNORECASE)
_PRIORITY_RE = re.compile(
    r"(priority|preference|points).{0,80}(trib|indian)|(trib|indian).{0,80}(priority|preference|points)",
    re.IGNORECASE | re.DOTALL,
)
_UNRESTRICTED_RE = re.compile(r"unrestricted|open to any type", re.IGNORECASE)
_NATIVE_SERVING_RE = re.compile(r"native[- ]serving", re.IGNORECASE)

# Tribal applicant-type detection is deliberately NOT defined here. It is the
# classification lane's canonical vocabulary, imported above from
# real_grant_classification_input_adapter_service.
#
# A local copy stood at this spot until Gate 105. It shadowed the import on
# line 13 - same name, two fewer alternatives - so this module read as bridged
# while silently missing "indian tribe" and "tribal government". The failure
# was under-detection: a strict subset can only find less, never invent more.
# See docs/operations/583 and 584. Do not redefine the name here.


# Flags by which a row states that its emptiness is deliberate.
#
# Deliberately NOT including `never_synthesized`: it is a corpus-wide provenance
# assertion carried by all 40 NF-13 rows, so it discriminates nothing. A guard
# whose condition is true of everything is a coincidence, not a guard.
HONEST_EMPTINESS_FLAGS: tuple[str, ...] = ("empty_honestly", "no_live_nofo")


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _declares_honest_emptiness(grant: dict[str, Any]) -> bool:
    """Has this row said its blank fields are the truth rather than a gap?"""
    return any(grant.get(flag) is True for flag in HONEST_EMPTINESS_FLAGS)


def _parsed_eligibility_is_source_backed(parsed: dict[str, Any]) -> bool:
    """Did the parser build its eligibility_text from real eligibility fields?

    Detected from the parser's own provenance rather than trusted. When the only
    contribution was `synopsisDesc`, the result is prose *about* the opportunity
    - for an unposted NOFO, literally a note that no NOFO exists - and adopting
    it as eligibility text puts manufactured text into the evidence path that
    `derive_explicit_source_evidence` and the Tribal classifier read.
    """
    return bool(
        str(parsed.get("applicant_types_text") or "").strip()
        or str(parsed.get("applicant_eligibility_desc") or "").strip()
    )


def _negative_applicant_type_is_earned(
    *, applicant_types: Any, eligibility_text: Any
) -> bool:
    """Is there anything describing who may apply, that simply did not say Tribal?

    `False` asserts the applicant classes are known and exclude Tribes. That is a
    claim, and it needs a source. With no structured applicant types and no
    eligibility text, nobody has said who may apply, and the honest answer is
    unknown.
    """
    return bool(applicant_types) or bool(str(eligibility_text or "").strip())


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

    if (
        parsed.get("eligibility_text")
        and not out.get("eligibility_text")
        and _parsed_eligibility_is_source_backed(parsed)
        and not _declares_honest_emptiness(out)
    ):
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

    # A negative has to be earned. `False` claims the applicant types are known
    # and exclude Tribes; that needs something describing who may apply.
    negative_is_evidence_backed = _negative_applicant_type_is_earned(
        applicant_types=types, eligibility_text=out.get("eligibility_text")
    )

    if tribal_type_present:
        out["applicant_types_include_tribal"] = True
    elif _UNRESTRICTED_RE.search(str(out.get("eligibility_text") or "")):
        out["applicant_types_include_tribal"] = None
    elif out.get("applicant_types_include_tribal") is None:
        # Unknown stays unknown unless a negative was earned. Narrowing None to
        # False because nothing said otherwise inverts deny-by-default and
        # asserts more than the source supports.
        if negative_is_evidence_backed:
            out["applicant_types_include_tribal"] = False

    if out.get("tribal_eligible") and not tribal_type_present:
        if _TRIBAL_TYPE_RE.search(str(out.get("eligibility_text") or "")):
            out["applicant_types_include_tribal"] = True
        elif negative_is_evidence_backed:
            out["applicant_types_include_tribal"] = False

    # Unknown is a value, not an absence. Where derivation declined to assert
    # anything, the field is still present and explicitly None - otherwise a
    # caller reading row["applicant_types_include_tribal"] raises KeyError and
    # "we do not know" becomes indistinguishable from "this field is not part of
    # the schema".
    out.setdefault("eligibility_text", "")
    out.setdefault("applicant_types_include_tribal", None)

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
