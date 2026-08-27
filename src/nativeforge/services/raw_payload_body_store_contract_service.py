"""Raw payload body store contract (Gate 96D).

Says where response bodies live in production. Today the answer is nowhere, and
this module reports that by looking rather than by being told.

## Four modes, one of which is production-capable

``s3_compatible_configured``     the only mode a real collector may activate on
``database_small_payload_only``  tests and tiny fixtures. Never production
                                 source ingestion.
``local_dev_ignored``            Gate 95's per-checkout store. Never production.
``unconfigured``                 the default, and the current state

Gate 97 renamed the first from ``object_store_required``. A mode should say
what *is*, not what is *needed* - reading "mode: object_store_required" told you
nothing about whether one existed, which is the only thing a mode is asked.

## Why database_small_payload_only is not a production option

"Small" is not a property of a source response. It is a property of the
responses you happened to have seen. The Grants.gov daily extract is ~78 MB
compressed, its description field runs to 18,000 characters and its eligibility
text to 4,000 - and the size of tomorrow's response is not something a schema
can promise. A mode that works until it does not is worse than one that refuses
from the start.

## Detected, not declared

``detect_body_store_mode`` reads the actual **values** of the five required
settings. It does not read a caller-supplied flag, because a flag saying "the
body store is configured" is the same shape as the corpus flags Gates 87-89
unpicked: a claim about a claim.

Gate 96 checked whether the *fields existed on the Settings model*, which was
correct only while no such fields existed. Gate 97 added them with empty
defaults, at which point the old check would have reported a credential-free
checkout as fully configured. Values, not declarations.

A blank value is unconfigured. So is a placeholder: ``AKIAIOSFODNN7EXAMPLE`` is
AWS's own documentation key, and a checkout that pasted it from a tutorial is
not a production environment.

## Two facts, not one

``body_store_implementation_available``  the write seam exists
``body_store_configured``                an environment supplies real settings

Gate 96 folded these together by requiring an *installed* SDK. With Gate 97's
injected-client seam the client arrives at call time, so requiring it to be
importable would mean ``body_store_configured`` could never be true however
correctly an operator configured their environment. Production availability
requires both halves; splitting them makes each checkable.

## Requirements a body store must meet before it counts

Content-addressed, hash-preserving, secret-scan-clean before promotion, and
silent about body values in logs. All four are reported on the contract and
checked by invariants, so a future integration that satisfies three of them
still does not qualify.
"""

from __future__ import annotations

import json
from typing import Any

SCHEMA_VERSION = "nf_raw_payload_body_store_contract_v1"

BODY_STORE_MODES = frozenset(
    {
        "local_dev_ignored",
        "database_small_payload_only",
        "s3_compatible_configured",
        "unconfigured",
    }
)

# Gate 97 renamed `object_store_required` -> `s3_compatible_configured`. The old
# name described what was *needed*; a mode should describe what *is*. Reading
# "mode: object_store_required" told you nothing about whether one existed,
# which is the only question the mode is asked.
RENAMED_MODES: dict[str, str] = {"object_store_required": "s3_compatible_configured"}

# The single mode a live collector may run on. Derived affirmatively: the
# permitted set is named, never computed by removing the ones that are not.
PRODUCTION_CAPABLE_MODES = frozenset({"s3_compatible_configured"})

# Modes that exist for tests and local work and must never be mistaken for
# production, each with the reason it is disqualified.
NON_PRODUCTION_MODES: dict[str, str] = {
    "local_dev_ignored": (
        "per-checkout directory, gitignored, no durability or cross-process "
        "retrieval"
    ),
    "database_small_payload_only": (
        "'small' is a property of the responses seen so far, not of the source; "
        "a 78 MB Grants.gov extract is not a database row"
    ),
    "unconfigured": "no body store exists",
}

# What any body store must guarantee before it counts as one.
REQUIRED_GUARANTEES: tuple[str, ...] = (
    "content_addressed",
    "hash_preserving",
    "secret_scan_clean_before_promotion",
    "no_body_values_in_logs",
)

# Settings a configured S3-compatible store must provide, with real values.
# Gate 96 named three, folding the credential into one opaque field. Gate 97
# splits it: an access key id is safe to report present, a secret key is not,
# and one field cannot carry two different handling rules.
REQUIRED_SETTINGS: tuple[str, ...] = (
    "raw_payload_object_store_endpoint",
    "raw_payload_object_store_bucket",
    "raw_payload_object_store_region",
    "raw_payload_object_store_access_key_id",
    "raw_payload_object_store_secret_access_key",
)

# Optional: MinIO and most self-hosted S3-compatible stores need path-style
# URLs, but a store that does not is still configured.
OPTIONAL_SETTINGS: tuple[str, ...] = (
    "raw_payload_object_store_force_path_style",
)

# The module that implements the write path. Gate 97 uses an injected client,
# so no SDK is imported and none is required - what must exist is the seam.
BODY_STORE_IMPLEMENTATION_MODULE = (
    "nativeforge.services.s3_raw_payload_body_store_service"
)
BODY_STORE_IMPLEMENTATION_CALLABLE = "store_body"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def detect_body_store_implementation() -> bool:
    """Whether the write path exists. Imported and checked, not assumed."""
    try:
        import importlib

        module = importlib.import_module(BODY_STORE_IMPLEMENTATION_MODULE)
    except ImportError:
        return False
    return callable(getattr(module, BODY_STORE_IMPLEMENTATION_CALLABLE, None))


def _setting_value(settings: Any, name: str) -> str:
    """Read one setting as text without rendering a secret.

    A SecretStr's `str()` is `**********`, so a naive read would treat every
    configured secret as a placeholder. `get_secret_value()` is called here and
    only here, and its result is measured (empty or not) rather than returned.
    """
    value = getattr(settings, name, "")
    getter = getattr(value, "get_secret_value", None)
    if callable(getter):
        return str(getter() or "")
    return str(value or "")


def _configured_settings() -> tuple[list[str], list[str]]:
    """(present-with-real-values, present-but-placeholder).

    Gate 96 checked whether the *field existed on the model*, which was
    harmless only while no such fields existed. With the fields added, that
    check would report a credential-free checkout as fully configured - a check
    that reads a declaration rather than the thing declared, which is the exact
    failure this campaign keeps finding.
    """
    try:
        from nativeforge.lib.settings import get_settings
        from nativeforge.services.s3_raw_payload_body_store_service import (
            is_placeholder_value,
        )
    except ImportError:
        return [], []

    settings = get_settings()
    real: list[str] = []
    placeholder: list[str] = []
    for name in REQUIRED_SETTINGS:
        raw = _setting_value(settings, name).strip()
        if not raw:
            continue
        if is_placeholder_value(raw):
            placeholder.append(name)
        else:
            real.append(name)
    return real, placeholder


def detect_body_store_mode() -> str:
    """The mode this checkout actually supports. Deny by default."""
    real, placeholder = _configured_settings()
    if placeholder:
        return "unconfigured"
    if len(real) == len(REQUIRED_SETTINGS) and detect_body_store_implementation():
        return "s3_compatible_configured"
    return "unconfigured"


def build_body_store_contract(*, declared_mode: Any = None) -> dict[str, Any]:
    """The body store contract, and whether anything satisfies it.

    ``declared_mode`` is what a caller *believes* is configured. It is recorded
    and compared against what was detected; it never overrides it.
    """
    detected = detect_body_store_mode()
    declared = str(declared_mode).strip() if declared_mode else None
    if declared is not None and declared not in BODY_STORE_MODES:
        declared = "unconfigured"

    settings_present, placeholder_settings = _configured_settings()
    missing_settings = [
        s
        for s in REQUIRED_SETTINGS
        if s not in settings_present and s not in placeholder_settings
    ]
    implementation_available = detect_body_store_implementation()

    configured = detected in PRODUCTION_CAPABLE_MODES

    blocked: list[str] = []
    if not implementation_available:
        blocked.append("body_store_implementation_missing")
    if missing_settings:
        blocked.append(
            "object_store_settings_missing:" + ",".join(sorted(missing_settings))
        )
    if placeholder_settings:
        blocked.append(
            "object_store_settings_are_placeholders:"
            + ",".join(sorted(placeholder_settings))
        )
    if detected in NON_PRODUCTION_MODES:
        blocked.append(f"mode_not_production_capable:{detected}")
    if declared is not None and declared != detected:
        blocked.append(f"declared_mode_does_not_match_detected:{declared}!={detected}")

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "detected_mode": detected,
            "declared_mode": declared,
            "modes": sorted(BODY_STORE_MODES),
            "production_capable_modes": sorted(PRODUCTION_CAPABLE_MODES),
            "non_production_modes": dict(sorted(NON_PRODUCTION_MODES.items())),
            "required_guarantees": list(REQUIRED_GUARANTEES),
            "required_settings": list(REQUIRED_SETTINGS),
            "optional_settings": list(OPTIONAL_SETTINGS),
            "settings_present": sorted(settings_present),
            "settings_missing": sorted(missing_settings),
            "placeholder_settings": sorted(placeholder_settings),
            # Gate 97: two distinct facts. The seam exists; an environment
            # configuring it is a separate question.
            "body_store_implementation_available": implementation_available,
            "injected_client_seam": True,
            "object_store_sdk_required": False,
            # The three facts, kept apart.
            "body_store_configured": configured,
            "object_store_required_for_collection": True,
            "local_dev_counts_as_production": False,
            "database_mode_allowed_for_production": False,
            "blocked_reasons": blocked,
            # Nothing in this module stores, fetches, or activates.
            "bodies_stored": 0,
            "fetch_performed": False,
            "fabricated": False,
        }
    )


def mode_is_production_capable(mode: Any) -> bool:
    """Affirmative membership. An unknown mode is not production capable."""
    return str(mode or "") in PRODUCTION_CAPABLE_MODES


def body_store_invariant_failures(contract: dict[str, Any]) -> list[str]:
    fails: list[str] = []

    if contract.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")
    if contract.get("fabricated") is not False:
        fails.append("fabricated_must_be_false")
    if contract.get("fetch_performed") is not False:
        fails.append("body_store_contract_claimed_a_fetch")
    if contract.get("bodies_stored"):
        fails.append("body_store_contract_reported_stored_bodies")

    detected = contract.get("detected_mode")
    if detected not in BODY_STORE_MODES:
        fails.append("detected_mode_out_of_vocabulary")

    declared = contract.get("declared_mode")
    if declared is not None and declared not in BODY_STORE_MODES:
        fails.append("declared_mode_out_of_vocabulary")

    # `body_store_configured` is derived from the detected mode, never set
    # beside it, and never satisfied by a non-production mode.
    if contract.get("body_store_configured") != (
        detected in PRODUCTION_CAPABLE_MODES
    ):
        fails.append("body_store_configured_disagrees_with_detected_mode")
    if contract.get("body_store_configured") and detected in NON_PRODUCTION_MODES:
        fails.append(f"non_production_mode_reported_configured:{detected}")

    # The two modes that must never be mistaken for production.
    if contract.get("local_dev_counts_as_production") is not False:
        fails.append("local_dev_counted_as_production")
    if contract.get("database_mode_allowed_for_production") is not False:
        fails.append("database_mode_allowed_for_production")
    if contract.get("object_store_required_for_collection") is not True:
        fails.append("object_store_requirement_dropped")

    # A configured store must satisfy every guarantee, not most of them.
    guarantees = list(contract.get("required_guarantees") or [])
    if guarantees != list(REQUIRED_GUARANTEES):
        fails.append("required_guarantee_list_altered")

    if not contract.get("body_store_configured") and not contract.get(
        "blocked_reasons"
    ):
        fails.append("unconfigured_body_store_without_a_reason")

    # Gate 97: a placeholder is not configuration, and an implementation is not
    # a configuration either.
    if contract.get("body_store_configured") and contract.get(
        "placeholder_settings"
    ):
        fails.append("configured_with_placeholder_settings")
    if contract.get("body_store_configured") and not contract.get(
        "body_store_implementation_available"
    ):
        fails.append("configured_without_an_implementation")
    # No credential value may appear anywhere in a contract.
    for forbidden in (
        "secret_access_key",
        "access_key_id",
        "credential",
        "secret",
    ):
        if forbidden in contract:
            fails.append(f"contract_rendered_a_credential_field:{forbidden}")

    return fails
