"""OIDC Mode B readiness (Gate 59).

Reports whether real OIDC token verification is even *possible* yet. It never
reads a secret value, never performs network I/O, and never claims login is live.

Env var naming: the repo already standardised on ``OIDC_*`` (19 references
across ``src/`` and ``scripts/``, consumed by ``auth0_preflight_service`` and
``oidc_config_schema_service``). The Gate 59 brief named
``NATIVEFORGE_OIDC_*``. Rather than fork the convention or ignore the brief,
both spellings are accepted, with ``OIDC_*`` canonical. See doc 374.

Composes with the existing ``auth0_preflight_service`` /
``oidc_config_schema_service`` / ``login_live_promotion_gate_service`` rather
than restating their rules.
"""

from __future__ import annotations

import json
import os
from typing import Any

SCHEMA_VERSION = "nf_oidc_readiness_v1"

# Canonical name first, brief alias second.
ENV_KEYS: dict[str, tuple[str, ...]] = {
    "issuer": ("OIDC_ISSUER", "NATIVEFORGE_OIDC_ISSUER"),
    "audience": ("OIDC_AUDIENCE", "NATIVEFORGE_OIDC_AUDIENCE"),
    "jwks_url": ("OIDC_JWKS_URL", "NATIVEFORGE_OIDC_JWKS_URL"),
    "client_id": ("OIDC_CLIENT_ID", "NATIVEFORGE_OIDC_CLIENT_ID"),
    "client_secret": ("OIDC_CLIENT_SECRET", "NATIVEFORGE_OIDC_CLIENT_SECRET"),
}

# Flip to True only when a real token verification path exists AND passes.
# Strict readiness cannot succeed while this is False, because "ready for
# live login" must mean a token can actually be verified — not merely that
# config strings are present.
TOKEN_VERIFICATION_IMPLEMENTED = False

# Minimum set required before any token verification could be attempted.
REQUIRED_FOR_VERIFICATION = ("issuer", "audience", "jwks_url", "client_id")

READINESS_STATES = frozenset(
    {
        "oidc_unconfigured",
        "oidc_partially_configured",
        "oidc_configured_unverified",
        "oidc_verified",
        "unknown",
    }
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _present(logical: str) -> tuple[bool, str | None]:
    """Return presence only. The value is never returned or logged."""
    for key in ENV_KEYS[logical]:
        raw = os.environ.get(key)
        if raw is not None and str(raw).strip():
            return True, key
    return False, None


def build_oidc_readiness(*, strict: bool = False) -> dict[str, Any]:
    """Report OIDC configuration presence and what it does or does not unlock.

    ``strict=False`` (default / demo): missing config is a *state*, not a
    failure — the demo runs without OIDC and must keep running.
    ``strict=True`` (live-readiness): missing config fails closed.
    """
    presence: dict[str, bool] = {}
    source_keys: dict[str, str | None] = {}
    for logical in ENV_KEYS:
        ok, key = _present(logical)
        presence[logical] = ok
        source_keys[logical] = key

    required_present = [k for k in REQUIRED_FOR_VERIFICATION if presence[k]]
    required_missing = [k for k in REQUIRED_FOR_VERIFICATION if not presence[k]]

    if not required_present:
        state = "oidc_unconfigured"
    elif required_missing:
        state = "oidc_partially_configured"
    else:
        # Config complete, but nothing has verified a token. Verification
        # requires a real verifier; presence of config is not verification.
        state = "oidc_configured_unverified"

    config_complete = not required_missing
    # Config presence is necessary but NOT sufficient.
    verification_possible = config_complete and TOKEN_VERIFICATION_IMPLEMENTED
    blocked_reasons: list[str] = []
    if required_missing:
        blocked_reasons.append(
            "missing_required_config:" + ",".join(sorted(required_missing))
        )
    if not TOKEN_VERIFICATION_IMPLEMENTED:
        blocked_reasons.append("token_verification_path_not_implemented")

    result = {
        "schema_version": SCHEMA_VERSION,
        "mode": "strict" if strict else "default",
        "readiness_state": state,
        # Presence booleans only — no values, ever.
        "config_present": presence,
        "config_source_keys": source_keys,
        "required_for_verification": list(REQUIRED_FOR_VERIFICATION),
        "required_missing": required_missing,
        "config_complete": config_complete,
        "token_verification_implemented": TOKEN_VERIFICATION_IMPLEMENTED,
        "verification_possible": verification_possible,
        "blocked_reasons": blocked_reasons,
        "network_access_attempted": False,
        "jwks_fetched": False,
        # Honest boundaries.
        "login_live_claimed": False,
        "customer_login_live_claimed": False,
        "mode_b_executed": False,
        "secret_values_read": False,
    }

    # Strict mode fails closed unless verification is genuinely possible.
    result["ok"] = bool(verification_possible) if strict else True
    result["strict_failure"] = bool(strict and not verification_possible)
    return _json_safe(result)


def oidc_readiness_invariant_failures(readiness: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    if readiness.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")
    if readiness.get("readiness_state") not in READINESS_STATES:
        fails.append("readiness_state_invalid")

    # login_live can never be claimed from configuration presence alone.
    for forbidden in (
        "login_live_claimed",
        "customer_login_live_claimed",
        "mode_b_executed",
        "secret_values_read",
        "network_access_attempted",
        "jwks_fetched",
    ):
        if readiness.get(forbidden) is not False:
            fails.append(f"forbidden_claim:{forbidden}")

    # Never report verified: no verifier exists.
    if readiness.get("readiness_state") == "oidc_verified":
        fails.append("verified_state_without_verifier")

    # config_present must be booleans, never values.
    for k, v in (readiness.get("config_present") or {}).items():
        if not isinstance(v, bool):
            fails.append(f"config_present_not_boolean:{k}")

    if readiness.get("mode") == "strict":
        if readiness.get("ok") and readiness.get("required_missing"):
            fails.append("strict_ok_with_missing_config")
        if readiness.get("ok") and not readiness.get(
            "token_verification_implemented"
        ):
            fails.append("strict_ok_without_verifier")

    return fails
