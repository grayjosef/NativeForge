"""Recognition routing model (Campaign Block 27).

State-recognized status is never treated as federally recognized.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

SCHEMA_VERSION = "nf_recognition_routing_contract_v1"

ENTITY_TYPES = frozenset(
    {
        "federally_recognized_tribe",
        "state_recognized_tribe",
        "native_serving_nonprofit",
        "tribal_college_university",
        "alaska_native_entity",
        "native_hawaiian_organization",
        "intertribal_consortium",
        "fiscal_sponsor_partner_org",
        "unknown_needs_verification",
    }
)

OPPORTUNITY_JURISDICTIONS = frozenset({"federal", "state", "local", "tribal", "unknown"})


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def make_recognition_routing_id(org_id: str, opportunity_id: str) -> str:
    raw = f"rr::{org_id}::{opportunity_id}".encode()
    return f"rr_{hashlib.sha256(raw).hexdigest()[:16]}"


def build_recognition_routing_record(
    *,
    organization_profile_id: str,
    entity_type: str,
    opportunity_id: str,
    opportunity_jurisdiction: str,
    opportunity_requires_federal_recognition: bool = False,
    opportunity_allows_state_recognized: bool = False,
    opportunity_allows_native_serving_nonprofit: bool = False,
    opportunity_allows_tcu: bool = False,
    federal_recognition_evidence_refs: list[str] | None = None,
    state_recognition_evidence_refs: list[str] | None = None,
    federal_recognition_source: str | None = None,
    state_recognition_source: str | None = None,
) -> dict[str, Any]:
    et = entity_type if entity_type in ENTITY_TYPES else "unknown_needs_verification"
    jur = (
        opportunity_jurisdiction
        if opportunity_jurisdiction in OPPORTUNITY_JURISDICTIONS
        else "unknown"
    )
    fed_refs = list(federal_recognition_evidence_refs or [])
    state_refs = list(state_recognition_evidence_refs or [])

    is_federal_tribe = et == "federally_recognized_tribe" and bool(fed_refs)
    is_state_tribe = et == "state_recognized_tribe" and bool(state_refs)

    # State-recognized must NEVER count as federally recognized
    treated_as_federally_recognized = bool(is_federal_tribe)
    if et == "state_recognized_tribe":
        treated_as_federally_recognized = False

    federal_route_ok = False
    state_route_ok = False
    blockers: list[str] = []

    if jur == "federal" or opportunity_requires_federal_recognition:
        if opportunity_requires_federal_recognition:
            if treated_as_federally_recognized:
                federal_route_ok = True
            elif et == "state_recognized_tribe":
                blockers.append("state_recognized_not_federal")
                federal_route_ok = False
            elif et == "native_serving_nonprofit" and opportunity_allows_native_serving_nonprofit:
                federal_route_ok = True
            elif et == "tribal_college_university" and opportunity_allows_tcu:
                federal_route_ok = True
            elif et in {
                "alaska_native_entity",
                "native_hawaiian_organization",
                "intertribal_consortium",
            }:
                # Route only when NOFO explicitly permits — without evidence mark needs review
                blockers.append(f"{et}_needs_nofo_permission_evidence")
                federal_route_ok = False
            else:
                blockers.append("federal_recognition_required_not_met")
        else:
            # Federal opportunity without exclusive federal-recognition gate
            federal_route_ok = et != "unknown_needs_verification"

    if jur == "state":
        if is_state_tribe and opportunity_allows_state_recognized:
            state_route_ok = True
        elif is_federal_tribe:
            # Federally recognized tribes may often apply to state programs — still needs program rules
            state_route_ok = False
            blockers.append("state_program_rules_need_verification")
        elif opportunity_allows_state_recognized and et in {
            "native_serving_nonprofit",
            "tribal_college_university",
            "intertribal_consortium",
            "fiscal_sponsor_partner_org",
        }:
            state_route_ok = False
            blockers.append("state_entity_eligibility_needs_verification")
        else:
            blockers.append("state_route_not_supported_or_unknown")

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "recognition_routing_id": make_recognition_routing_id(
                organization_profile_id, opportunity_id
            ),
            "organization_profile_id": organization_profile_id,
            "entity_type": et,
            "opportunity_id": opportunity_id,
            "opportunity_jurisdiction": jur,
            "opportunity_requires_federal_recognition": bool(
                opportunity_requires_federal_recognition
            ),
            "opportunity_allows_state_recognized": bool(
                opportunity_allows_state_recognized
            ),
            "opportunity_allows_native_serving_nonprofit": bool(
                opportunity_allows_native_serving_nonprofit
            ),
            "opportunity_allows_tcu": bool(opportunity_allows_tcu),
            "federal_recognition_evidence_refs": fed_refs,
            "state_recognition_evidence_refs": state_refs,
            "federal_recognition_source": federal_recognition_source
            or ("BIA/Federal_Register_placeholder" if fed_refs else None),
            "state_recognition_source": state_recognition_source,
            "treated_as_federally_recognized": treated_as_federally_recognized,
            "federal_route_ok": bool(federal_route_ok),
            "state_route_ok": bool(state_route_ok),
            "blockers": blockers,
            "human_review_required": True,
            "final_eligibility_claimed": False,
            "every_tribe_qualifies_claimed": False,
            "state_recognized_as_federal_claimed": False,
            "live_coverage_claimed": False,
        }
    )


def recognition_routing_invariant_failures(record: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    if record.get("entity_type") not in ENTITY_TYPES:
        fails.append("bad_entity_type")
    if record.get("final_eligibility_claimed") is True:
        fails.append("final_eligibility_claimed")
    if record.get("every_tribe_qualifies_claimed") is True:
        fails.append("every_tribe_qualifies_claimed")
    if record.get("state_recognized_as_federal_claimed") is True:
        fails.append("state_recognized_as_federal_claimed")
    if record.get("live_coverage_claimed") is True:
        fails.append("live_coverage_claimed")
    if record.get("entity_type") == "state_recognized_tribe":
        if record.get("treated_as_federally_recognized") is True:
            fails.append("state_treated_as_federal")
        if (
            record.get("opportunity_requires_federal_recognition") is True
            and record.get("federal_route_ok") is True
        ):
            fails.append("state_passed_federal_only_gate")
    return fails
