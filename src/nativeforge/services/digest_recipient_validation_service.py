"""Gate 142D: who a digest would go to, as a fingerprint and a domain.

## The address never leaves this module

```text
in    an address, from nf_identities, held in a local variable
out   a fingerprint, a domain, a verification boolean, a refusal reason
```

`nf_identities.email` holds a real address because OIDC handed it over. Every
row downstream of that holds a fingerprint instead — `nf_membership_invites`
has carried `invited_email_domain` plus `invited_email_fingerprint` since
migration 0039, for the reason written into
`membership_invite_repository_service`:

> enough for acceptance to require that the identity accepting is the identity
> invited, without the row holding the address that would let something else
> send to it.

A delivery queue is the most downstream thing there is. `email_fingerprint` is
imported from that module rather than reimplemented: two hashing schemes would
drift and then disagree about whether a recipient matched.

## A domain is reported and an address is not

The domain is what makes a refusal legible — "nobody at this organization uses
that domain" is a thing an operator can act on, and it names no mailbox. The
local part is what identifies a person, and it never appears in a result.

## Verified is a fact somebody established, not a shape

```text
recipient_verified   nf_identities.email_verified, which comes from an OIDC
                     token signature. Not "the address parses."
```

A well-formed address nobody verified is refused with
`recipient_not_verified` rather than accepted because it looks fine. This is
the same distinction the eligibility contract makes everywhere else in this
system: a shape is not a fact.

## Nothing is contacted

No DNS lookup, no MX check, no provider validation API, no socket. "Is this
domain deliverable" is a question only a network can answer, and this module
does not ask it — it reports what the rows say and names what it did not check.
"""

from __future__ import annotations

import json
import re
from typing import Any

from nativeforge.services.membership_invite_repository_service import (
    email_fingerprint,
)

SCHEMA_VERSION = "nf_digest_recipient_validation_v1"

#: Deliberately loose. This is a shape check, not an RFC 5322 parser, and a
#: parser here would give a false impression that the address was validated.
#: The real question - is it verified - is answered from a row.
ADDRESS_SHAPE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

MAX_ADDRESS_LENGTH = 320

#: Where a recipient came from. Mirrors migration 0041's CHECK.
RECIPIENT_SOURCES: frozenset[str] = frozenset(
    {
        "org_membership",
        "controlled_fixture",
        "tenant_requested",
        "needs_human_review",
        "unknown",
    }
)

#: Sources that need a person to look before anything is delivered.
HUMAN_REVIEW_SOURCES: frozenset[str] = frozenset(
    {"tenant_requested", "needs_human_review", "unknown"}
)

#: A fixture recipient must live here, so nothing can mistake one for a real
#: mailbox. RFC 2606 reserves it precisely so it can never be delivered to.
FIXTURE_DOMAIN = "invalid"

REFUSAL_REASONS: tuple[str, ...] = (
    "recipient_shape_invalid",
    "recipient_not_verified",
    "recipient_domain_not_allowed",
    "recipient_address_too_long",
    "recipient_source_not_recognised",
    "no_recipient_supplied",
)

#: What a validation result carries. No address is among them.
RESULT_FIELDS: tuple[str, ...] = (
    "recipient_fingerprint",
    "recipient_domain",
    "recipient_source",
    "recipient_verified",
    "deliverable",
    "human_review_required",
    "blocked_reasons",
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _domain_of(address: str) -> str | None:
    _, _, domain = address.partition("@")
    domain = domain.strip().lower()
    return domain or None


def validate_recipient(
    *,
    address: Any = None,
    verified: Any = None,
    recipient_source: Any = None,
    allowed_domains: Any = None,
) -> dict[str, Any]:
    """Is this a recipient a digest may be recorded against? Deny by default.

    ``address`` is read here and never returned. Everything downstream of this
    call sees a fingerprint.
    """
    text = str(address or "").strip().lower()
    source = str(recipient_source or "unknown").strip().lower()
    blocked: list[str] = []

    if not text:
        blocked.append("no_recipient_supplied")
    elif len(text) > MAX_ADDRESS_LENGTH:
        blocked.append("recipient_address_too_long")
    elif not ADDRESS_SHAPE.match(text):
        blocked.append("recipient_shape_invalid")

    if source not in RECIPIENT_SOURCES:
        blocked.append("recipient_source_not_recognised")

    domain = _domain_of(text) if text else None

    allowed = {
        str(d).strip().lower() for d in (allowed_domains or []) if str(d).strip()
    }
    if allowed and domain and domain not in allowed:
        blocked.append("recipient_domain_not_allowed")

    # Verified is a fact somebody established. A shape is not a fact.
    is_verified = bool(verified)
    if not is_verified:
        blocked.append("recipient_not_verified")

    fingerprint = email_fingerprint(text) if text else None
    if fingerprint is None and "recipient_shape_invalid" not in blocked:
        if text:
            blocked.append("recipient_shape_invalid")

    human_review = source in HUMAN_REVIEW_SOURCES

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            # A handle, never the address it was made from.
            "recipient_fingerprint": fingerprint,
            "recipient_domain": domain,
            "recipient_source": source,
            "recipient_verified": is_verified,
            "deliverable": not blocked,
            "human_review_required": human_review,
            "is_fixture_recipient": bool(
                domain and domain.split(".")[-1] == FIXTURE_DOMAIN
            ),
            # Stated, so a reader does not infer a guarantee from an absence.
            "address_reported": False,
            "address_stored": False,
            "local_part_reported": False,
            # What this module did NOT check, named rather than implied.
            "dns_checked": False,
            "mx_checked": False,
            "provider_validation_called": False,
            "network_calls": 0,
            "refusal_reasons_available": list(REFUSAL_REASONS),
            "blocked_reasons": sorted(set(blocked)),
        }
    )


def resolve_org_recipients(
    *,
    connection: Any = None,
    organization_id: Any = None,
    allowed_domains: Any = None,
) -> dict[str, Any]:
    """Every active member of one organization, as fingerprints.

    Reads `nf_identities.email` and `nf_identities.email_verified` through the
    membership rows, validates each, and returns only fingerprints. No address
    is placed in the returned structure.
    """
    import sqlalchemy as sa

    recipients: list[dict[str, Any]] = []
    blocked: list[str] = []
    rows_read = 0

    if connection is None:
        blocked.append("no_connection_supplied_so_nothing_was_read")
    if not str(organization_id or "").strip():
        blocked.append("recipients_without_an_organization_id_anchor")

    if not blocked:
        import uuid as _uuid

        try:
            anchor = _uuid.UUID(str(organization_id))
        except (ValueError, AttributeError, TypeError):
            return _json_safe(
                {
                    "schema_version": SCHEMA_VERSION,
                    "organization_id": None,
                    "recipients": [],
                    "rows_read": 0,
                    "deliverable_count": 0,
                    "addresses_reported": False,
                    "blocked_reasons": ["organization_id_anchor_is_not_uuid_shaped"],
                }
            )

        found = connection.execute(
            sa.text(
                "SELECT i.email, i.email_verified "
                "FROM nf_identities i "
                "JOIN nf_org_memberships m ON m.identity_id = i.id "
                "WHERE m.organization_id = :o AND m.state = 'active' "
                "AND i.disabled_at IS NULL "
                "ORDER BY i.id"
            ),
            {"o": anchor.hex},
        ).all()
        rows_read = len(found)

        for email, verified in found:
            # `email` is read into this loop variable and reaches nothing else.
            recipients.append(
                validate_recipient(
                    address=email,
                    verified=verified,
                    recipient_source="org_membership",
                    allowed_domains=allowed_domains,
                )
            )

    deliverable = [r for r in recipients if r["deliverable"]]
    if rows_read and not deliverable:
        blocked.append("no_member_of_this_organization_has_a_verified_address")
    if not rows_read and not blocked:
        blocked.append("this_organization_has_no_active_members")

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "organization_id": str(organization_id) if organization_id else None,
            "recipients": recipients,
            "rows_read": rows_read,
            "deliverable_count": len(deliverable),
            "human_review_count": sum(
                1 for r in recipients if r["human_review_required"]
            ),
            "addresses_reported": False,
            "addresses_stored": False,
            "dns_checked": False,
            "network_calls": 0,
            "blocked_reasons": sorted(set(blocked)),
        }
    )


def recipient_invariant_failures(result: dict[str, Any]) -> list[str]:
    """What must never be true of a recipient validation result."""
    fails: list[str] = []

    for field in (
        "address_reported",
        "address_stored",
        "local_part_reported",
        "dns_checked",
        "mx_checked",
        "provider_validation_called",
    ):
        if result.get(field):
            fails.append(f"claimed:{field}")
    if result.get("network_calls"):
        fails.append("nonzero:network_calls")

    if result.get("deliverable"):
        if not result.get("recipient_verified"):
            fails.append("deliverable_without_a_verified_recipient")
        if not result.get("recipient_fingerprint"):
            fails.append("deliverable_without_a_fingerprint")
        if result.get("blocked_reasons"):
            fails.append("deliverable_alongside_blockers")

    fingerprint = result.get("recipient_fingerprint")
    if fingerprint is not None:
        if "@" in str(fingerprint):
            fails.append("the_fingerprint_is_an_address")
        if len(str(fingerprint)) != 32:
            fails.append(f"fingerprint_is_not_32_characters:{len(str(fingerprint))}")

    # No address anywhere in the result. Checked against the serialised form,
    # because a nested field is exactly where one would arrive unnoticed.
    rendered = json.dumps(result)
    if "@" in rendered:
        fails.append("result_carries_an_address_shaped_string")

    if not result.get("deliverable") and not result.get("blocked_reasons"):
        fails.append("not_deliverable_and_nothing_blocked_it")

    return fails


def recipient_set_invariant_failures(result: dict[str, Any]) -> list[str]:
    """The same, for a whole organization's recipients."""
    fails: list[str] = []

    for field in ("addresses_reported", "addresses_stored", "dns_checked"):
        if result.get(field):
            fails.append(f"claimed:{field}")
    if result.get("network_calls"):
        fails.append("nonzero:network_calls")

    for recipient in result.get("recipients") or []:
        fails.extend(recipient_invariant_failures(recipient))

    rendered = json.dumps(result)
    if "@" in rendered:
        fails.append("recipient_set_carries_an_address_shaped_string")

    deliverable = sum(1 for r in result.get("recipients") or [] if r["deliverable"])
    if int(result.get("deliverable_count") or 0) != deliverable:
        fails.append("deliverable_count_disagrees_with_the_recipients")

    return fails
