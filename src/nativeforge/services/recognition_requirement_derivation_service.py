"""SC-1: derive recognition_requirement from rules + eligibility text (honest UNKNOWN)."""

from __future__ import annotations

import json
import re
from typing import Any

from nativeforge.services.grants_gov_applicant_type_recognition_service import (
    derive_recognition_from_grant_applicant_types,
)
from nativeforge.services.sc_pilot_fixture_loader_service import (
    RECOGNITION_REQUIREMENTS,
    load_sc_eligibility_rules,
    match_sc_rule_category,
)

SCHEMA_VERSION = "nf_recognition_requirement_derivation_v2"

_FEDERAL_ONLY_RE = re.compile(
    r"federally\s+recognized\s+(?:american\s+)?indian|only\s+federally\s+recognized|"
    r"only\s+indian\s+tribes|only\s+federally\s+recognized\s+tribal|"
    r"Native American tribal governments \(Federally recognized\)",
    re.IGNORECASE,
)
_STATE_OK_RE = re.compile(
    r"state[- ]recognized|non[- ]federally\s+recognized|native\s+american\s+organizations|"
    r"native\s+serving\s+nonprofit|urban\s+indian",
    re.IGNORECASE,
)
_STATE_OK_BOILERPLATE_RE = re.compile(
    r"\btribal\s+organi[sz]ations?\b",
    re.IGNORECASE,
)
_OPEN_NONPROFIT_RE = re.compile(
    r"501\s*\(\s*c\s*\)\s*3|nonprofit|non-profit",
    re.IGNORECASE,
)
_FEDERAL_AGENCY_RE = re.compile(r"\bBIA\b|Bureau of Indian Affairs|\bIHS\b|Indian Health Service", re.I)
_FEDERAL_PROGRAM_RE = re.compile(r"\b638\b|\bIHBG\b|NAHASDA|Self-Governance\s+Compact", re.I)
_DUAL_PATHWAY_FEDERAL_RE = re.compile(
    r"10\.766|community\s+facilities|11\.3|economic\s+development\s+administration|\bEDA\b|"
    r"USDA\s+CF",
    re.I,
)
_BIA_ALN_RE = re.compile(r"\b15\.\d{3}\b")
_ANA_ALN_RE = re.compile(r"\b93\.(587|612)\b")

_RULE_CONFLICT_MIN_SCORE = 3


def _attribute_derivation_source(base_source: str, grant: dict[str, Any]) -> str:
    """Tag forecast-sourced eligibility when derivation used merged API text."""
    if base_source in {"text", "applicant_types"} and grant.get("eligibility_text_source") == "forecast":
        return "forecast"
    return base_source


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _haystack(grant: dict[str, Any]) -> str:
    return " ".join(
        str(grant.get(k) or "")
        for k in (
            "opportunity_title",
            "eligibility_text",
            "synopsis",
            "agency",
            "program_title",
            "opportunity_number",
        )
    )


def _rule_match_with_score(
    grant: dict[str, Any],
    rules: dict[str, Any],
) -> tuple[str | None, int, dict[str, Any] | None]:
    cat = match_sc_rule_category(grant, rules)
    if not cat:
        return None, 0, None
    hay = _haystack(grant)
    agency = str(grant.get("agency") or "")
    title = str(grant.get("opportunity_title") or "")
    opp_num = str(grant.get("opportunity_number") or "")
    score = 0
    title_pats = cat.get("title_patterns") or []
    if any(p.lower() in title.lower() for p in title_pats if p):
        score += 3
    aln = str(cat.get("aln") or "")
    if aln and aln not in {"N/A", "STATE_ONLY"}:
        for token in re.split(r"[/\s,]+", aln):
            token = token.strip()
            if token and token.replace(".", "").isdigit() and token in hay + opp_num:
                score += 2
                break
    text_pats = cat.get("text_patterns") or []
    if any(re.search(p, hay, re.I) for p in text_pats):
        score += 2
    agency_pats = cat.get("agency_patterns") or []
    if any(p.lower() in agency.lower() for p in agency_pats):
        score += 1
    if score <= 0:
        return None, 0, None
    return str(cat["recognition_requirement"]), score, cat


def _derive_from_others_eligibility_body(grant: dict[str, Any]) -> str | None:
    """Parse eligibility body when Grants.gov applicant type is Others (25) only."""
    hay = _haystack(grant)
    if _STATE_OK_RE.search(hay) or _STATE_OK_BOILERPLATE_RE.search(hay):
        return "state_ok"
    if _FEDERAL_ONLY_RE.search(hay) and not _STATE_OK_RE.search(hay):
        return "federal_required"
    if _OPEN_NONPROFIT_RE.search(hay):
        return "open_nonprofit"
    return None


def _derive_from_text_body(
    grant: dict[str, Any],
    *,
    skip_state_ok_boilerplate: bool = False,
) -> str | None:
    hay = _haystack(grant)
    title = str(grant.get("opportunity_title") or "")
    agency = str(grant.get("agency") or "")

    if _DUAL_PATHWAY_FEDERAL_RE.search(hay) and (
        re.search(r"nonprofit|501\s*\(\s*c", hay, re.I) or grant.get("dual_pathway")
    ):
        return "federal_required_for_tribal_pathway"

    if _FEDERAL_ONLY_RE.search(hay):
        if skip_state_ok_boilerplate:
            if _STATE_OK_RE.search(hay) and not _STATE_OK_BOILERPLATE_RE.search(hay):
                return None
        elif _STATE_OK_RE.search(hay):
            return None
        return "federal_required"

    if _FEDERAL_AGENCY_RE.search(agency) and _FEDERAL_PROGRAM_RE.search(f"{title} {hay}"):
        return "federal_required"
    if _FEDERAL_PROGRAM_RE.search(title) and _FEDERAL_AGENCY_RE.search(f"{agency} {hay}"):
        return "federal_required"

    if not skip_state_ok_boilerplate and _STATE_OK_RE.search(hay):
        return "state_ok"
    if _OPEN_NONPROFIT_RE.search(hay) and grant.get("tier") == 3:
        return "open_nonprofit"
    return None


def _derive_from_text(
    grant: dict[str, Any],
    *,
    structured_applicant_types_used: bool = False,
) -> str | None:
    result = _derive_from_text_body(
        grant,
        skip_state_ok_boilerplate=structured_applicant_types_used,
    )
    if result == "federal_required" and not structured_applicant_types_used:
        if _STATE_OK_RE.search(_haystack(grant)):
            return None
    return result


def _derive_from_aln_agency(grant: dict[str, Any]) -> str | None:
    hay = _haystack(grant)
    agency = str(grant.get("agency") or "")
    if _ANA_ALN_RE.search(hay):
        return "state_ok"
    if _BIA_ALN_RE.search(hay) and _FEDERAL_AGENCY_RE.search(agency):
        return "federal_required"
    return None


def derive_recognition_requirement_bundle(
    grant: dict[str, Any],
    *,
    rules: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Derive recognition requirement with provenance.

    Order: explicit → applicant types → SC rules → text → ALN/agency → UNKNOWN.
    """
    explicit = grant.get("recognition_requirement")
    if explicit and str(explicit) in RECOGNITION_REQUIREMENTS and not grant.get(
        "recognition_requirement_derived"
    ):
        return _json_safe(
            {
                "recognition_requirement": str(explicit),
                "recognition_requirement_source": "explicit",
                "recognition_requirement_conflict": False,
            }
        )

    rule_doc = rules if rules is not None else load_sc_eligibility_rules(require_files=False)
    from_rules, rule_score, _cat = _rule_match_with_score(grant, rule_doc)

    applicant = derive_recognition_from_grant_applicant_types(grant)
    from_applicant = applicant.get("recognition_requirement") if applicant else None

    if from_applicant and from_rules and from_applicant != from_rules:
        if rule_score >= _RULE_CONFLICT_MIN_SCORE:
            return _json_safe(
                {
                    "recognition_requirement": "unknown",
                    "recognition_requirement_source": "conflict",
                    "recognition_requirement_conflict": True,
                    "recognition_requirement_candidates": {
                        "applicant_types": from_applicant,
                        "rules": from_rules,
                    },
                    "applicant_type_ids": applicant.get("applicant_type_ids") if applicant else None,
                    "requires_501c3_from_applicant_types": applicant.get(
                        "requires_501c3_from_applicant_types"
                    )
                    if applicant
                    else None,
                    "dual_pathway_from_applicant_types": applicant.get(
                        "dual_pathway_from_applicant_types"
                    )
                    if applicant
                    else None,
                }
            )

    if from_applicant:
        out = {
            "recognition_requirement": from_applicant,
            "recognition_requirement_source": _attribute_derivation_source(
                "applicant_types", grant
            ),
            "recognition_requirement_conflict": False,
            "applicant_type_ids": applicant.get("applicant_type_ids"),
        }
        if applicant.get("requires_501c3_from_applicant_types") is not None:
            out["requires_501c3_from_applicant_types"] = applicant[
                "requires_501c3_from_applicant_types"
            ]
        if applicant.get("dual_pathway_from_applicant_types"):
            out["dual_pathway_from_applicant_types"] = applicant[
                "dual_pathway_from_applicant_types"
            ]
        return _json_safe(out)

    if from_rules:
        return _json_safe(
            {
                "recognition_requirement": from_rules,
                "recognition_requirement_source": "rules",
                "recognition_requirement_conflict": False,
                "rule_match_score": rule_score,
            }
        )

    from_text = _derive_from_text(grant, structured_applicant_types_used=False)
    if from_text:
        return _json_safe(
            {
                "recognition_requirement": from_text,
                "recognition_requirement_source": _attribute_derivation_source("text", grant),
                "recognition_requirement_conflict": False,
            }
        )

    from_aln = _derive_from_aln_agency(grant)
    if from_aln:
        return _json_safe(
            {
                "recognition_requirement": from_aln,
                "recognition_requirement_source": "aln_agency",
                "recognition_requirement_conflict": False,
            }
        )

    return _json_safe(
        {
            "recognition_requirement": str(rule_doc.get("default_requirement") or "unknown"),
            "recognition_requirement_source": "unknown",
            "recognition_requirement_conflict": False,
        }
    )


def derive_recognition_requirement_from_grant(
    grant: dict[str, Any],
    *,
    rules: dict[str, Any] | None = None,
) -> str:
    """Return recognition_requirement; unknown when ambiguous — never guessed."""
    return str(
        derive_recognition_requirement_bundle(grant, rules=rules)["recognition_requirement"]
    )


def enrich_grant_with_recognition_requirement(
    grant: dict[str, Any],
    *,
    rules: dict[str, Any] | None = None,
) -> dict[str, Any]:
    out = dict(grant)
    bundle = derive_recognition_requirement_bundle(grant, rules=rules)
    out.update(bundle)
    out["recognition_requirement_derived"] = grant.get("recognition_requirement") is None
    return _json_safe(out)


def enrich_opportunity_with_recognition_requirement(
    opportunity: dict[str, Any],
    *,
    grant: dict[str, Any] | None = None,
    rules: dict[str, Any] | None = None,
) -> dict[str, Any]:
    source = grant or opportunity
    out = dict(opportunity)
    bundle = derive_recognition_requirement_bundle(source, rules=rules)
    out.update(bundle)
    return _json_safe(out)
