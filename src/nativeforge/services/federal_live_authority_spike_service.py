"""Federal live/read-only authority verification spike (Block 33).

No credentials configured → dry-run only; all verified claims stay false.
"""

from __future__ import annotations

import json
import os
from typing import Any

SCHEMA_VERSION = "nf_federal_live_authority_spike_v1"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _credentials_present() -> bool:
    # Explicitly do NOT treat random env as secrets to use — only check known keys exist
    keys = (
        "SAM_API_KEY",
        "SAM_GOV_API_KEY",
        "GRANTS_GOV_API_KEY",
        "NF_SAM_READ_ONLY_TOKEN",
    )
    return any(os.environ.get(k) for k in keys)


def run_federal_live_authority_spike(
    *,
    evidence_present: dict[str, bool] | None = None,
    self_attested_only: bool = False,
    attempt_live: bool = True,
) -> dict[str, Any]:
    present = dict(evidence_present or {})
    creds = _credentials_present()
    live_available = False  # no safe configured integration in repo
    # Even if creds appear, Gate 14 does not implement network calls without approved client
    integration_requirements = [
        "Approved read-only SAM.gov entity lookup client",
        "Approved Grants.gov role/workspace read path if any",
        "Secret storage for API tokens (not in git)",
        "No-mutation guarantee + rate limits + audit logging",
        "Owner approval before any live network verification",
    ]

    sam_uei_live_checked = False
    ebiz_live_checked = False
    aor_live_checked = False

    # Never claim verified from self-attestation or missing live check
    sam_uei_verified_claimed = False
    ebiz_poc_verified_claimed = False
    aor_verified_claimed = False
    federal_submission_authority_claimed = False

    missing = [
        k
        for k in (
            "uei_sam_registration_evidence",
            "ebiz_poc_evidence",
            "aor_or_expanded_aor_or_delegated_role_evidence",
            "tribal_authorization_or_delegation_evidence",
        )
        if not present.get(k)
    ]

    if self_attested_only:
        next_action = "Reject self-attestation as verification; require evidence packet"
    elif not creds or not live_available:
        next_action = (
            "Keep dry-run; collect manual evidence; configure approved read-only APIs "
            "before any live_verified claim"
        )
    else:
        next_action = "Live path not implemented in Gate 14 — do not claim verified"

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "mode": "no_credential_dry_run",
            "live_check_available": live_available,
            "credentials_detected_in_env": bool(creds),
            "network_call_attempted": False,
            "sam_uei_live_checked": sam_uei_live_checked,
            "sam_uei_verified_claimed": sam_uei_verified_claimed,
            "ebiz_poc_live_checked": ebiz_live_checked,
            "ebiz_poc_verified_claimed": ebiz_poc_verified_claimed,
            "aor_live_checked": aor_live_checked,
            "aor_verified_claimed": aor_verified_claimed,
            "federal_submission_authority_claimed": federal_submission_authority_claimed,
            "self_attested_only": bool(self_attested_only),
            "missing_evidence": missing,
            "integration_requirements": integration_requirements,
            "next_verification_action": next_action,
            "human_review_required": True,
            "attempt_live_requested": bool(attempt_live),
        }
    )


def federal_live_authority_spike_invariant_failures(
    report: dict[str, Any],
) -> list[str]:
    fails: list[str] = []
    for key in (
        "sam_uei_verified_claimed",
        "ebiz_poc_verified_claimed",
        "aor_verified_claimed",
        "federal_submission_authority_claimed",
    ):
        if report.get(key) is True:
            fails.append(key)
    if report.get("network_call_attempted") is True and not report.get(
        "live_check_available"
    ):
        fails.append("network_without_availability")
    if report.get("self_attested_only") and report.get("sam_uei_verified_claimed"):
        fails.append("self_attestation_verified")
    return fails
