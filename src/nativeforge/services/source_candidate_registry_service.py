"""Sprint 37: deterministic Source Candidate Registry from coverage plan / source_quality."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from nativeforge.domain.enums import OperatorDecisionSeverity
from nativeforge.services import source_coverage_plan_service as scp_svc

SCHEMA_VERSION = "nf_source_candidate_registry_v1"

_STRONG_POSTURE_PRIORITY_CAP = OperatorDecisionSeverity.medium.value

_PRIORITY_ORDER: tuple[str, ...] = (
    OperatorDecisionSeverity.info.value,
    OperatorDecisionSeverity.low.value,
    OperatorDecisionSeverity.medium.value,
    OperatorDecisionSeverity.high.value,
    OperatorDecisionSeverity.critical.value,
)

_REVIEW_INTERVAL_DAYS: dict[str, int] = {
    "critical": 7,
    "weak": 14,
    "adequate": 30,
    "strong": 90,
}

# Deterministic candidate seeds: planning targets only — not eligibility confirmation.
_CANDIDATE_SEEDS: dict[str, list[dict[str, str]]] = {
    "federal_native_specific": [
        {
            "source_name": "BIA Grants",
            "source_type": "federal",
            "suggested_url_pattern_or_search_target": "bia.gov grants tribal programs",
            "expected_native_relevance": "high_programmatic_alignment_with_federally_recognized_tribes",
            "expected_update_frequency": "program_cycle_driven",
        },
        {
            "source_name": "IHS Division of Grants Management",
            "source_type": "federal",
            "suggested_url_pattern_or_search_target": "ihs.gov grants management tribal health",
            "expected_native_relevance": "high_health_program_alignment_for_tribal_communities",
            "expected_update_frequency": "annual_program_cycles",
        },
        {
            "source_name": "Administration for Native Americans",
            "source_type": "federal",
            "suggested_url_pattern_or_search_target": "acf.hhs.gov ana funding NOFO",
            "expected_native_relevance": "high_native_community_development_alignment",
            "expected_update_frequency": "periodic_NOFO_releases",
        },
        {
            "source_name": "DOJ CTAS",
            "source_type": "federal",
            "suggested_url_pattern_or_search_target": "justice.gov tribal ctas solicitation",
            "expected_native_relevance": "high_public_safety_and_tribal_justice_alignment",
            "expected_update_frequency": "annual_solicitation_cycles",
        },
        {
            "source_name": "DOE Office of Indian Energy",
            "source_type": "federal",
            "suggested_url_pattern_or_search_target": "energy.gov indianenergy funding",
            "expected_native_relevance": "high_energy_sovereignty_alignment",
            "expected_update_frequency": "periodic_competitive_cycles",
        },
        {
            "source_name": "HUD Office of Native American Programs",
            "source_type": "federal",
            "suggested_url_pattern_or_search_target": "hud.gov ONAP tribal housing grants",
            "expected_native_relevance": "high_housing_and_community_development_alignment",
            "expected_update_frequency": "program_notice_driven",
        },
        {
            "source_name": "EPA Tribal Grants",
            "source_type": "federal",
            "suggested_url_pattern_or_search_target": "epa.gov tribal grants environmental programs",
            "expected_native_relevance": "high_environmental_program_alignment_for_tribes",
            "expected_update_frequency": "seasonal_and_program_cycles",
        },
    ],
    "federal_native_relevant_broad": [
        {
            "source_name": "Grants.gov tribal eligible opportunities",
            "source_type": "federal",
            "suggested_url_pattern_or_search_target": "grants.gov search tribal eligibility keywords",
            "expected_native_relevance": "catalog_review_required_before_claiming_eligibility",
            "expected_update_frequency": "daily_catalog_updates",
        },
        {
            "source_name": "SAM.gov Assistance Listings",
            "source_type": "federal",
            "suggested_url_pattern_or_search_target": "sam.gov assistance listings CFDA tribal",
            "expected_native_relevance": "broad_federal_catalog_human_review_for_native_fit",
            "expected_update_frequency": "frequent_metadata_updates",
        },
        {
            "source_name": "Federal Register NOFO notices",
            "source_type": "federal",
            "suggested_url_pattern_or_search_target": "federalregister.gov NOFO tribal native",
            "expected_native_relevance": "notice_level_signals_require_publisher_rules_review",
            "expected_update_frequency": "continuous_notice_stream",
        },
        {
            "source_name": "USDA Rural Development tribal-relevant programs",
            "source_type": "federal",
            "suggested_url_pattern_or_search_target": "rd.usda.gov tribal rural programs",
            "expected_native_relevance": "rural_program_fit_requires_human_review_for_tribal_applicants",
            "expected_update_frequency": "program_cycle_driven",
        },
        {
            "source_name": "FEMA tribal hazard mitigation / preparedness",
            "source_type": "federal",
            "suggested_url_pattern_or_search_target": "fema.gov tribal mitigation preparedness grants",
            "expected_native_relevance": "hazard_program_alignment_review_before_activation",
            "expected_update_frequency": "disaster_cycle_and_NOFO_driven",
        },
        {
            "source_name": "DOT / FHWA Tribal Transportation",
            "source_type": "federal",
            "suggested_url_pattern_or_search_target": "transportation.gov tribal transportation programs",
            "expected_native_relevance": "transportation_program_fit_review_for_tribal_recipients",
            "expected_update_frequency": "program_cycle_driven",
        },
    ],
    "foundation_native_serving": [
        {
            "source_name": "Native Americans in Philanthropy",
            "source_type": "foundation",
            "suggested_url_pattern_or_search_target": "nativephilanthropy.org initiatives grants",
            "expected_native_relevance": "high_philanthropic_native_network_alignment",
            "expected_update_frequency": "quarterly_initiative_updates",
        },
        {
            "source_name": "First Nations Development Institute",
            "source_type": "foundation",
            "suggested_url_pattern_or_search_target": "firstnations.org grants RFP",
            "expected_native_relevance": "high_native_community_economic_development_alignment",
            "expected_update_frequency": "RFP_driven_cycles",
        },
        {
            "source_name": "NDN Collective",
            "source_type": "foundation",
            "suggested_url_pattern_or_search_target": "ndncollective.org funding opportunities",
            "expected_native_relevance": "high_native_led_movement_alignment",
            "expected_update_frequency": "campaign_driven_releases",
        },
        {
            "source_name": "Bush Foundation Native Nations",
            "source_type": "foundation",
            "suggested_url_pattern_or_search_target": "bushfoundation.org native nations",
            "expected_native_relevance": "regional_native_governance_and_leadership_alignment",
            "expected_update_frequency": "annual_or_semiannual_cycles",
        },
        {
            "source_name": (
                "Robert Wood Johnson Foundation health equity Native-relevant grants"
            ),
            "source_type": "foundation",
            "suggested_url_pattern_or_search_target": "rwjf.org grants tribal health equity",
            "expected_native_relevance": "health_equity_fit_requires_human_review_for_native_communities",
            "expected_update_frequency": "foundation_cycle_driven",
        },
        {
            "source_name": ("Ford Foundation Indigenous rights / civic power grants"),
            "source_type": "foundation",
            "suggested_url_pattern_or_search_target": "fordfoundation.org indigenous rights grants",
            "expected_native_relevance": "civic_power_alignment_review_before_activation",
            "expected_update_frequency": "foundation_cycle_driven",
        },
    ],
    "corporate_philanthropy": [
        {
            "source_name": "Corporate foundation Native community grants",
            "source_type": "corporate",
            "suggested_url_pattern_or_search_target": "corporate foundation CSR tribal Native community",
            "expected_native_relevance": "csr_fit_requires_human_review_and_geography_checks",
            "expected_update_frequency": "annual_giving_cycles",
        },
        {
            "source_name": "Broadband philanthropy Native-relevant programs",
            "source_type": "corporate",
            "suggested_url_pattern_or_search_target": "digital equity philanthropy tribal broadband",
            "expected_native_relevance": "digital_equity_alignment_review_required",
            "expected_update_frequency": "initiative_driven",
        },
        {
            "source_name": "Energy sovereignty philanthropy",
            "source_type": "corporate",
            "suggested_url_pattern_or_search_target": "renewable energy philanthropy tribal sovereignty",
            "expected_native_relevance": "energy_transition_fit_human_review_required",
            "expected_update_frequency": "program_cycle_driven",
        },
        {
            "source_name": "Health equity corporate giving programs",
            "source_type": "corporate",
            "suggested_url_pattern_or_search_target": "health equity corporate grants tribal",
            "expected_native_relevance": "health_equity_fit_human_review_required",
            "expected_update_frequency": "annual_cycles",
        },
        {
            "source_name": "Workforce / education corporate giving programs",
            "source_type": "corporate",
            "suggested_url_pattern_or_search_target": "workforce education corporate grants Native",
            "expected_native_relevance": "education_workforce_fit_human_review_required",
            "expected_update_frequency": "annual_cycles",
        },
    ],
    "university_research": [
        {
            "source_name": "Tribal college research opportunities",
            "source_type": "university",
            "suggested_url_pattern_or_search_target": "tribal college research office sponsored programs",
            "expected_native_relevance": "high_tcu_research_alignment",
            "expected_update_frequency": "academic_year_cycles",
        },
        {
            "source_name": "Indigenous research institute grants",
            "source_type": "university",
            "suggested_url_pattern_or_search_target": "Indigenous research institute RFP university",
            "expected_native_relevance": "research_alignment_review_before_activation",
            "expected_update_frequency": "RFP_driven",
        },
        {
            "source_name": "University community partnership grants",
            "source_type": "university",
            "suggested_url_pattern_or_search_target": "university community engaged research tribal partnership",
            "expected_native_relevance": "partnership_fit_human_review_required",
            "expected_update_frequency": "semester_and_RFP_cycles",
        },
        {
            "source_name": "NSF / NIH broader impacts tribal partnership opportunities",
            "source_type": "university",
            "suggested_url_pattern_or_search_target": "nsf.gov nih.gov broader impacts tribal partnership",
            "expected_native_relevance": "sponsor_rules_review_required_not_keyword_native_alone",
            "expected_update_frequency": "sponsor_deadline_driven",
        },
    ],
    "general_broad_with_native_eligibility": [
        {
            "source_name": "Rural broadband programs",
            "source_type": "private",
            "suggested_url_pattern_or_search_target": "rural broadband funding tribal eligibility review",
            "expected_native_relevance": "broad_eligibility_human_review_required_not_keyword_confirmation",
            "expected_update_frequency": "program_cycle_driven",
        },
        {
            "source_name": "Health equity programs",
            "source_type": "private",
            "suggested_url_pattern_or_search_target": "health equity grants tribal eligibility human review",
            "expected_native_relevance": "broad_eligibility_human_review_required_not_keyword_confirmation",
            "expected_update_frequency": "program_cycle_driven",
        },
        {
            "source_name": "Environmental justice programs",
            "source_type": "private",
            "suggested_url_pattern_or_search_target": "environmental justice grants tribal communities review",
            "expected_native_relevance": "broad_eligibility_human_review_required_not_keyword_confirmation",
            "expected_update_frequency": "program_cycle_driven",
        },
        {
            "source_name": "Housing programs",
            "source_type": "private",
            "suggested_url_pattern_or_search_target": "housing programs tribal eligibility human review",
            "expected_native_relevance": "broad_eligibility_human_review_required_not_keyword_confirmation",
            "expected_update_frequency": "program_cycle_driven",
        },
        {
            "source_name": "Workforce development programs",
            "source_type": "private",
            "suggested_url_pattern_or_search_target": "workforce development tribal eligibility review",
            "expected_native_relevance": "broad_eligibility_human_review_required_not_keyword_confirmation",
            "expected_update_frequency": "program_cycle_driven",
        },
        {
            "source_name": "Education access programs",
            "source_type": "private",
            "suggested_url_pattern_or_search_target": "education access programs Native entities eligibility review",
            "expected_native_relevance": "broad_eligibility_human_review_required_not_keyword_confirmation",
            "expected_update_frequency": "program_cycle_driven",
        },
    ],
    "tribal_government": [
        {
            "source_name": "Tribal nation compact and grant portals",
            "source_type": "tribal",
            "suggested_url_pattern_or_search_target": "tribal government grants portal compact programs",
            "expected_native_relevance": "high_tribal_government_program_alignment",
            "expected_update_frequency": "tribal_publication_cadence",
        },
    ],
    "tribal_college": [
        {
            "source_name": "Tribal college sponsored programs office",
            "source_type": "university",
            "suggested_url_pattern_or_search_target": "TCU sponsored programs opportunities",
            "expected_native_relevance": "high_tcu_program_alignment",
            "expected_update_frequency": "academic_year_cycles",
        },
    ],
    "native_nonprofit": [
        {
            "source_name": "Native-led nonprofit institutional funders",
            "source_type": "nonprofit",
            "suggested_url_pattern_or_search_target": "Native-led 501(c)(3) grants programs",
            "expected_native_relevance": "high_native_institutional_alignment",
            "expected_update_frequency": "annual_cycles",
        },
    ],
    "alaska_native": [
        {
            "source_name": "Alaska Native corporation and village priority programs",
            "source_type": "nonprofit",
            "suggested_url_pattern_or_search_target": "Alaska Native regional programs grants",
            "expected_native_relevance": "high_alaska_native_alignment_review_geo_rules",
            "expected_update_frequency": "state_and_regional_cycles",
        },
    ],
    "native_hawaiian": [
        {
            "source_name": "Native Hawaiian organization community funds",
            "source_type": "nonprofit",
            "suggested_url_pattern_or_search_target": "Native Hawaiian organization grants Hawaiʻi",
            "expected_native_relevance": "high_native_hawaiian_alignment_review_geo_rules",
            "expected_update_frequency": "regional_cycles",
        },
    ],
    "state_local_native_relevant": [
        {
            "source_name": "State broadband and equity offices (Native-relevant)",
            "source_type": "state",
            "suggested_url_pattern_or_search_target": "state broadband office grants tribal eligibility",
            "expected_native_relevance": "state_program_fit_human_review_for_tribal_applicants",
            "expected_update_frequency": "state_program_cycles",
        },
    ],
}


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _candidate_id(org_id: str, lane: str, source_name: str) -> str:
    payload = f"{org_id}|{lane}|{source_name}|nf_source_candidate_registry_v1".encode()
    digest = hashlib.sha256(payload).hexdigest()
    return f"nf_src_candidate_v1_{digest[:24]}"


def _cap_priority(priority: str, *, posture: str) -> str:
    if posture != "strong":
        return priority
    if priority not in _PRIORITY_ORDER:
        return _STRONG_POSTURE_PRIORITY_CAP
    cap_i = _PRIORITY_ORDER.index(_STRONG_POSTURE_PRIORITY_CAP)
    p_i = _PRIORITY_ORDER.index(priority)
    return _PRIORITY_ORDER[min(p_i, cap_i)]


def _lane_priority_to_candidate_priority(
    lane_priority: str,
    *,
    posture: str,
    lane: str,
    plan_status: str,
) -> str:
    raw = lane_priority
    if lane == "federal_native_specific" and plan_status in {"missing", "weak"}:
        if raw not in {
            OperatorDecisionSeverity.critical.value,
            OperatorDecisionSeverity.high.value,
        }:
            raw = OperatorDecisionSeverity.high.value
    return _cap_priority(raw, posture=posture)


def _onboarding_readiness(
    lane: str,
    *,
    seed_idx: int,
    source_name: str,
) -> str:
    if lane == "general_broad_with_native_eligibility":
        return "needs_research"
    low_risk = {"Grants.gov", "SAM.gov", "Federal Register"}
    if any(x in source_name for x in low_risk):
        return "legal_tos_review_required"
    if (
        lane in {"corporate_philanthropy", "foundation_native_serving"}
        and seed_idx >= 4
    ):
        return "deferred"
    if "human review" in source_name.lower() or "review" in source_name.lower():
        return "needs_research"
    return "ready_for_review"


def _candidate_rationale(
    lane: str,
    plan_status: str,
    *,
    posture: str,
    balancing: bool,
) -> str:
    base = (
        "Planning candidate only—no live ingestion or activation is implied; operator review is "
        "required before any registry activation."
    )
    if balancing:
        return (
            "Portfolio lane concentration: add underrepresented doctrine coverage through new "
            "candidates—existing active sources remain in place; diversification adds breadth rather "
            "than narrowing the portfolio. " + base
        )
    if lane == "general_broad_with_native_eligibility":
        return (
            "Broad Native-eligible program class—human review is required; keyword-only Native "
            "relevance does not confirm eligibility (Native-first, not Native-only). "
            + base
        )
    if plan_status == "overrepresented":
        return (
            "Balancing diversification candidate for underrepresented lanes—existing registry rows "
            "stay active; add breadth elsewhere. " + base
        )
    if posture == "strong" and plan_status == "healthy":
        return (
            "Maintenance-scale verification candidate for a healthy lane—periodic diligence rather "
            "than emergency-scale expansion. " + base
        )
    if posture == "strong":
        return (
            "Strong registry posture—treat as maintenance and hardening rather than emergency-scale "
            "expansion. " + base
        )
    return base


def _per_candidate_risk_flags(
    lane: str,
    onboarding_readiness: str,
) -> list[str]:
    flags: list[str] = []
    if onboarding_readiness == "legal_tos_review_required":
        flags.append("publisher_terms_review_required")
    if lane == "general_broad_with_native_eligibility":
        flags.append("broad_eligibility_human_review_gate")
    return flags


def _registry_risk_flags(
    candidates: list[dict[str, Any]],
    deferred_n: int,
) -> list[str]:
    flags: list[str] = []
    lanes_with = {c["lane"] for c in candidates}
    if not candidates:
        flags.append("no_candidate_sources")
    if "federal_native_specific" not in lanes_with:
        flags.append("no_federal_native_specific_candidates")
    if "foundation_native_serving" not in lanes_with:
        flags.append("no_foundation_candidates")
    if "corporate_philanthropy" not in lanes_with:
        flags.append("no_corporate_philanthropy_candidates")
    if "general_broad_with_native_eligibility" not in lanes_with:
        flags.append("no_broad_native_eligibility_candidates")
    if deferred_n >= max(3, len(candidates) // 2) and len(candidates) > 0:
        flags.append("too_many_deferred_candidates")
    if any(
        "legal_tos_review_required" == c.get("onboarding_readiness") for c in candidates
    ):
        flags.append("legal_tos_review_required")
    return sorted(set(flags))


def _pick_templates(
    lane: str,
    n: int,
    *,
    start: int = 0,
) -> list[tuple[int, dict[str, str]]]:
    seeds = _CANDIDATE_SEEDS.get(lane, [])
    out: list[tuple[int, dict[str, str]]] = []
    if n <= 0 or not seeds:
        return out
    for i in range(start, start + n):
        out.append((i, seeds[i % len(seeds)]))
    return out


def _emit_for_lane(
    lane: str,
    plan_row: dict[str, Any],
    sq: dict[str, Any],
    *,
    posture: str,
    balancing: bool,
    max_count: int,
    start_index: int,
) -> list[dict[str, Any]]:
    status = str(plan_row.get("status") or "")
    org_id = str(sq.get("organization_id") or "")
    lane_pri = str(plan_row.get("priority") or OperatorDecisionSeverity.medium.value)
    cand_pri = _lane_priority_to_candidate_priority(
        lane_pri, posture=posture, lane=lane, plan_status=status
    )
    evidence = list(plan_row.get("evidence_refs") or [])
    out: list[dict[str, Any]] = []
    for idx, seed in _pick_templates(lane, max_count, start=start_index):
        name = seed["source_name"]
        oid = _candidate_id(org_id, lane, name)
        readiness = _onboarding_readiness(lane, seed_idx=idx, source_name=name)
        cand = {
            "candidate_id": oid,
            "lane": lane,
            "source_name": name,
            "source_type": seed["source_type"],
            "priority": cand_pri,
            "rationale": _candidate_rationale(
                lane, status, posture=posture, balancing=balancing
            ),
            "suggested_url_pattern_or_search_target": seed[
                "suggested_url_pattern_or_search_target"
            ],
            "expected_native_relevance": seed["expected_native_relevance"],
            "expected_update_frequency": seed["expected_update_frequency"],
            "review_status": "candidate_review_required",
            "onboarding_readiness": readiness,
            "risk_flags": _per_candidate_risk_flags(lane, readiness),
            "evidence_refs": list(evidence),
            "next_operator_step": str(plan_row.get("next_operator_step") or ""),
            "can_become_active_source": False,
            "should_create_action": False,
        }
        out.append(_json_safe(cand))
    return out


def _minimum_viable_candidates(
    sq: dict[str, Any],
    detail_by_lane: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    """Empty org / critical posture: federal_native_specific-led minimum viable set."""
    out: list[dict[str, Any]] = []
    fed_row = detail_by_lane.get("federal_native_specific") or {}
    out.extend(
        _emit_for_lane(
            "federal_native_specific",
            fed_row
            or {
                "lane": "federal_native_specific",
                "status": "missing",
                "priority": OperatorDecisionSeverity.critical.value,
                "evidence_refs": [],
                "next_operator_step": "Add federal Native-specific registry sources after review.",
            },
            sq,
            posture=str(sq.get("posture") or "critical"),
            balancing=False,
            max_count=len(_CANDIDATE_SEEDS["federal_native_specific"]),
            start_index=0,
        )
    )
    for lane, n in (
        ("foundation_native_serving", 2),
        ("corporate_philanthropy", 2),
        ("general_broad_with_native_eligibility", 2),
        ("federal_native_relevant_broad", 2),
    ):
        row = detail_by_lane.get(lane) or {}
        merged = dict(row)
        merged.setdefault("lane", lane)
        merged.setdefault("status", "missing")
        merged.setdefault(
            "priority",
            OperatorDecisionSeverity.medium.value,
        )
        merged.setdefault("evidence_refs", row.get("evidence_refs") or [])
        merged.setdefault(
            "next_operator_step",
            str(row.get("next_operator_step") or "Review candidate targets."),
        )
        out.extend(
            _emit_for_lane(
                lane,
                merged,
                sq,
                posture=str(sq.get("posture") or "critical"),
                balancing=False,
                max_count=n,
                start_index=0,
            )
        )
    return out


def _needed_seed_count(plan_row: dict[str, Any], *, posture: str) -> int:
    status = str(plan_row.get("status") or "")
    lane = str(plan_row.get("lane") or "")
    cur = int(plan_row.get("current_source_count") or 0)
    tgt = int(plan_row.get("target_source_count") or 0)
    seeds_len = len(_CANDIDATE_SEEDS.get(lane, ()))
    if seeds_len == 0:
        return 0
    if status in {"missing", "weak"}:
        need = (
            max(1, tgt - cur) if tgt > cur else (3 if status == "weak" else seeds_len)
        )
        return min(seeds_len, max(1, min(need, seeds_len)))
    if status == "healthy" and posture == "strong":
        return 1 if lane == "federal_native_specific" else 0
    return 0


def build_source_candidate_registry(source_quality: dict[str, Any]) -> dict[str, Any]:
    """Return nf_source_candidate_registry_v1 given nf_discovery_source_quality_v1 (+ embedded plan)."""
    sq = dict(source_quality)
    plan = sq.get("source_coverage_plan") or scp_svc.build_source_coverage_plan(sq)
    posture = str(sq.get("posture") or "adequate")
    dqs = int(sq.get("data_quality_score") or 0)
    active_n = int((sq.get("source_counts") or {}).get("active") or 0)
    org_id = str(sq.get("organization_id") or "")
    gen_at = sq.get("generated_at") or ""

    detail_by_lane: dict[str, dict[str, Any]] = {}
    for row in plan.get("priority_lanes") or []:
        ln = row.get("lane")
        if isinstance(ln, str) and ln:
            detail_by_lane[ln] = row

    candidates: list[dict[str, Any]] = []

    if active_n == 0 or posture == "critical":
        candidates.extend(_minimum_viable_candidates(sq, detail_by_lane))
    else:
        over_lanes = {
            str(x.get("lane"))
            for x in (plan.get("priority_lanes") or [])
            if str(x.get("status") or "") == "overrepresented"
        }
        balancing_targets: list[str] = []
        if over_lanes:
            for row in plan.get("priority_lanes") or []:
                ln = str(row.get("lane") or "")
                st = str(row.get("status") or "")
                if ln and st in {"missing", "weak"}:
                    balancing_targets.append(ln)
            balancing_targets = sorted(set(balancing_targets))

        for row in plan.get("priority_lanes") or []:
            lane = str(row.get("lane") or "")
            if not lane:
                continue
            status = str(row.get("status") or "")
            balancing = lane in balancing_targets and status in {"missing", "weak"}

            if status == "overrepresented":
                continue

            n = _needed_seed_count(row, posture=posture)
            if balancing:
                n = max(n, 2)
            if n == 0:
                continue

            candidates.extend(
                _emit_for_lane(
                    lane,
                    row,
                    sq,
                    posture=posture,
                    balancing=balancing,
                    max_count=n,
                    start_index=0,
                )
            )

        if over_lanes and balancing_targets:
            for bl in balancing_targets:
                brow = detail_by_lane.get(bl) or {}
                row = dict(brow)
                row.setdefault("lane", bl)
                row.setdefault("status", "missing")
                row.setdefault("priority", OperatorDecisionSeverity.medium.value)
                row.setdefault("evidence_refs", brow.get("evidence_refs") or [])
                row.setdefault(
                    "next_operator_step",
                    str(brow.get("next_operator_step") or ""),
                )
                already = {c["candidate_id"] for c in candidates}
                emitted = _emit_for_lane(
                    bl,
                    row,
                    sq,
                    posture=posture,
                    balancing=True,
                    max_count=2,
                    start_index=0,
                )
                for c in emitted:
                    if c["candidate_id"] not in already:
                        candidates.append(c)
                        already.add(c["candidate_id"])

    if not candidates and active_n > 0:
        fr = detail_by_lane.get("federal_native_specific") or {
            "lane": "federal_native_specific",
            "status": "healthy",
            "priority": OperatorDecisionSeverity.low.value,
            "current_source_count": 0,
            "target_source_count": 1,
            "evidence_refs": [],
            "next_operator_step": "Periodic verification of federal Native-specific coverage.",
        }
        candidates.extend(
            _emit_for_lane(
                "federal_native_specific",
                fr,
                sq,
                posture=posture,
                balancing=False,
                max_count=1,
                start_index=0,
            )
        )

    # Dedupe deterministic order
    seen: set[str] = set()
    deduped: list[dict[str, Any]] = []
    for c in candidates:
        cid = str(c.get("candidate_id") or "")
        if cid in seen:
            continue
        seen.add(cid)
        deduped.append(c)

    deferred_n = sum(1 for c in deduped if c.get("onboarding_readiness") == "deferred")
    high_pri_n = sum(
        1
        for c in deduped
        if c.get("priority")
        in {
            OperatorDecisionSeverity.high.value,
            OperatorDecisionSeverity.critical.value,
        }
    )

    seq_plan: list[dict[str, Any]] = []
    by_lane_ids: dict[str, list[str]] = {}
    for c in deduped:
        by_lane_ids.setdefault(str(c.get("lane")), []).append(
            str(c.get("candidate_id"))
        )

    for lane_k in by_lane_ids:
        by_lane_ids[lane_k] = sorted(by_lane_ids[lane_k])

    for st in plan.get("sequenced_plan") or []:
        lanes = list(st.get("focus_lanes") or [])
        cids: list[str] = []
        for ln in lanes:
            cids.extend(by_lane_ids.get(ln, []))
        cids = sorted(set(cids))
        seq_plan.append(
            _json_safe(
                {
                    "step_number": int(st.get("step_number") or 0),
                    "action_type": str(st.get("action_type") or ""),
                    "priority": str(st.get("priority") or ""),
                    "title": str(st.get("title") or ""),
                    "rationale": str(st.get("rationale") or ""),
                    "candidate_ids": cids,
                    "focus_lanes": sorted(set(lanes)),
                    "depends_on": list(st.get("depends_on") or []),
                    "should_create_action": False,
                }
            )
        )

    review_days = int(_REVIEW_INTERVAL_DAYS.get(posture, 30))

    summary = _registry_summary(
        org_id=org_id,
        posture=posture,
        candidate_n=len(deduped),
        plan_summary=str(plan.get("summary") or ""),
    )

    out: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "organization_scope": {
            "organization_id": org_id,
            "generated_at": gen_at,
        },
        "registry_posture": {
            "source_quality_posture": posture,
            "data_quality_score": dqs,
            "active_source_count": active_n,
            "candidate_count": len(deduped),
            "high_priority_candidate_count": high_pri_n,
        },
        "candidate_sources": deduped,
        "sequenced_onboarding_plan": seq_plan,
        "risk_flags": _registry_risk_flags(deduped, deferred_n),
        "summary": summary,
        "recommended_review_interval_days": review_days,
    }
    return _json_safe(out)


def _registry_summary(
    *,
    org_id: str,
    posture: str,
    candidate_n: int,
    plan_summary: str,
) -> str:
    if posture == "strong":
        return (
            f"Organization {org_id}: candidate registry is maintenance-focused ({candidate_n} "
            "reviewable targets); activation remains gated - no live ingestion implied."
        )
    return (
        f"Organization {org_id}: {candidate_n} deterministic source candidates derived from coverage "
        f"gaps - review-only planning payload. Context: {plan_summary}"
    )
