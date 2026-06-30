"""SC-1b: derive grant eligibility conditions + recognition requirement from rules."""

from __future__ import annotations

import json
import re
from typing import Any

from nativeforge.services.grants_gov_eligibility_completeness_service import (
    enrich_grant_with_grants_gov_completeness,
)
from nativeforge.services.recognition_requirement_derivation_service import (
    derive_recognition_requirement_bundle,
)
from nativeforge.services.sc_pilot_fixture_loader_service import (
    load_sc_eligibility_rules,
    match_sc_rule_category,
)

SCHEMA_VERSION = "nf_grant_eligibility_conditions_v2"

_INDIVIDUAL_ONLY_RE = re.compile(
    r"\bindividuals?\s+only\b|scholarship\s+for\s+students?|student\s+scholarship",
    re.IGNORECASE,
)
_INCORPORATION_RE = re.compile(
    r"incorporated\s+organi|must\s+be\s+incorporated|legally\s+incorporated",
    re.IGNORECASE,
)
_501C3_RE = re.compile(r"501\s*\(\s*c\s*\)\s*3|501c3|tax-exempt\s+nonprofit", re.IGNORECASE)
_DUAL_PATHWAY_RE = re.compile(
    r"nonprofit\s+alternative|501\s*\(\s*c\s*\)\s*3\s+organizations?\s+may\s+also|"
    r"or\s+nonprofit|tribal\s+organi[sz]ations?\s+or\s+nonprofit",
    re.IGNORECASE,
)
_USDA_CF_RE = re.compile(r"10\.766|community\s+facilities|USDA\s+CF", re.I)
_EDA_RE = re.compile(r"11\.3|economic\s+development\s+administration|\bEDA\b", re.I)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _haystack(grant: dict[str, Any]) -> str:
    return " ".join(
        str(grant.get(k) or "")
        for k in ("opportunity_title", "eligibility_text", "synopsis", "agency", "program_title")
    )


def _match_rule_category(grant: dict[str, Any], rules: dict[str, Any]) -> dict[str, Any] | None:
    return match_sc_rule_category(grant, rules)


def derive_grant_eligibility_conditions(
    grant: dict[str, Any],
    *,
    rules: dict[str, Any] | None = None,
    recognition_bundle: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Honest condition flags from explicit grant fields, then rules category, then text."""
    rule_doc = rules if rules is not None else load_sc_eligibility_rules(require_files=False)
    cat = _match_rule_category(grant, rule_doc)
    hay = _haystack(grant)
    bundle = recognition_bundle or derive_recognition_requirement_bundle(grant, rules=rule_doc)

    dual_pathway = dict(grant.get("dual_pathway") or {})
    if bundle.get("dual_pathway_from_applicant_types"):
        dual_pathway = {
            **dual_pathway,
            **dict(bundle["dual_pathway_from_applicant_types"]),
        }
    if cat and cat.get("dual_pathway"):
        dual_pathway = {**dict(cat.get("dual_pathway") or {}), **dual_pathway}

    requires_501c3_from_types = bundle.get("requires_501c3_from_applicant_types")

    conditions: dict[str, Any] = {
        "requires_incorporation": bool(grant.get("requires_incorporation"))
        if grant.get("requires_incorporation") is not None
        else bool(cat.get("requires_incorporation"))
        if cat and cat.get("requires_incorporation") is not None
        else bool(_INCORPORATION_RE.search(hay)),
        "requires_501c3": bool(grant.get("requires_501c3"))
        if grant.get("requires_501c3") is not None
        else bool(requires_501c3_from_types)
        if requires_501c3_from_types is not None
        else bool(cat.get("requires_501c3"))
        if cat and cat.get("requires_501c3") is not None
        else bool(_501C3_RE.search(hay)),
        "individual_only": bool(grant.get("individual_only"))
        if grant.get("individual_only") is not None
        else bool(cat.get("individual_only"))
        if cat and cat.get("individual_only") is not None
        else bool(_INDIVIDUAL_ONLY_RE.search(hay)),
        "dual_pathway": dual_pathway,
    }

    if not dual_pathway.get("nonprofit_alternative"):
        if _DUAL_PATHWAY_RE.search(hay) or _USDA_CF_RE.search(hay) or _EDA_RE.search(hay):
            conditions["dual_pathway"] = {
                **dual_pathway,
                "nonprofit_alternative": True,
            }

    if cat:
        conditions["matched_rule_category_id"] = cat.get("category_id")

    return _json_safe(conditions)


def enrich_grant_with_eligibility_metadata(
    grant: dict[str, Any],
    *,
    rules: dict[str, Any] | None = None,
    allow_live_completeness_fetch: bool = False,
) -> dict[str, Any]:
    rule_doc = rules if rules is not None else load_sc_eligibility_rules(require_files=False)
    completed = enrich_grant_with_grants_gov_completeness(
        grant,
        allow_live_fetch=allow_live_completeness_fetch,
    )
    bundle = derive_recognition_requirement_bundle(completed, rules=rule_doc)
    out = dict(completed)
    out.update(bundle)
    out["recognition_requirement_derived"] = grant.get("recognition_requirement") is None
    conditions = derive_grant_eligibility_conditions(
        completed, rules=rule_doc, recognition_bundle=bundle
    )
    out.update(conditions)
    return _json_safe(out)


def enrich_opportunity_with_eligibility_metadata(
    opportunity: dict[str, Any],
    *,
    grant: dict[str, Any] | None = None,
    rules: dict[str, Any] | None = None,
) -> dict[str, Any]:
    enriched = enrich_grant_with_eligibility_metadata(grant or opportunity, rules=rules)
    out = dict(opportunity)
    for key in (
        "recognition_requirement",
        "recognition_requirement_source",
        "recognition_requirement_conflict",
        "recognition_requirement_candidates",
        "recognition_requirement_derived",
        "eligibility_text_source",
        "eligibility_provenance",
        "grants_gov_attachment_inventory",
        "grants_gov_doc_type",
        "applicant_type_ids",
        "requires_incorporation",
        "requires_501c3",
        "individual_only",
        "dual_pathway",
        "matched_rule_category_id",
    ):
        if key in enriched:
            out[key] = enriched[key]
    return _json_safe(out)
