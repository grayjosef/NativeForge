"""Block 33 assembler: live authority verification spike surface."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.authority_claim_resolver_service import (
    authority_claim_resolver_invariant_failures,
    resolve_authority_claims,
)
from nativeforge.services.authority_source_registry_service import (
    authority_source_registry_invariant_failures,
    build_authority_source_registry,
)
from nativeforge.services.state_authority_spike_service import (
    build_all_top15_state_authority_profiles,
)

SCHEMA_VERSION = "nf_live_authority_spike_assembler_v1"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def build_live_authority_spike_demo_surface() -> dict[str, Any]:
    registry = build_authority_source_registry()
    profiles = build_all_top15_state_authority_profiles()
    resolved = resolve_authority_claims(
        jurisdiction="federal",
        evidence_present={},
        human_review_complete=False,
        self_attested_only=False,
    )
    self_attest = resolve_authority_claims(
        evidence_present={"aor_or_expanded_aor_or_delegated_role_evidence": True},
        self_attested_only=True,
    )
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "campaign_block": 33,
            "title": "Live authority verification spike",
            "authority_source_registry": registry,
            "state_authority_profiles": profiles,
            "states_covered": [p["state_code"] for p in profiles],
            "authority_claim_resolver": resolved,
            "self_attestation_example": self_attest,
            "buyer_summary": [
                "Authority source registry maps SAM/UEI, EBiz POC, AOR, tribal, and state paths",
                "No live verification credentials configured — dry-run only",
                "Self-attestation cannot unlock submit authority",
                "All Top-15 states have authority profiles; none live-verified",
            ],
            "sam_uei_live_checked": False,
            "sam_uei_verified_claimed": False,
            "ebiz_poc_live_checked": False,
            "ebiz_poc_verified_claimed": False,
            "aor_live_checked": False,
            "aor_verified_claimed": False,
            "state_authority_live_checked": False,
            "state_authority_verified_claimed": False,
            "submit_authority": False,
            "draft_authority": False,
            "manage_workspace_authority": False,
            "login_live_claimed": False,
            "human_review_required": True,
        }
    )


def live_authority_spike_demo_surface_invariant_failures(
    surface: dict[str, Any],
) -> list[str]:
    fails: list[str] = []
    for key in (
        "sam_uei_verified_claimed",
        "ebiz_poc_verified_claimed",
        "aor_verified_claimed",
        "state_authority_verified_claimed",
        "submit_authority",
        "login_live_claimed",
    ):
        if surface.get(key) is True:
            fails.append(key)
    fails.extend(
        authority_source_registry_invariant_failures(
            surface.get("authority_source_registry") or {}
        )
    )
    fails.extend(
        authority_claim_resolver_invariant_failures(
            surface.get("authority_claim_resolver") or {}
        )
    )
    if len(surface.get("states_covered") or []) != 15:
        fails.append("states_not_15")
    return fails
