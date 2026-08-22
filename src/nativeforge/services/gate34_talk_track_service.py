"""Buyer talk-track honesty (Block 80)."""

from __future__ import annotations

import json
from typing import Any

SCHEMA_VERSION = "nf_gate34_talk_track_v1"

ALLOWED = (
    "Native-relevant opportunity intelligence",
    "Evidence-backed pursuit package",
    "Review eligibility",
    "Resolve authority gap",
    "Prepare human review",
    "Production claim blocked until owner inputs validate",
    "Internal/demo route is GO",
    "Controlled pilot is pending Auth0, storage, and pen-test",
)

FORBIDDEN = (
    "production-ready",
    "pilot-ready",
    "secure",
    "pen-test passed",
    "login live",
    "customer access live",
    "auto-submit",
    "guaranteed eligibility",
    "submission-ready",
    "final export ready",
    "all states live",
    "Top-15 live",
    "production storage live",
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def detect_risky_phrases(text: str, *, claims_true: bool = False) -> list[str]:
    found: list[str] = []
    lower = text.lower()
    for phrase in FORBIDDEN:
        if phrase.lower() in lower and not claims_true:
            found.append(phrase)
    return found


def resolve_talk_track(
    *,
    draft: str | None = None,
    customer_access_cta: bool = False,
    claims_validated: bool = False,
) -> dict[str, Any]:
    script = draft or " ".join(ALLOWED)
    risky = detect_risky_phrases(script, claims_true=claims_validated)
    cta_safe = not customer_access_cta
    blocked_language = bool(risky)
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "buyer_talk_track_contract": True,
            "allowed_language": list(ALLOWED),
            "forbidden_language": list(FORBIDDEN),
            "demo_script": script,
            "risky_phrases": risky,
            "forbidden_blocked": blocked_language,
            "cta_safety": "block_customer_access" if not cta_safe else "safe_demo_only",
            "cta_safe": cta_safe,
            "evidence_backed_narrative": (
                "Demo GO is evidence-backed; owner inputs remain unvalidated."
            ),
            "owner_action_exposed": (
                "Provide OIDC_*, storage approval/config, pen-test report"
            ),
            "objection_map": {
                "is_it_production_ready": "No. Production claim blocked until owner inputs validate.",
                "can_customers_log_in": "No. Login live remains false.",
            },
            "trust_boundary": "internal_demo_go_not_customer_pilot",
            "fake_claim_language_blocked": True,
        }
    )


def talk_track_invariant_failures(result: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    if not result.get("owner_action_exposed"):
        fails.append("owner_action_missing")
    if result.get("cta_safe") is False:
        fails.append("unsafe_cta")
    script = (result.get("demo_script") or "").lower()
    for phrase in FORBIDDEN:
        if phrase.lower() in script:
            fails.append(f"forbidden_in_script:{phrase}")
    return fails
