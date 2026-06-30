"""SC-1: derive recognition_requirement from rules + eligibility text (honest UNKNOWN)."""

from __future__ import annotations

import json
import re
from typing import Any

from nativeforge.services.sc_pilot_fixture_loader_service import (
    RECOGNITION_REQUIREMENTS,
    load_sc_eligibility_rules,
)

SCHEMA_VERSION = "nf_recognition_requirement_derivation_v1"

_FEDERAL_ONLY_RE = re.compile(
    r"federally\s+recognized\s+(?:american\s+)?indian|only\s+federally\s+recognized|"
    r"only\s+indian\s+tribes|only\s+federally\s+recognized\s+tribal",
    re.IGNORECASE,
)
_STATE_OK_RE = re.compile(
    r"state[- ]recognized|non[- ]federally\s+recognized|native\s+american\s+organizations|"
    r"native\s+serving\s+nonprofit|tribal\s+organizations|urban\s+indian",
    re.IGNORECASE,
)
_OPEN_NONPROFIT_RE = re.compile(
    r"501\s*\(\s*c\s*\)\s*3|nonprofit|non-profit",
    re.IGNORECASE,
)
_FEDERAL_AGENCY_RE = re.compile(r"\bBIA\b|Bureau of Indian Affairs|\bIHS\b|Indian Health Service", re.I)
_FEDERAL_PROGRAM_RE = re.compile(r"\b638\b|\bIHBG\b|NAHASDA|Self-Governance\s+Compact", re.I)


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
        )
    )


def _match_category_rules(
    grant: dict[str, Any],
    rules: dict[str, Any],
) -> str | None:
    hay = _haystack(grant)
    agency = str(grant.get("agency") or "")
    title = str(grant.get("opportunity_title") or "")
    for cat in rules.get("categories") or []:
        agency_pats = cat.get("agency_patterns") or []
        title_pats = cat.get("title_patterns") or []
        text_pats = cat.get("text_patterns") or []
        agency_hit = any(p.lower() in agency.lower() for p in agency_pats)
        title_hit = any(p.lower() in title.lower() for p in title_pats)
        text_hit = any(re.search(p, hay, re.I) for p in text_pats)
        if agency_hit or title_hit or text_hit:
            return str(cat["recognition_requirement"])
    return None


def _derive_from_text(grant: dict[str, Any]) -> str | None:
    hay = _haystack(grant)
    title = str(grant.get("opportunity_title") or "")
    agency = str(grant.get("agency") or "")

    # Unambiguous federal-only when explicit and no broader Native-org carve-out.
    if _FEDERAL_ONLY_RE.search(hay) and not _STATE_OK_RE.search(hay):
        return "federal_required"
    if _FEDERAL_AGENCY_RE.search(agency) and _FEDERAL_PROGRAM_RE.search(f"{title} {hay}"):
        return "federal_required"
    if _FEDERAL_PROGRAM_RE.search(title) and _FEDERAL_AGENCY_RE.search(f"{agency} {hay}"):
        return "federal_required"

    if _STATE_OK_RE.search(hay):
        return "state_ok"
    if _OPEN_NONPROFIT_RE.search(hay) and grant.get("tier") == 3:
        return "open_nonprofit"
    return None


def derive_recognition_requirement_from_grant(
    grant: dict[str, Any],
    *,
    rules: dict[str, Any] | None = None,
) -> str:
    """Return recognition_requirement; unknown when ambiguous — never guessed."""
    explicit = grant.get("recognition_requirement")
    if explicit and str(explicit) in RECOGNITION_REQUIREMENTS:
        return str(explicit)

    rule_doc = rules if rules is not None else load_sc_eligibility_rules(require_files=False)
    from_rules = _match_category_rules(grant, rule_doc)
    if from_rules:
        return from_rules

    from_text = _derive_from_text(grant)
    if from_text:
        # Conflicting signals → unknown
        if from_text == "federal_required" and _STATE_OK_RE.search(_haystack(grant)):
            return "unknown"
        return from_text

    return str(rule_doc.get("default_requirement") or "unknown")


def enrich_grant_with_recognition_requirement(
    grant: dict[str, Any],
    *,
    rules: dict[str, Any] | None = None,
) -> dict[str, Any]:
    out = dict(grant)
    req = derive_recognition_requirement_from_grant(grant, rules=rules)
    out["recognition_requirement"] = req
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
    out["recognition_requirement"] = derive_recognition_requirement_from_grant(
        source, rules=rules
    )
    return _json_safe(out)
