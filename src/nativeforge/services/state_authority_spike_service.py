"""State authority verification spike profiles for Top-15 (Block 33)."""

from __future__ import annotations

import json
from typing import Any

SCHEMA_VERSION = "nf_state_authority_spike_v1"

TOP15 = (
    "SC",
    "OK",
    "AZ",
    "NM",
    "AK",
    "CA",
    "WA",
    "OR",
    "MT",
    "SD",
    "ND",
    "MN",
    "WI",
    "NC",
    "HI",
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def build_state_authority_profile(state_code: str) -> dict[str, Any]:
    code = state_code.upper()
    sc_notes = (
        "SC demo lane: portals vary by program; no live portal role verification"
        if code == "SC"
        else f"{code}: portal path needs research; no live credentials configured"
    )
    return _json_safe(
        {
            "state_code": code,
            "state_grant_portal_authority_path": "needs_research"
            if code != "SC"
            else "partially_known_program_specific",
            "vendor_registration_path": "needs_research",
            "authorized_signer_path": "manual_evidence_required",
            "tribal_resolution_delegation_path": "manual_evidence_required",
            "state_specific_unknowns": [
                "portal URL inventory incomplete",
                "role labels vary by agency",
                "no live check configured",
            ],
            "live_check_availability": "not_configured",
            "credentials_required": True,
            "human_review_required": True,
            "authority_can_be_claimed": False,
            "state_authority_live_checked": False,
            "state_authority_verified_claimed": False,
            "notes": sc_notes,
        }
    )


def build_all_top15_state_authority_profiles() -> list[dict[str, Any]]:
    return [build_state_authority_profile(c) for c in TOP15]


def run_state_authority_spike(
    *,
    state_code: str,
    evidence_present: dict[str, bool] | None = None,
) -> dict[str, Any]:
    profile = build_state_authority_profile(state_code)
    present = dict(evidence_present or {})
    required = [
        "state_portal_or_vendor_account_evidence",
        "authorized_signer_evidence",
        "tribal_resolution_or_delegation_evidence",
    ]
    missing = [k for k in required if not present.get(k)]
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "profile": profile,
            "missing_evidence": missing,
            "state_authority_live_checked": False,
            "state_authority_verified_claimed": False,
            "human_review_required": True,
        }
    )


def state_authority_spike_invariant_failures(report: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    if report.get("state_authority_verified_claimed") is True:
        fails.append("state_authority_verified_claimed")
    if report.get("state_authority_live_checked") is True:
        fails.append("state_authority_live_checked_unexpected")
    profile = report.get("profile") or report
    if isinstance(profile, dict) and profile.get("authority_can_be_claimed") is True:
        fails.append("authority_can_be_claimed")
    return fails
