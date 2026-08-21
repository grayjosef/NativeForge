"""State source packet contract + Top-15 builder + confidence resolver (Block 30)."""

from __future__ import annotations

import hashlib
import json
from typing import Any

SCHEMA_VERSION = "nf_state_source_packet_contract_v1"

SOURCE_STATUSES = frozenset(
    {
        "identified",
        "needs_research",
        "needs_review",
        "validated_read_only",
        "unsupported",
        "unknown",
    }
)

VALIDATION_STATUSES = frozenset(
    {
        "not_started",
        "packet_created",
        "source_identified",
        "read_only_checked",
        "needs_human_review",
        "validated_for_demo",
        "not_live",
    }
)

TOP15 = (
    ("SC", "South Carolina"),
    ("OK", "Oklahoma"),
    ("AZ", "Arizona"),
    ("NM", "New Mexico"),
    ("AK", "Alaska"),
    ("CA", "California"),
    ("WA", "Washington"),
    ("OR", "Oregon"),
    ("MT", "Montana"),
    ("SD", "South Dakota"),
    ("ND", "North Dakota"),
    ("MN", "Minnesota"),
    ("WI", "Wisconsin"),
    ("NC", "North Carolina"),
    ("HI", "Hawaii"),
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def make_state_source_packet_id(state_code: str) -> str:
    raw = f"ssp::{state_code}".encode()
    return f"ssp_{hashlib.sha256(raw).hexdigest()[:16]}"


def build_state_source_packet(
    *,
    state_code: str,
    state_name: str,
    coverage_ranking_id: str | None = None,
    state_grant_portal_urls: list[str] | None = None,
    state_agency_sources: list[str] | None = None,
    native_specific_sources: list[str] | None = None,
    foundation_sources: list[str] | None = None,
    rural_community_sources: list[str] | None = None,
    education_workforce_sources: list[str] | None = None,
    health_housing_infrastructure_sources: list[str] | None = None,
    recognition_sources: list[str] | None = None,
    source_status: str = "needs_research",
    freshness_status: str = "unknown",
    validation_status: str = "packet_created",
    live_check_supported: bool = False,
    live_check_run: bool = False,
    human_review_required: bool = True,
    inclusion_reason: str = "",
    confidence: str = "low",
    next_validation_action: str = "Research state portal and Native-relevant sources",
    active_lane: bool = False,
) -> dict[str, Any]:
    ss = source_status if source_status in SOURCE_STATUSES else "unknown"
    vs = validation_status if validation_status in VALIDATION_STATUSES else "not_started"
    # Live coverage only if actually supported AND run AND validated
    live = bool(
        live_check_supported
        and live_check_run
        and vs in {"read_only_checked", "validated_for_demo"}
    )
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "state_source_packet_id": make_state_source_packet_id(state_code),
            "state_code": state_code.upper(),
            "state_name": state_name,
            "coverage_ranking_id": coverage_ranking_id
            or f"cov_seed_{state_code.upper()}",
            "state_grant_portal_urls": list(state_grant_portal_urls or []),
            "state_agency_sources": list(state_agency_sources or []),
            "native_specific_sources": list(native_specific_sources or []),
            "foundation_sources": list(foundation_sources or []),
            "rural_community_sources": list(rural_community_sources or []),
            "education_workforce_sources": list(education_workforce_sources or []),
            "health_housing_infrastructure_sources": list(
                health_housing_infrastructure_sources or []
            ),
            "recognition_sources": list(recognition_sources or []),
            "source_status": ss,
            "freshness_status": freshness_status,
            "validation_status": vs,
            "live_check_supported": bool(live_check_supported),
            "live_check_run": bool(live_check_run),
            "human_review_required": bool(human_review_required),
            "coverage_live_claimed": live,
            "inclusion_reason": inclusion_reason,
            "confidence": confidence,
            "next_validation_action": next_validation_action,
            "active_customer_lane": bool(active_lane),
            "all_portals_integrated_claimed": False,
            "all_opportunities_current_claimed": False,
            "final_eligibility_claimed": False,
        }
    )


def state_source_packet_invariant_failures(packet: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    if packet.get("source_status") not in SOURCE_STATUSES:
        fails.append("bad_source_status")
    if packet.get("validation_status") not in VALIDATION_STATUSES:
        fails.append("bad_validation_status")
    if packet.get("coverage_live_claimed") is True:
        if not packet.get("live_check_supported"):
            fails.append("live_without_support")
        if not packet.get("live_check_run"):
            fails.append("live_without_run")
    for key in (
        "all_portals_integrated_claimed",
        "all_opportunities_current_claimed",
        "final_eligibility_claimed",
    ):
        if packet.get(key) is True:
            fails.append(key)
    return fails


def resolve_coverage_confidence(packet: dict[str, Any]) -> dict[str, Any]:
    identified = packet.get("source_status") in {
        "identified",
        "needs_review",
        "validated_read_only",
    }
    reviewed = packet.get("validation_status") in {
        "needs_human_review",
        "validated_for_demo",
        "read_only_checked",
    }
    read_only = packet.get("validation_status") in {
        "read_only_checked",
        "validated_for_demo",
    }
    freshness_known = packet.get("freshness_status") not in {None, "unknown", ""}
    recog = bool(packet.get("recognition_sources"))
    cats = any(
        packet.get(k)
        for k in (
            "native_specific_sources",
            "education_workforce_sources",
            "health_housing_infrastructure_sources",
            "rural_community_sources",
        )
    )
    live_run = bool(packet.get("live_check_run") and packet.get("live_check_supported"))

    score = sum(
        [
            15 if identified else 0,
            15 if reviewed else 0,
            20 if read_only else 0,
            15 if freshness_known else 0,
            15 if recog else 0,
            10 if cats else 0,
            10 if live_run else 0,
        ]
    )
    if score >= 80:
        conf = "high"
    elif score >= 50:
        conf = "medium"
    elif score >= 25:
        conf = "low"
    else:
        conf = "unknown"

    live = bool(
        packet.get("coverage_live_claimed")
        and live_run
        and read_only
    )
    blockers = []
    if not identified:
        blockers.append("sources_not_identified")
    if not freshness_known:
        blockers.append("freshness_unknown")
    if not live_run:
        blockers.append("live_check_not_run")
    if packet.get("human_review_required") and packet.get("validation_status") not in {
        "validated_for_demo",
        "read_only_checked",
    }:
        blockers.append("human_review_pending")

    return _json_safe(
        {
            "state_code": packet.get("state_code"),
            "coverage_confidence": conf,
            "confidence_score": score,
            "freshness_status": packet.get("freshness_status"),
            "coverage_live_claimed": live,
            "next_safe_action": packet.get("next_validation_action"),
            "blocker_reasons": blockers,
        }
    )


def build_top15_state_source_packets() -> list[dict[str, Any]]:
    packets: list[dict[str, Any]] = []
    for code, name in TOP15:
        if code == "SC":
            pkt = build_state_source_packet(
                state_code=code,
                state_name=name,
                state_grant_portal_urls=[
                    "https://www.sc.gov/ (portal inventory needs program-level mapping)"
                ],
                state_agency_sources=["SC curated demo agency fixtures"],
                native_specific_sources=["SC Monday demo Native-relevant pack"],
                rural_community_sources=["SC community development demo fixtures"],
                education_workforce_sources=["SC education/workforce fixture stubs"],
                health_housing_infrastructure_sources=[
                    "SC health/housing fixture stubs"
                ],
                recognition_sources=[
                    "BIA/Federal_Register_placeholder (Catawba)",
                    "SC state recognition list placeholder",
                ],
                source_status="identified",
                freshness_status="curated_current_demo",
                validation_status="validated_for_demo",
                live_check_supported=False,
                live_check_run=False,
                inclusion_reason="Active customer/demo lane with curated-current fixtures",
                confidence="medium",
                next_validation_action=(
                    "Expand SC portal program mapping; keep curated-current honesty"
                ),
                active_lane=True,
            )
        else:
            pkt = build_state_source_packet(
                state_code=code,
                state_name=name,
                state_grant_portal_urls=[],
                state_agency_sources=[],
                native_specific_sources=[],
                recognition_sources=["needs_research"],
                source_status="needs_research",
                freshness_status="unknown",
                validation_status="packet_created",
                live_check_supported=False,
                live_check_run=False,
                inclusion_reason=(
                    f"Provisional Top-15 seed for {name}; source inventory not live"
                ),
                confidence="low",
                next_validation_action=(
                    f"Identify {code} grant portal + Native-relevant agency sources"
                ),
                active_lane=False,
            )
        packets.append(pkt)
    return packets
