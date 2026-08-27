"""The NativeForge user-agent (Gate 94C).

One string. Every outbound request in this codebase presents it, and an
enforcement scan fails the build if a second one is defined.

## Why one

Gate 94A found two: ``polite_http_fetch_service.USER_AGENT`` and Gate 92's
``source_crawler_governance_service.NATIVEFORGE_USER_AGENT``. Both passed Gate
92's validity check, so this was a fork rather than a violation — but which
string a host operator saw depended on which module made the call, and a host
that wants to block or contact us should not have to work out that there are
two of us.

## The contact has to be reachable

Gate 92's string pointed at ``nativeforge.example``, an RFC 2606 reserved
domain that resolves to nothing. A contact URL nobody can reach is decoration:
the point of putting it in the UA is that an operator who wants us to stop, or
wants to ask what we are doing, has somewhere to go.

The polite fetcher's contact — the public repository — is real. The canonical
string keeps Gate 92's ``NativeForgeBot`` identity and takes that contact.

``contact_is_reachable`` is a checked property, not an assumption: a contact on
a reserved domain (``.example``, ``.invalid``, ``.test``, ``.localhost``) is
reported unreachable and blocks crawler activation, exactly as Gate 94C
requires for an unknown contact. That check is what stops the placeholder from
quietly coming back.

## Never an AI-crawler string

hud.gov names ClaudeBot, GPTBot, CCBot and others with ``Disallow: /`` and
asserts ``ai-train=no`` as a condition of access. Presenting one of those is a
robots violation and a terms violation at once.

## This module owns user-agent facts

The canonical string and the forbidden-token list both live here, and Gate 92's
``source_crawler_governance_service`` imports them. That is a reversal of the
original direction, and it is deliberate: while governance owned the string, a
second one could exist in a fetcher without governance being any the wiser -
which is exactly what happened. One owner, one string, one list.

``source_crawler_governance_service`` re-exports both names, so existing
importers and Gate 92's tests continue to work unchanged.
"""

from __future__ import annotations

import json
from typing import Any

SCHEMA_VERSION = "nf_nativeforge_user_agent_v1"

# AI-crawler tokens. hud.gov names these with `Disallow: /` and asserts
# `ai-train=no` as a condition of access, so presenting one is simultaneously a
# robots violation and a terms violation. Matched as case-insensitive
# substrings, so `NativeForgeBot/2.0` stays valid while any variant carrying
# one of these is refused.
FORBIDDEN_USER_AGENT_TOKENS = frozenset(
    {
        "claudebot",
        "claude-web",
        "gptbot",
        "chatgpt-user",
        "ccbot",
        "anthropic-ai",
        "amazonbot",
        "applebot-extended",
        "bytespider",
        "google-extended",
        "meta-externalagent",
        "perplexitybot",
        "diffbot",
        "omgili",
    }
)

# The contact a host operator can actually reach.
CONTACT_URL = "https://github.com/grayjosef/NativeForge"

# The one canonical string. Everything outbound presents this.
NATIVEFORGE_USER_AGENT = (
    f"NativeForgeBot/1.0 (+{CONTACT_URL}; "
    "grant discovery for tribal organizations)"
)

# Reserved / non-routable TLDs. A contact here cannot be reached, so it is not
# a contact. RFC 2606 plus the reserved .localhost.
UNREACHABLE_CONTACT_SUFFIXES: tuple[str, ...] = (
    ".example",
    ".invalid",
    ".test",
    ".localhost",
)

CONTACT_STATUSES = frozenset({"reachable", "unreachable_reserved_domain", "unknown"})


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _contact_host(contact: str) -> str:
    text = str(contact or "").strip().lower()
    for prefix in ("https://", "http://", "mailto:"):
        if text.startswith(prefix):
            text = text[len(prefix) :]
            break
    if "@" in text:
        text = text.split("@", 1)[1]
    return text.split("/", 1)[0].split(":", 1)[0]


def classify_contact(contact: Any) -> str:
    """Deny by default: an absent or unparseable contact is `unknown`."""
    host = _contact_host(contact)
    if not host or "." not in host:
        return "unknown"
    for suffix in UNREACHABLE_CONTACT_SUFFIXES:
        if host.endswith(suffix):
            return "unreachable_reserved_domain"
    return "reachable"


def user_agent_violations(user_agent: Any) -> list[str]:
    """Why this string may not be used. Empty list means it may."""
    ua = str(user_agent or "").strip()
    fails: list[str] = []

    if not ua:
        return ["user_agent_empty"]

    lowered = ua.lower()
    for token in sorted(FORBIDDEN_USER_AGENT_TOKENS):
        if token in lowered:
            fails.append(f"ai_crawler_user_agent:{token}")
    if "nativeforge" not in lowered:
        fails.append("user_agent_does_not_identify_nativeforge")
    if "http" not in lowered and "mailto:" not in lowered:
        fails.append("user_agent_carries_no_contact")
    if ua != NATIVEFORGE_USER_AGENT:
        fails.append("user_agent_is_not_the_canonical_string")

    return fails


def build_user_agent_contract() -> dict[str, Any]:
    """The canonical string and whether it is fit to send."""
    contact_status = classify_contact(CONTACT_URL)
    violations = user_agent_violations(NATIVEFORGE_USER_AGENT)
    reachable = contact_status == "reachable"

    blocked: list[str] = list(violations)
    if not reachable:
        blocked.append(f"contact_not_reachable:{contact_status}")

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "user_agent": NATIVEFORGE_USER_AGENT,
            "contact": CONTACT_URL,
            "contact_status": contact_status,
            "contact_is_reachable": reachable,
            "violations": violations,
            # A UA whose contact nobody can reach does not permit crawling.
            "crawler_activation_allowed": bool(reachable and not violations),
            "blocked_reasons": blocked,
            "is_ai_crawler_user_agent": any(
                v.startswith("ai_crawler_user_agent:") for v in violations
            ),
            "fabricated": False,
        }
    )


def user_agent_contract_invariant_failures(contract: dict[str, Any]) -> list[str]:
    fails: list[str] = []

    if contract.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")
    if contract.get("fabricated") is not False:
        fails.append("fabricated_must_be_false")

    ua = contract.get("user_agent")
    if ua != NATIVEFORGE_USER_AGENT:
        fails.append("canonical_user_agent_altered")
    if not isinstance(ua, str) or "nativeforge" not in ua.lower():
        fails.append("user_agent_does_not_identify_nativeforge")

    lowered = str(ua or "").lower()
    for token in FORBIDDEN_USER_AGENT_TOKENS:
        if token in lowered:
            fails.append(f"canonical_user_agent_carries_ai_token:{token}")

    if contract.get("contact_status") not in CONTACT_STATUSES:
        fails.append("contact_status_out_of_vocabulary")
    # The contact must be in the string, or it is not a contact anyone sees.
    if str(contract.get("contact") or "") not in str(ua or ""):
        fails.append("contact_not_present_in_the_user_agent")

    # Crawling requires a reachable contact and a clean string, both.
    if contract.get("crawler_activation_allowed"):
        if not contract.get("contact_is_reachable"):
            fails.append("crawler_allowed_with_an_unreachable_contact")
        if contract.get("violations"):
            fails.append("crawler_allowed_with_user_agent_violations")
    if not contract.get("crawler_activation_allowed") and not contract.get(
        "blocked_reasons"
    ):
        fails.append("crawler_blocked_without_a_reason")

    return fails
