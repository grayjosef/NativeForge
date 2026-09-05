"""Gate 142B: is an email provider configured? Names and states, never a value.

## What this reports and what it refuses to report

```text
reports    which setting NAMES are present, absent or placeholder
           a state, one of five
           whether SEND is activated, which is a separate question
never      a host, a port, a username, an API key, a sender address, a
           domain, or a prefix of any of them
```

Same shape as Gate 141B's object storage preflight, deliberately: two
capabilities that both mean "configured or not" should not answer in two
different vocabularies.

## Five states

```text
no_config                  nothing is set. Where this checkout is.
partial_config             some set, some not. It looks configured to a reader
                           and can deliver nothing.
configured_but_unverified  all set, nothing has proved a provider accepts them.
dry_run_verified           a digest rendered, a recipient validated and an
                           intent was recorded. Proves the CODE. Nothing about
                           any mailbox.
send_activated             a provider is configured, verified, AND somebody
                           explicitly activated sending. Not produced here.
```

## Configuration is not activation

Two questions, and this module keeps them apart because collapsing them is how
a deployment starts mailing people the day somebody pastes an API key into an
environment file:

```text
provider_configured    are the settings there?
send_activated         did somebody decide to send?
```

`email_delivery` is true only for `send_activated`, and `send_activated`
requires an explicit approval this module cannot manufacture. A dry run may
never produce it — a rehearsal that could flip the live flag would make every
"not live" above it unfalsifiable, which is the failure mode Gate 141B named
for the object store and Gate 134F removed from the customer-auth chain.

## No provider is contacted, and nothing imports a mail library

There is no smtplib import here, no socket, no HTTP client. Unlike Gate 141's
object store there is no "the SDK is not installed" guarantee available —
`smtplib` ships with Python — so the guarantee is that no module imports it,
which a test checks by parsing rather than by running.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

SCHEMA_VERSION = "nf_email_provider_configuration_preflight_v1"

#: What a configured provider would need. Named as settings that do not exist
#: yet, so a reader can see exactly what would have to be added - and so the
#: absent list is a to-do rather than a mystery.
REQUIRED_SETTING_NAMES: tuple[str, ...] = (
    "nf_email_provider",
    "nf_email_api_endpoint",
    "nf_email_api_key",
    "nf_email_sender_address",
    "nf_email_sender_domain",
)

#: Settings whose presence may be reported and whose value must never be, not
#: even truncated. A sender address is a real mailbox and is treated as one.
SECRET_SETTING_NAMES: frozenset[str] = frozenset(
    {
        "nf_email_api_key",
        "nf_email_sender_address",
    }
)

#: The setting that would say somebody decided to send. Separate from the five
#: above because configuration and activation are different decisions.
SEND_ACTIVATION_SETTING = "nf_email_send_activated"

NO_CONFIG = "no_config"
PARTIAL_CONFIG = "partial_config"
CONFIGURED_BUT_UNVERIFIED = "configured_but_unverified"
DRY_RUN_VERIFIED = "dry_run_verified"
SEND_ACTIVATED = "send_activated"

PREFLIGHT_STATES: tuple[str, ...] = (
    NO_CONFIG,
    PARTIAL_CONFIG,
    CONFIGURED_BUT_UNVERIFIED,
    DRY_RUN_VERIFIED,
    SEND_ACTIVATED,
)

#: The only state in which email may actually be delivered.
LIVE_STATES: frozenset[str] = frozenset({SEND_ACTIVATED})

#: What `send_activated` costs, from a caller that measured each. Never
#: inferred from the settings being present.
SEND_EVIDENCE_FIELDS: tuple[str, ...] = (
    "provider_verification_allowed",
    "provider_verification_passed",
    "send_activation_approved",
)

#: Values that look like configuration and are not. Reused shape from Gate 97's
#: placeholder detection rather than a second scheme.
PLACEHOLDER_VALUES: frozenset[str] = frozenset(
    {
        "changeme",
        "change-me",
        "example",
        "placeholder",
        "todo",
        "tbd",
        "your-api-key",
        "xxx",
        "none",
        "null",
    }
)

PLACEHOLDER_MARKERS: tuple[str, ...] = (
    "example.com",
    "example.org",
    "your-",
    "<",
    "changeme",
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def is_placeholder_value(value: Any) -> bool:
    """Is this a value somebody pasted from a README?"""
    text = str(value or "").strip().lower()
    if not text:
        return False
    if text in PLACEHOLDER_VALUES:
        return True
    return any(marker in text for marker in PLACEHOLDER_MARKERS)


def _settings():
    from nativeforge.lib.settings import get_settings

    return get_settings()


def _raw(settings: Any, name: str) -> str:
    """One setting as text, for presence testing only.

    The return value is consumed by `bool()` and `is_placeholder_value()` here
    and reaches no caller. A `SecretStr` is unwrapped because `str()` of a
    pydantic secret is the literal `'**********'`, which would read as a
    present value for every unset secret in the project.
    """
    value = getattr(settings, name, None)
    if hasattr(value, "get_secret_value"):
        value = value.get_secret_value()
    return str(value or "").strip()


def sender_domain_fingerprint(domain: Any) -> str | None:
    """A stable handle for a sender domain that is not the domain.

    Reported instead of the domain itself so two runs can be compared - "the
    sender changed" is a real finding - without the artifact naming where mail
    would come from.
    """
    text = str(domain or "").strip().lower()
    if not text:
        return None
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:32]


def inspect_required_settings(*, settings: Any = None) -> dict[str, Any]:
    """Which setting names are present, placeholder, or absent. Names only."""
    resolved = settings if settings is not None else _settings()

    present: list[str] = []
    placeholder: list[str] = []
    absent: list[str] = []
    for name in REQUIRED_SETTING_NAMES:
        raw = _raw(resolved, name)
        if not raw:
            absent.append(name)
        elif is_placeholder_value(raw):
            placeholder.append(name)
        else:
            present.append(name)

    return _json_safe(
        {
            "required_setting_names": list(REQUIRED_SETTING_NAMES),
            "present_setting_names": sorted(present),
            "placeholder_setting_names": sorted(placeholder),
            "absent_setting_names": sorted(absent),
            "present_count": len(present),
            "required_count": len(REQUIRED_SETTING_NAMES),
            "secret_setting_names": sorted(SECRET_SETTING_NAMES),
            "send_activation_setting_name": SEND_ACTIVATION_SETTING,
            # Stated, so a reader does not infer a guarantee from an absence.
            "values_read": False,
            "values_reported": False,
            "value_lengths_reported": False,
        }
    )


def build_email_provider_preflight(
    *,
    settings: Any = None,
    dry_run_passed: bool = False,
    provider_verification_allowed: bool = False,
    provider_verification_passed: bool = False,
    send_activation_approved: bool = False,
) -> dict[str, Any]:
    """The preflight. Contacts nothing; reads settings and reports names."""
    names = inspect_required_settings(settings=settings)
    resolved = settings if settings is not None else _settings()

    blocked: list[str] = []
    if names["absent_setting_names"]:
        blocked.append(
            "email_settings_absent:" + ",".join(names["absent_setting_names"])
        )
    if names["placeholder_setting_names"]:
        blocked.append(
            "email_settings_are_placeholders:"
            + ",".join(names["placeholder_setting_names"])
        )

    fully_configured = names["present_count"] == names["required_count"]

    # -- activation, which is a decision and not a value --------------------
    setting_says_activated = bool(_raw(resolved, SEND_ACTIVATION_SETTING))
    allowed = bool(provider_verification_allowed)
    passed = bool(provider_verification_passed)
    approved = bool(send_activation_approved)

    if passed and not allowed:
        blocked.append("provider_verification_passed_without_being_allowed")
        passed = False
    if approved and not fully_configured:
        blocked.append("send_activation_approved_without_a_configured_provider")
        approved = False
    if setting_says_activated and not approved:
        # A setting is not an approval. Somebody flipping an env var is not the
        # decision this gate requires, and saying so is the point.
        blocked.append("send_activation_setting_present_without_an_approval")

    if fully_configured and allowed and passed and approved:
        state = SEND_ACTIVATED
    elif fully_configured:
        state = CONFIGURED_BUT_UNVERIFIED
    elif dry_run_passed and names["present_count"] == 0:
        state = DRY_RUN_VERIFIED
    elif names["present_count"] or names["placeholder_setting_names"]:
        state = PARTIAL_CONFIG
    else:
        state = NO_CONFIG

    if fully_configured and allowed and not passed:
        blocked.append("provider_verification_allowed_but_did_not_pass")
    if not fully_configured:
        blocked.append("no_email_provider_configured")
    if not approved:
        blocked.append("send_activation_absent")

    email_delivery = state in LIVE_STATES

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "state": state,
            "states": list(PREFLIGHT_STATES),
            "provider_configured": fully_configured,
            "send_activated": approved and email_delivery,
            "email_delivery": email_delivery,
            **names,
            "sender_domain_fingerprint": sender_domain_fingerprint(
                _raw(resolved, "nf_email_sender_domain")
            ),
            "dry_run_passed": bool(dry_run_passed),
            "provider_verification_allowed": allowed,
            "provider_verification_passed": passed,
            "send_activation_approved": approved,
            "send_evidence_fields": list(SEND_EVIDENCE_FIELDS),
            # Constants. Nothing in this module can set any of them.
            "provider_contacted": False,
            "network_calls": 0,
            "emails_sent": 0,
            "send_attempted": False,
            "credential_values_read_into_a_result": False,
            "credential_values_printed": False,
            "recipient_addresses_reported": False,
            "production_email_delivery": False,
            "blocked_reasons": sorted(set(blocked)),
        }
    )


def email_preflight_invariant_failures(result: dict[str, Any]) -> list[str]:
    """What must never be true of an email provider preflight result."""
    fails: list[str] = []

    state = result.get("state")
    if state not in PREFLIGHT_STATES:
        fails.append(f"state_not_recognised:{state}")

    if result.get("email_delivery") and state != SEND_ACTIVATED:
        fails.append(f"email_delivery_in_state:{state}")

    # The load-bearing one. A rehearsal may not switch on the real thing.
    if state == DRY_RUN_VERIFIED and result.get("email_delivery"):
        fails.append("a_dry_run_activated_email_delivery")
    if result.get("dry_run_passed") and result.get("send_activated"):
        if state != SEND_ACTIVATED:
            fails.append("a_dry_run_activated_sending")

    if state == SEND_ACTIVATED:
        for field in SEND_EVIDENCE_FIELDS:
            if not result.get(field):
                fails.append(f"send_activated_without:{field}")
        if not result.get("provider_configured"):
            fails.append("send_activated_without_a_configured_provider")

    if result.get("provider_verification_passed") and not result.get(
        "provider_verification_allowed"
    ):
        fails.append("verification_passed_without_being_allowed")
    if result.get("send_activation_approved") and not result.get("provider_configured"):
        fails.append("send_approved_without_a_configured_provider")

    for field in (
        "provider_contacted",
        "send_attempted",
        "credential_values_read_into_a_result",
        "credential_values_printed",
        "recipient_addresses_reported",
        "production_email_delivery",
    ):
        if result.get(field):
            fails.append(f"claimed:{field}")
    for field in ("network_calls", "emails_sent"):
        if result.get(field):
            fails.append(f"nonzero:{field}")

    # No value, anywhere. Checked against the serialised form so a nested field
    # cannot smuggle one past a per-key check.
    rendered = json.dumps(result)
    for marker in ("@", "http://", "https://", "smtp", "-----BEGIN"):
        if marker in rendered:
            fails.append(f"result_carries_a_value_shaped_marker:{marker}")

    if not result.get("email_delivery") and not result.get("blocked_reasons"):
        fails.append("not_delivering_and_nothing_blocked_it")

    return fails
