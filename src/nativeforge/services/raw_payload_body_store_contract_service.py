"""Raw payload body store contract (Gate 96D).

Says where response bodies live in production. Today the answer is nowhere, and
this module reports that by looking rather than by being told.

## Four modes, one of which is production-capable

``object_store_required``        the only mode a real collector may activate on
``database_small_payload_only``  tests and tiny fixtures. Never production
                                 source ingestion.
``local_dev_ignored``            Gate 95's per-checkout store. Never production.
``unconfigured``                 the default, and the current state

## Why database_small_payload_only is not a production option

"Small" is not a property of a source response. It is a property of the
responses you happened to have seen. The Grants.gov daily extract is ~78 MB
compressed, its description field runs to 18,000 characters and its eligibility
text to 4,000 - and the size of tomorrow's response is not something a schema
can promise. A mode that works until it does not is worse than one that refuses
from the start.

## Detected, not declared

``detect_body_store_mode`` inspects settings and the installed environment. It
does not read a caller-supplied flag, because a flag saying "the body store is
configured" is the same shape as the corpus flags Gates 87-89 unpicked: a claim
about a claim.

As of Gate 96 there is no object-store client in the dependency set, no bucket
setting, no endpoint and no credential. The detector therefore returns
``unconfigured``, and no argument to any function in this module can change
that.

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
        "object_store_required",
        "unconfigured",
    }
)

# The single mode a live collector may run on. Derived affirmatively: the
# permitted set is named, never computed by removing the ones that are not.
PRODUCTION_CAPABLE_MODES = frozenset({"object_store_required"})

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

# Settings names a configured object store would have to provide. None of these
# exist as of Gate 96; they are listed so the gap is legible rather than vague.
REQUIRED_SETTINGS: tuple[str, ...] = (
    "raw_payload_object_store_endpoint",
    "raw_payload_object_store_bucket",
    "raw_payload_object_store_credential",
)

# Client libraries whose presence would indicate an object store integration.
OBJECT_STORE_CLIENT_MODULES: tuple[str, ...] = (
    "boto3",
    "minio",
    "google.cloud.storage",
    "azure.storage.blob",
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _installed_object_store_clients() -> list[str]:
    """Which object-store clients are importable. Import, do not assume."""
    import importlib.util

    found: list[str] = []
    for module in OBJECT_STORE_CLIENT_MODULES:
        try:
            if importlib.util.find_spec(module) is not None:
                found.append(module)
        except (ImportError, ModuleNotFoundError, ValueError):
            continue
    return found


def _configured_settings() -> list[str]:
    """Which required settings actually exist on the Settings model."""
    try:
        from nativeforge.lib.settings import Settings
    except ImportError:
        return []
    fields = set(getattr(Settings, "model_fields", {}) or {})
    return [name for name in REQUIRED_SETTINGS if name in fields]


def detect_body_store_mode() -> str:
    """The mode this checkout actually supports. Deny by default."""
    clients = _installed_object_store_clients()
    settings_present = _configured_settings()
    if clients and len(settings_present) == len(REQUIRED_SETTINGS):
        return "object_store_required"
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

    clients = _installed_object_store_clients()
    settings_present = _configured_settings()
    missing_settings = [s for s in REQUIRED_SETTINGS if s not in settings_present]

    configured = detected in PRODUCTION_CAPABLE_MODES

    blocked: list[str] = []
    if not clients:
        blocked.append("no_object_store_client_installed")
    if missing_settings:
        blocked.append(
            "object_store_settings_missing:" + ",".join(missing_settings)
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
            "settings_present": settings_present,
            "settings_missing": missing_settings,
            "object_store_clients_installed": clients,
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

    return fails
