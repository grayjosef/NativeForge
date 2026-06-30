"""SC-0: load operator-provided SC pilot fixtures — no synthesis."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "nf_sc_pilot_fixture_loader_v1"
PROFILES_SCHEMA = "sc_tribal_profiles_v1"
RULES_SCHEMA = "sc_eligibility_rules_v1"
RESEARCH_PROFILES_FORMAT = "sc_tribal_profiles_research_v1"
RESEARCH_RULES_FORMAT = "sc_eligibility_rules_research_v1"

RECOGNITION_TYPES: frozenset[str] = frozenset({"federal", "state_only"})
RECOGNITION_REQUIREMENTS: frozenset[str] = frozenset(
    {
        "federal_required",
        "federal_required_for_tribal_pathway",
        "state_ok",
        "open_nonprofit",
        "unknown",
    }
)
TRI_STATE_VALUES: frozenset[str] = frozenset({"true", "false", "unknown"})

_SC_PILOT_DIR = (
    Path(__file__).resolve().parents[3] / "fixtures" / "sc_pilot"
)
PROFILES_PATH = _SC_PILOT_DIR / "sc_tribal_profiles.json"
RULES_PATH = _SC_PILOT_DIR / "sc_eligibility_rules.json"


class ScPilotFixtureError(FileNotFoundError):
    """Operator fixtures missing or invalid."""


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def fixtures_present() -> dict[str, bool]:
    return {
        "profiles": PROFILES_PATH.is_file(),
        "rules": RULES_PATH.is_file(),
    }


def require_sc_pilot_fixtures() -> None:
    missing = [name for name, ok in fixtures_present().items() if not ok]
    if missing:
        raise ScPilotFixtureError(
            f"SC pilot fixtures missing in {_SC_PILOT_DIR}: {', '.join(missing)}. "
            "Place operator-sourced sc_tribal_profiles.json and sc_eligibility_rules.json "
            "— do not synthesize tribe or eligibility data."
        )


def _unwrap_field(row: dict[str, Any], field: str) -> tuple[Any, dict[str, Any] | None]:
    raw = row.get(field)
    if raw is None:
        return None, None
    if isinstance(raw, dict) and "value" in raw:
        meta = {k: v for k, v in raw.items() if k != "value"}
        return raw.get("value"), meta
    return raw, None


def _fixture_key_from_name(name: str) -> str:
    slug = name.strip().lower()
    if slug.startswith("the "):
        slug = slug[4:]
    slug = re.sub(r"[^a-z0-9]+", "_", slug).strip("_")
    return f"sc_pilot_{slug}"


def _normalize_has_501c3(value: Any, meta: dict[str, Any] | None) -> tuple[Any, dict[str, Any]]:
    extra: dict[str, Any] = {}
    if meta:
        if meta.get("ein"):
            extra["has_501c3_ein"] = meta["ein"]
        if meta.get("verify_note"):
            extra["has_501c3_verify_note"] = meta["verify_note"]
        if meta.get("legal_name"):
            extra["has_501c3_legal_name"] = meta["legal_name"]
    if value is True or value is False:
        return value, extra
    if str(value).lower() in TRI_STATE_VALUES:
        return str(value).lower(), extra
    return "unknown", extra


def _normalize_research_profile(row: dict[str, Any]) -> dict[str, Any]:
    name_val, _ = _unwrap_field(row, "name")
    if not name_val:
        raise ValueError("research profile missing name.value")
    org_name = str(name_val)
    fk = str(row.get("fixture_key") or _fixture_key_from_name(org_name))

    rec_type, _ = _unwrap_field(row, "recognition_type")
    if rec_type not in RECOGNITION_TYPES:
        raise ValueError(f"invalid recognition_type on profile {fk!r}: {rec_type!r}")

    inc_val, _ = _unwrap_field(row, "incorporated")
    has_val, has_meta = _unwrap_field(row, "has_501c3")
    has_501, has_extra = _normalize_has_501c3(has_val, has_meta)

    fiscal_val, _ = _unwrap_field(row, "fiscal_sponsor_available")
    if fiscal_val == "UNKNOWN":
        fiscal_val = None

    app_type, _ = _unwrap_field(row, "applicant_type")
    geo, _ = _unwrap_field(row, "service_geography")
    prog, _ = _unwrap_field(row, "program_areas")

    capture = str(row.get("capture_method") or "public_inferred")
    field_sources = {
        field: row.get(field)
        for field in row
        if isinstance(row.get(field), dict) and "provenance" in row[field]
    }

    profile: dict[str, Any] = {
        "fixture_key": fk,
        "organization_name": org_name,
        "recognition_type": rec_type,
        "applicant_type": app_type or "tribal_government",
        "incorporated": inc_val if inc_val is not None else "unknown",
        "has_501c3": has_501 if has_501 is not None else "unknown",
        "fiscal_sponsor_available": fiscal_val,
        "service_geography": geo,
        "program_areas": prog,
        "capture_method": capture,
        "provenance": {
            "format": RESEARCH_PROFILES_FORMAT,
            "capture_method": capture,
            "field_sources": field_sources,
        },
        **has_extra,
    }
    _validate_profile(profile)
    return profile


def _normalize_tri_state_field(value: Any, field_name: str) -> None:
    if value is None:
        return
    if isinstance(value, bool):
        return
    if str(value) in TRI_STATE_VALUES:
        return
    raise ValueError(f"profile field {field_name!r} must be true|false|unknown or boolean")


def _validate_profile(row: dict[str, Any]) -> None:
    if not row.get("fixture_key"):
        raise ValueError("profile missing fixture_key")
    rt = str(row.get("recognition_type") or "")
    if rt not in RECOGNITION_TYPES:
        raise ValueError(f"invalid recognition_type: {rt!r}")
    if not row.get("organization_name"):
        raise ValueError("profile missing organization_name")
    if row.get("provenance") is None:
        raise ValueError("profile missing provenance")
    for field in ("incorporated", "has_501c3"):
        _normalize_tri_state_field(row.get(field), field)
    fs = row.get("fiscal_sponsor_available")
    if fs is not None and fs != "unknown" and not isinstance(fs, bool):
        if str(fs) not in TRI_STATE_VALUES:
            raise ValueError("fiscal_sponsor_available must be boolean or unknown when present")


def load_sc_tribal_profiles(*, require_files: bool = True) -> list[dict[str, Any]]:
    if require_files:
        require_sc_pilot_fixtures()
    if not PROFILES_PATH.is_file():
        return []
    raw = json.loads(PROFILES_PATH.read_text(encoding="utf-8"))

    if isinstance(raw, list):
        profiles = [_normalize_research_profile(row) for row in raw]
    elif str(raw.get("schema_version") or "") == PROFILES_SCHEMA:
        profiles = list(raw.get("profiles") or [])
        for p in profiles:
            _validate_profile(p)
    else:
        raise ValueError(
            f"sc_tribal_profiles.json: expected {PROFILES_SCHEMA!r} object or "
            f"research profile array — got {type(raw).__name__}"
        )
    if len(profiles) != 10:
        raise ValueError(f"expected 10 SC tribal profiles, got {len(profiles)}")
    return _json_safe(profiles)


def _normalize_recognition_requirement(req: str) -> str:
    req = str(req or "unknown")
    if req == "federal_required_for_grantee":
        return "federal_required"
    if req in RECOGNITION_REQUIREMENTS:
        return req
    raise ValueError(f"invalid recognition_requirement: {req!r}")


def _conditions_from_additional(additional: list[str]) -> dict[str, bool]:
    flags = {str(x) for x in additional}
    return {
        "requires_incorporation": "incorporated_required" in flags,
        "requires_501c3": "501c3_required" in flags
        or "501c3_required_or_fiscal_sponsor" in flags,
        "individual_only": "individual_only" in flags
        or "not_tribal_org" in flags,
    }


def _normalize_operator_category(cat: dict[str, Any]) -> dict[str, Any]:
    cat_id = str(cat.get("id") or cat.get("category_id") or "")
    if not cat_id:
        raise ValueError("rule category missing id/category_id")
    req = _normalize_recognition_requirement(str(cat.get("recognition_requirement") or "unknown"))
    cond = _conditions_from_additional(list(cat.get("additional_conditions") or []))
    dual_raw = cat.get("dual_pathway")
    dual_pathway: dict[str, Any] = {}
    if dual_raw:
        dual_pathway["nonprofit_alternative"] = True
        dual_pathway["note"] = str(dual_raw)

    label = str(cat.get("label") or "")
    title_patterns = [label] if label else []
    if "SEDS" in cat_id:
        title_patterns.extend(["Social & Economic Development", "SEDS"])
    if "638" in cat_id or cat_id == "BIA_638":
        title_patterns.extend(["638", "Self-Determination", "P.L. 93-638"])
    if cat_id == "USDA_CF_TRIBAL":
        title_patterns.extend(["Community Facilities", "USDA CF", "10.766"])
    if cat_id == "EDA_INDIGENOUS_TRIBAL":
        title_patterns.extend(["Indigenous Communities", "EDA"])
    if cat_id.startswith("IHS_INDIVIDUAL"):
        title_patterns.extend(["Scholarship", "IHS Preparatory"])

    agency_patterns: list[str] = []
    if cat_id.startswith("ANA") or "ANA" in label.upper():
        agency_patterns.append("ANA")
    if cat_id.startswith("BIA") or "BIA" in label:
        agency_patterns.append("BIA")
    if cat_id.startswith("IHS"):
        agency_patterns.append("IHS")
    if cat_id.startswith("USDA"):
        agency_patterns.append("USDA")
    if cat_id.startswith("EDA"):
        agency_patterns.append("EDA")
    if cat_id.startswith("NEA"):
        agency_patterns.append("NEA")
    if cat_id.startswith("NEH"):
        agency_patterns.append("NEH")
    if cat_id.startswith("HUD"):
        agency_patterns.append("HUD")
    if cat_id.startswith("EPA"):
        agency_patterns.append("EPA")

    return {
        "category_id": cat_id,
        "label": label,
        "aln": cat.get("aln"),
        "recognition_requirement": req,
        "requires_incorporation": cond["requires_incorporation"],
        "requires_501c3": cond["requires_501c3"],
        "individual_only": cond["individual_only"],
        "dual_pathway": dual_pathway,
        "title_patterns": title_patterns,
        "agency_patterns": agency_patterns,
        "text_patterns": [],
        "source": cat.get("source"),
    }


def _normalize_rules_document(raw: dict[str, Any]) -> dict[str, Any]:
    if str(raw.get("schema_version") or "") == RULES_SCHEMA:
        categories = list(raw.get("categories") or [])
        for cat in categories:
            _validate_rule_category(cat)
        default = str(raw.get("default_requirement") or "unknown")
        if default not in RECOGNITION_REQUIREMENTS:
            raise ValueError(f"invalid default_requirement: {default!r}")
        return {
            "schema_version": RULES_SCHEMA,
            "source_format": RULES_SCHEMA,
            "categories": categories,
            "default_requirement": default,
            "metadata": raw.get("metadata"),
        }

    part4 = raw.get("part_4_machine_usable_ruleset") or {}
    operator_cats = list(part4.get("categories") or [])
    if not operator_cats:
        raise ValueError("sc_eligibility_rules.json: no categories in part_4_machine_usable_ruleset")
    categories = [_normalize_operator_category(c) for c in operator_cats]
    for cat in categories:
        _validate_rule_category(cat)
    return {
        "schema_version": RULES_SCHEMA,
        "source_format": RESEARCH_RULES_FORMAT,
        "categories": categories,
        "default_requirement": "unknown",
        "metadata": raw.get("metadata"),
        "part_1_sc_state_recognized_tribes": raw.get("part_1_sc_state_recognized_tribes"),
    }


def _validate_rule_category(cat: dict[str, Any]) -> None:
    req = str(cat.get("recognition_requirement") or "")
    if req not in RECOGNITION_REQUIREMENTS - {"unknown"}:
        raise ValueError(f"invalid recognition_requirement on category: {req!r}")
    if not cat.get("category_id"):
        raise ValueError("rule category missing category_id")
    for flag in ("requires_incorporation", "requires_501c3", "individual_only"):
        val = cat.get(flag)
        if val is not None and not isinstance(val, bool):
            raise ValueError(f"category {cat.get('category_id')!r}: {flag} must be boolean")
    dp = cat.get("dual_pathway")
    if dp is not None:
        if not isinstance(dp, dict):
            raise ValueError(f"category {cat.get('category_id')!r}: dual_pathway must be object")
        npa = dp.get("nonprofit_alternative")
        if npa is not None and not isinstance(npa, bool):
            raise ValueError(
                f"category {cat.get('category_id')!r}: dual_pathway.nonprofit_alternative must be boolean"
            )


def load_sc_eligibility_rules(*, require_files: bool = True) -> dict[str, Any]:
    if require_files:
        require_sc_pilot_fixtures()
    if not RULES_PATH.is_file():
        return {"schema_version": RULES_SCHEMA, "categories": [], "default_requirement": "unknown"}
    raw = json.loads(RULES_PATH.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("sc_eligibility_rules.json must be a JSON object")
    doc = _normalize_rules_document(raw)
    if len(doc["categories"]) < 1:
        raise ValueError("sc_eligibility_rules.json: categories must not be empty")
    return _json_safe(doc)


def match_sc_rule_category(
    grant: dict[str, Any],
    rules: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Match grant to operator rules category (rules-file primary)."""
    rule_doc = rules if rules is not None else load_sc_eligibility_rules(require_files=False)
    hay = " ".join(
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
    agency = str(grant.get("agency") or "")
    title = str(grant.get("opportunity_title") or "")
    opp_num = str(grant.get("opportunity_number") or "")

    explicit_cat = grant.get("sc_rule_category_id")
    if explicit_cat:
        for cat in rule_doc.get("categories") or []:
            if cat.get("category_id") == explicit_cat:
                return cat

    best: dict[str, Any] | None = None
    best_score = 0
    for cat in rule_doc.get("categories") or []:
        score = 0
        agency_pats = cat.get("agency_patterns") or []
        title_pats = cat.get("title_patterns") or []
        text_pats = cat.get("text_patterns") or []
        if any(p.lower() in title.lower() for p in title_pats if p):
            score += 3
        aln = str(cat.get("aln") or "")
        if aln and aln not in {"N/A", "STATE_ONLY"}:
            for token in re.split(r"[/\s,]+", aln):
                token = token.strip()
                if token and token.replace(".", "").isdigit() and token in hay + opp_num:
                    score += 2
                    break
        if any(re.search(p, hay, re.I) for p in text_pats):
            score += 2
        if any(p.lower() in agency.lower() for p in agency_pats):
            score += 1
        if score > best_score:
            best_score = score
            best = cat
    return best if best_score > 0 else None


def build_sc_pilot_rule_reference_grants(
    rules: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Minimal grant rows from operator rules categories — eligibility sourced from rules file only."""
    rule_doc = rules if rules is not None else load_sc_eligibility_rules(require_files=False)
    grants: list[dict[str, Any]] = []
    for cat in rule_doc.get("categories") or []:
        grants.append(
            {
                "grant_id": f"sc-rule-{cat['category_id']}",
                "opportunity_title": cat.get("label") or cat["category_id"],
                "opportunity_number": str(cat.get("aln") or cat["category_id"]),
                "agency": (cat.get("agency_patterns") or ["SC Pilot Rules"])[0],
                "eligibility_text": str(cat.get("source") or ""),
                "tribal_eligible": True,
                "application_deadline": "2026-12-31",
                "sc_rule_category_id": cat["category_id"],
                "recognition_requirement": cat["recognition_requirement"],
                "requires_incorporation": cat.get("requires_incorporation"),
                "requires_501c3": cat.get("requires_501c3"),
                "individual_only": cat.get("individual_only"),
                "dual_pathway": cat.get("dual_pathway"),
                "sc_pilot_rule_reference": True,
                "fixture": True,
            }
        )
    return grants


def build_sc_pilot_fixture_contract() -> dict[str, Any]:
    present = fixtures_present()
    ready = all(present.values())
    profile_count = 0
    category_count = 0
    if ready:
        profile_count = len(load_sc_tribal_profiles(require_files=False))
        category_count = len(load_sc_eligibility_rules(require_files=False).get("categories") or [])
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "fixtures_dir": str(_SC_PILOT_DIR),
            "fixtures_present": present,
            "ready": ready,
            "profiles_schema": PROFILES_SCHEMA,
            "rules_schema": RULES_SCHEMA,
            "profile_count": profile_count,
            "rule_category_count": category_count,
        }
    )
