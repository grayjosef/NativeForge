"""Gate 141B: is object storage configured? Presence only, never a value.

## What this reports and what it refuses to report

```text
reports    which required key NAMES are present, absent or placeholder
           a state, one of five
           booleans and counts
never      an endpoint, a bucket, a region, an access key id, a secret,
           a prefix of any of them, or a length that would narrow one
```

The key **names** are safe and are the point — a reader needs to know which
setting to fill in. The values are not, and there is no branch in this module
that puts one into a returned dict, a message, or an exception.

## Five states, because "configured" hides four different situations

```text
no_config                 nothing is set. The honest default.
partial_config            some set, some not. The dangerous one: it looks
                          configured to a reader and cannot store anything.
configured_but_unverified all five set, nothing has proved they work.
hermetic_fake_verified    an in-memory adapter passed. Proves the CODE, and
                          nothing about any bucket anywhere.
production_verified       an external check was explicitly allowed AND passed.
                          This module never produces it on its own.
```

`object_store_configured` is true only for `production_verified`.
`hermetic_fake_verified` is deliberately NOT enough: a fake proves the adapter's
refusals and its round trip, and a fake that could flip a production flag would
make every "not configured" above it unfalsifiable.

## No network, ever

Nothing here opens a socket, and there is no SDK in this project to open one
with. `detect_body_store_mode()` already answers "is a store configured" by
reading settings, and this module asks it rather than answering again — a second
answer to one question is the shape Gate 114 spent a gate collapsing.
"""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.raw_payload_body_store_contract_service import (
    REQUIRED_SETTINGS,
    detect_body_store_implementation,
    detect_body_store_mode,
)
from nativeforge.services.s3_raw_payload_body_store_service import (
    is_placeholder_value,
)

SCHEMA_VERSION = "nf_object_storage_configuration_preflight_v1"

#: The five settings a configured S3-compatible store must provide. Reused from
#: Gate 97 rather than restated: a second list would drift from the detector.
REQUIRED_KEY_NAMES: tuple[str, ...] = tuple(REQUIRED_SETTINGS)

#: Settings whose presence may be reported but whose value must never be, not
#: even truncated. Named so a reader can see the distinction is deliberate.
SECRET_KEY_NAMES: frozenset[str] = frozenset(
    {
        "raw_payload_object_store_secret_access_key",
        "raw_payload_object_store_access_key_id",
    }
)

NO_CONFIG = "no_config"
PARTIAL_CONFIG = "partial_config"
CONFIGURED_BUT_UNVERIFIED = "configured_but_unverified"
HERMETIC_FAKE_VERIFIED = "hermetic_fake_verified"
PRODUCTION_VERIFIED = "production_verified"

PREFLIGHT_STATES: tuple[str, ...] = (
    NO_CONFIG,
    PARTIAL_CONFIG,
    CONFIGURED_BUT_UNVERIFIED,
    HERMETIC_FAKE_VERIFIED,
    PRODUCTION_VERIFIED,
)

#: The only state that means a real store exists and was proved to.
CONFIGURED_STATES: frozenset[str] = frozenset({PRODUCTION_VERIFIED})

#: What `production_verified` costs. Both, together, from a caller that
#: measured them - never inferred from the settings being present.
PRODUCTION_EVIDENCE_FIELDS: tuple[str, ...] = (
    "external_verification_allowed",
    "external_verification_passed",
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _settings():
    from nativeforge.lib.settings import get_settings

    return get_settings()


def _raw(settings: Any, name: str) -> str:
    """One setting as text, for presence testing only.

    The return value is consumed by `bool()` and `is_placeholder_value()` in
    this module and reaches no caller. A `SecretStr` is unwrapped here because
    a pydantic secret's `str()` is the literal `'**********'`, which would read
    as a present value for every unset secret in the project.
    """
    value = getattr(settings, name, None)
    if hasattr(value, "get_secret_value"):
        value = value.get_secret_value()
    return str(value or "").strip()


def inspect_required_keys(*, settings: Any = None) -> dict[str, Any]:
    """Which required key names are present, placeholder, or absent.

    Names only. The value of every one of them is tested and discarded inside
    this function.
    """
    resolved = settings if settings is not None else _settings()

    present: list[str] = []
    placeholder: list[str] = []
    absent: list[str] = []
    for name in REQUIRED_KEY_NAMES:
        raw = _raw(resolved, name)
        if not raw:
            absent.append(name)
        elif is_placeholder_value(raw):
            placeholder.append(name)
        else:
            present.append(name)

    return _json_safe(
        {
            "required_key_names": list(REQUIRED_KEY_NAMES),
            "present_key_names": sorted(present),
            "placeholder_key_names": sorted(placeholder),
            "absent_key_names": sorted(absent),
            "present_count": len(present),
            "required_count": len(REQUIRED_KEY_NAMES),
            "secret_key_names": sorted(SECRET_KEY_NAMES),
            # Stated, so a reader does not have to infer it from the absence of
            # a field that would have carried one.
            "values_read": False,
            "values_reported": False,
            "value_lengths_reported": False,
        }
    )


def build_object_storage_preflight(
    *,
    settings: Any = None,
    hermetic_fake_passed: bool = False,
    external_verification_allowed: bool = False,
    external_verification_passed: bool = False,
) -> dict[str, Any]:
    """The preflight. Contacts nothing; reads settings and reports names.

    `external_verification_*` are supplied by a caller that actually did the
    check. Neither is inferred from configuration being present, because
    "five settings are filled in" and "those five settings reach a bucket that
    accepts writes" are different claims and the second is the one that matters.
    """
    keys = inspect_required_keys(settings=settings)
    implementation = detect_body_store_implementation()
    mode = detect_body_store_mode()

    blocked: list[str] = []

    if keys["absent_key_names"]:
        blocked.append(
            "object_store_settings_absent:" + ",".join(keys["absent_key_names"])
        )
    if keys["placeholder_key_names"]:
        blocked.append(
            "object_store_settings_are_placeholders:"
            + ",".join(keys["placeholder_key_names"])
        )
    if not implementation:
        blocked.append("body_store_implementation_missing")

    fully_configured = (
        keys["present_count"] == keys["required_count"] and implementation
    )

    # -- the state, derived in one place ------------------------------------
    allowed = bool(external_verification_allowed)
    passed = bool(external_verification_passed)

    if passed and not allowed:
        # A result nobody authorized asking for. Refused rather than believed.
        blocked.append("external_verification_passed_without_being_allowed")
        passed = False

    if fully_configured and allowed and passed:
        state = PRODUCTION_VERIFIED
    elif fully_configured:
        state = CONFIGURED_BUT_UNVERIFIED
    elif hermetic_fake_passed and keys["present_count"] == 0:
        # A fake proves the adapter, on a checkout with nothing configured.
        # It is a state of the CODE, never of a bucket.
        state = HERMETIC_FAKE_VERIFIED
    elif keys["present_count"] or keys["placeholder_key_names"]:
        state = PARTIAL_CONFIG
    else:
        state = NO_CONFIG

    if allowed and not passed and fully_configured:
        blocked.append("external_verification_allowed_but_did_not_pass")

    configured = state in CONFIGURED_STATES

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "state": state,
            "states": list(PREFLIGHT_STATES),
            "object_store_configured": configured,
            "fully_configured": fully_configured,
            "implementation_available": implementation,
            "detected_body_store_mode": mode,
            **keys,
            "hermetic_fake_passed": bool(hermetic_fake_passed),
            "external_verification_allowed": allowed,
            "external_verification_passed": passed,
            "production_evidence_fields": list(PRODUCTION_EVIDENCE_FIELDS),
            # Constants. Nothing in this module can set any of them.
            "external_object_store_contacted": False,
            "network_calls": 0,
            "credential_values_read_into_a_result": False,
            "credential_values_printed": False,
            "body_bytes_written": 0,
            "production_storage": False,
            "blocked_reasons": sorted(set(blocked)),
        }
    )


def preflight_invariant_failures(result: dict[str, Any]) -> list[str]:
    """What must never be true of a preflight result."""
    fails: list[str] = []

    state = result.get("state")
    if state not in PREFLIGHT_STATES:
        fails.append(f"state_not_recognised:{state}")

    if result.get("object_store_configured") and state != PRODUCTION_VERIFIED:
        fails.append(f"configured_in_state:{state}")

    # The load-bearing one. A fake adapter proves the code and nothing about a
    # bucket; letting it configure a store would make every refusal above it
    # unfalsifiable.
    if state == HERMETIC_FAKE_VERIFIED and result.get("object_store_configured"):
        fails.append("a_fake_adapter_configured_the_object_store")

    if state == PRODUCTION_VERIFIED:
        for field in PRODUCTION_EVIDENCE_FIELDS:
            if not result.get(field):
                fails.append(f"production_verified_without:{field}")
        if not result.get("fully_configured"):
            fails.append("production_verified_without_full_configuration")

    if result.get("external_verification_passed") and not result.get(
        "external_verification_allowed"
    ):
        fails.append("verification_passed_without_being_allowed")

    for field in (
        "external_object_store_contacted",
        "credential_values_read_into_a_result",
        "credential_values_printed",
        "production_storage",
    ):
        if result.get(field):
            fails.append(f"claimed:{field}")
    for field in ("network_calls", "body_bytes_written"):
        if result.get(field):
            fails.append(f"nonzero:{field}")

    # No value, anywhere in the result. Checked against the serialised form so
    # a nested field cannot smuggle one past a per-key check.
    rendered = json.dumps(result)
    for marker in ("http://", "https://", "AKIA", "aws_secret", "-----BEGIN"):
        if marker in rendered:
            fails.append(f"result_carries_a_value_shaped_marker:{marker}")

    if not result.get("object_store_configured") and not result.get("blocked_reasons"):
        if state != HERMETIC_FAKE_VERIFIED:
            fails.append("not_configured_and_nothing_blocked_it")

    return fails
