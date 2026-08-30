"""Customer auth signing key readiness (Gate 119B).

Gate 118B answered one question about the signing key: is there one? This
service answers the rest of them, and none of the answers is the key.

## Presence is not readiness

```text
present      something is set
configured   it is set in a place production may read from
length_ok    it is long enough to be a key rather than a word
rotation     there is a way to replace it without downtime
readiness    all of the above
```

A key that exists but came from a committed fixture is present and unusable. A
key that is eight characters long is present and forgeable. Gate 118B's boolean
could not tell those apart from a real key, and a session layer that cannot tell
them apart will sign production sessions with a demo secret.

## Sources, and which of them may sign for production

```text
environment        NF_SESSION_SIGNING_KEY is set and is not the fixture
secret_manager     supplied by a managed store, asserted by the caller
local_dev_fixture  the committed fake. Signs nothing anybody should accept.
missing            nothing is set
unknown            a source name this service does not recognise
```

`environment` and `secret_manager` may sign production sessions.
`local_dev_fixture` may not, ever, and an invariant refuses any result that
says otherwise. That is the whole point of naming the source rather than
returning a boolean: "there is a key" and "there is a key we would stake a
customer's session on" are different claims.

## Length, and why it is a floor rather than a measurement

HMAC-SHA256 takes a key of any length and produces the same output size, so
nothing fails loudly when the key is short — it just becomes guessable. The
floor is the digest size, 32 bytes, because a key shorter than the digest adds
no security over one exactly that long.

Entropy is *not* measured. A high-entropy estimate on a short string and a low
estimate on a passphrase are both misleading, and a service that scored keys
would be inventing confidence. What is checked is length, distinct-character
count, and whether the value is the known fixture. Anything beyond that is the
secret manager's job.

## The value never leaves

There is no field for it. `secret_value_exposed` exists as a self-check: it is
derived by scanning this service's own output for anything resembling the key
material it was handed, and an invariant fails if it is ever true. A readiness
report that leaked the key would defeat the reason for having one.

## Rotation may be false

Rotation is not implemented anywhere in NativeForge, and this service says so
rather than omitting the field. `signing_key_rotation_supported` is false and
appears in `next_required_actions`. A signed session cannot be revoked before it
expires (Gate 118B), so rotation is how a leaked key is answered — its absence
is a real gap, and a reported gap is worth more than a missing field.
"""

from __future__ import annotations

import json
import os
from typing import Any

from nativeforge.services.customer_session_format_service import (
    FIXTURE_SIGNING_KEY,
    SIGNING_KEY_ENV,
)

SCHEMA_VERSION = "nf_customer_auth_signing_key_readiness_v1"

# Where a key may come from. Bridged nowhere because nothing else names these
# yet; this service is the origin of the vocabulary.
KEY_SOURCES = frozenset(
    {
        "environment",
        "secret_manager",
        "local_dev_fixture",
        "missing",
        "unknown",
    }
)

# Only these two may sign a session a customer would be held to.
PRODUCTION_KEY_SOURCES = frozenset({"environment", "secret_manager"})

# The HMAC-SHA256 digest size. A key shorter than the digest buys nothing over
# one exactly that long, so this is a floor rather than a preference.
MIN_KEY_LENGTH = 32

# A key made of four repeated characters is long and not a key. This is a
# crude floor, deliberately: see the module docstring on why entropy is not
# scored.
MIN_DISTINCT_CHARACTERS = 8

# No field here may ever carry key material. Named so an invariant can check.
FORBIDDEN_VALUE_FIELDS = frozenset(
    {
        "signing_key",
        "signing_key_value",
        "key",
        "key_value",
        "secret",
        "secret_value",
    }
)

RESULT_FIELDS: tuple[str, ...] = (
    "schema_version",
    "signing_key_configured",
    "signing_key_present",
    "signing_key_source",
    "signing_key_length_ok",
    "signing_key_rotation_supported",
    "can_sign_production_session",
    "can_verify_production_session",
    "secret_value_exposed",
    "blocked_reasons",
    "next_required_actions",
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _environment_key() -> str:
    """Read the configured key. Never returned; only measured."""
    return (os.environ.get(SIGNING_KEY_ENV) or "").strip()


def _length_ok(material: str) -> bool:
    return (
        len(material) >= MIN_KEY_LENGTH
        and len(set(material)) >= MIN_DISTINCT_CHARACTERS
    )


def _detect_source(material: str, *, secret_manager_present: bool) -> str:
    """Name where the key came from, preferring the strongest claim."""
    if secret_manager_present:
        return "secret_manager"
    if not material:
        return "missing"
    if material == FIXTURE_SIGNING_KEY or material.startswith("nf-demo-fixture-"):
        return "local_dev_fixture"
    return "environment"


def build_signing_key_readiness(
    *,
    signing_key_material: str | None = None,
    secret_manager_present: bool = False,
    declared_source: str | None = None,
    rotation_supported: bool = False,
) -> dict[str, Any]:
    """Report whether a signing key is fit to sign a production session.

    ``signing_key_material`` is injectable so a test can exercise the permitted
    branch without setting a process-wide environment variable. When it is not
    supplied the environment is read. The value is measured and discarded; no
    caller of this function can obtain it back.

    ``declared_source`` lets a caller assert a source. It is honoured only when
    it agrees with what was detected — a caller claiming ``environment`` for the
    committed fixture is the shape of a bug, and detection wins. Both Gate 117
    and Gate 118 learned that a declared fact overriding a derived one is how
    this campaign's defects are born.
    """
    injected = signing_key_material is not None
    material = (
        str(signing_key_material or "").strip() if injected else _environment_key()
    )

    present = bool(material) or bool(secret_manager_present)
    detected_source = _detect_source(
        material, secret_manager_present=bool(secret_manager_present)
    )

    blocked_reasons: list[str] = []
    next_required_actions: list[str] = []

    declared = str(declared_source or "").strip().lower()
    if declared and declared not in KEY_SOURCES:
        blocked_reasons.append("declared_signing_key_source_not_recognised")
    elif declared and declared != detected_source:
        # Derived beats declared. Recorded rather than silently discarded.
        blocked_reasons.append(
            f"declared_source_{declared}_contradicts_detected_{detected_source}"
        )

    source = detected_source
    if source not in KEY_SOURCES:
        source = "unknown"
        blocked_reasons.append("signing_key_source_not_recognised")

    # A secret manager supplies the key out of band, so there is no material
    # here to measure. Length is asserted by the manager, not by us, and saying
    # so is more honest than reporting a length check that did not run.
    if source == "secret_manager" and not material:
        length_ok = True
    else:
        length_ok = _length_ok(material)

    if not present:
        blocked_reasons.append("no_signing_key_configured")
        next_required_actions.append(
            f"set_{SIGNING_KEY_ENV}_out_of_band_or_supply_a_secret_manager"
        )
    elif source == "local_dev_fixture":
        blocked_reasons.append("signing_key_is_the_committed_local_dev_fixture")
        next_required_actions.append(
            f"replace_the_fixture_key_with_a_real_{SIGNING_KEY_ENV}_value"
        )
    elif not length_ok:
        blocked_reasons.append(
            f"signing_key_shorter_than_{MIN_KEY_LENGTH}_characters_or_too_repetitive"
        )
        next_required_actions.append(
            f"supply_a_signing_key_of_at_least_{MIN_KEY_LENGTH}_characters"
        )

    configured = bool(present and source in PRODUCTION_KEY_SOURCES)
    if present and source not in PRODUCTION_KEY_SOURCES and source != "missing":
        blocked_reasons.append(f"source_{source}_may_not_sign_a_production_session")

    rotation = bool(rotation_supported)
    if not rotation:
        # Not a blocked reason: a key without rotation still signs. It is a
        # named gap, because a signed session cannot be revoked before expiry.
        next_required_actions.append("implement_signing_key_rotation")

    can_sign = bool(configured and length_ok and not blocked_reasons)
    # Verification needs the same key. There is no asymmetric path here, so a
    # key that cannot sign cannot verify either — stated as a derivation so it
    # moves if an asymmetric format is ever introduced.
    can_verify = bool(can_sign)

    result = {
        "schema_version": SCHEMA_VERSION,
        "signing_key_configured": configured,
        "signing_key_present": present,
        "signing_key_source": source,
        "signing_key_length_ok": bool(length_ok),
        "signing_key_rotation_supported": rotation,
        "can_sign_production_session": can_sign,
        "can_verify_production_session": can_verify,
        "secret_value_exposed": False,
        "blocked_reasons": sorted(set(blocked_reasons)),
        "next_required_actions": sorted(set(next_required_actions)),
    }
    # Self-check: does anything in the output carry the material it measured?
    result["secret_value_exposed"] = _material_leaked(result, material)
    return _json_safe(result)


def _material_leaked(result: dict[str, Any], material: str) -> bool:
    """Did any field come to contain the key material it was handed?

    Short material is not searched for: a two-character key would match by
    coincidence in a schema version and report a leak that did not happen.
    """
    if len(material) < 8:
        return False
    return material in json.dumps(result)


def signing_key_readiness_invariant_failures(result: dict[str, Any]) -> list[str]:
    """Contradictions this service must never be able to produce."""
    failures: list[str] = []

    source = str(result.get("signing_key_source") or "")
    if source not in KEY_SOURCES:
        failures.append("signing_key_source_outside_vocabulary")

    if result.get("secret_value_exposed"):
        failures.append("signing_key_material_reached_the_result")

    for field in FORBIDDEN_VALUE_FIELDS:
        if field in result:
            failures.append(f"result_carries_{field}")

    if source == "local_dev_fixture" and result.get("can_sign_production_session"):
        failures.append("local_dev_fixture_claimed_a_production_session")

    if source == "missing" and result.get("signing_key_present"):
        failures.append("missing_source_claimed_a_present_key")

    if result.get("signing_key_configured") and source not in PRODUCTION_KEY_SOURCES:
        failures.append("configured_claimed_for_a_non_production_source")

    if result.get("can_sign_production_session") and not result.get(
        "signing_key_configured"
    ):
        failures.append("signing_permitted_without_a_configured_key")

    if result.get("can_sign_production_session") != result.get(
        "can_verify_production_session"
    ):
        # One symmetric key does both. If these ever diverge the format changed
        # and this invariant is the thing that should notice.
        failures.append("sign_and_verify_diverged_under_a_symmetric_key")

    if result.get("can_sign_production_session") and result.get("blocked_reasons"):
        failures.append("signing_permitted_with_blocked_reasons_present")

    if not result.get("signing_key_present") and not result.get("blocked_reasons"):
        failures.append("no_key_and_no_reason_given")

    return sorted(set(failures))
