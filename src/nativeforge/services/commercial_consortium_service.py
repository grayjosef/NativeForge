"""178A2: the intertribal consortium suite — quoted, never computed.

When Tribes join together, the thing being sold stops being one licence for
one organisation. A consortium is priced as a SUITE, and the operator's
instruction names the three things it depends on:

```text
ISOLATION NEED   do member Tribes share a workspace, or must each one's
                 pursuits be invisible to the others?
COMPLEXITY       how much of this is standard, and how much is bespoke?
SEATS            how many named people across the whole consortium?
```

## Why there is no price in this module

A suite price depending on isolation, complexity and seats is a commercial
judgement. A function that multiplied three factors and returned a number
would return a WRONG number, confidently, to a group of sovereign
governments negotiating together — and the wrongness would be invisible
because it would look like arithmetic rather than like a guess.

So `build_consortium_quote_request` produces a QUOTE REQUEST: the dimensions
captured, the inputs recorded, `price_cents` explicitly `None`, and
`requires_human_quote` true. `quote_invariant_failures` refuses a request
that arrived carrying a price.

This is the same discipline as the coverage scorecard refusing to report a
percentage against an unknown denominator. The system is allowed to say "a
person decides this", and saying so is more useful than a number nobody
should trust.

## Isolation is not a preference, it is an architecture

`ISOLATED_PER_MEMBER` means each member Tribe is its own tenant: one Tribe's
pursuits, documents and decisions are invisible to the others, which is the
isolation Gate 179 proved and the reason that proof matters commercially.
`SHARED_WORKSPACE` means the consortium operates as one organisation. These
cost differently because they ARE different, and the quote records which was
asked for so nobody later discovers they bought the other one.

A consortium that has not stated its isolation model is not quotable, and
`ISOLATION_UNKNOWN` is an outcome rather than a default.
"""

from __future__ import annotations

import datetime as dt
import hashlib
from typing import Any

from nativeforge.services.commercial_license_model_service import (
    ANNUAL_MAINTENANCE_PRICE_CENTS,
    INCLUDED_MAINTENANCE_MONTHS,
    PERSISTENT_LICENSE_PRICE_CENTS,
    POLICY_VERSION,
    dollars,
)

SCHEMA_VERSION = "nf_commercial_consortium_v1"

# ---------------------------------------------------------------------------
# The two things NativeForge sells.
# ---------------------------------------------------------------------------

OFFERING_SINGLE_ORGANIZATION = "SINGLE_ORGANIZATION"
OFFERING_INTERTRIBAL_CONSORTIUM = "INTERTRIBAL_CONSORTIUM"

OFFERINGS: tuple[str, ...] = (
    OFFERING_SINGLE_ORGANIZATION,
    OFFERING_INTERTRIBAL_CONSORTIUM,
)

OFFERING_MEANINGS: dict[str, str] = {
    OFFERING_SINGLE_ORGANIZATION: (
        "one Tribe or Native organisation, one persistent licence at the "
        "published price"
    ),
    OFFERING_INTERTRIBAL_CONSORTIUM: (
        "several Tribes together, priced as a suite on isolation need, "
        "complexity and seats. Quoted by a person, never computed"
    ),
}

#: Offerings with a published price. The consortium is deliberately absent.
PUBLISHED_PRICE: frozenset[str] = frozenset({OFFERING_SINGLE_ORGANIZATION})

# ---- isolation ---------------------------------------------------------
ISOLATION_SHARED_WORKSPACE = "SHARED_WORKSPACE"
ISOLATION_ISOLATED_PER_MEMBER = "ISOLATED_PER_MEMBER"
ISOLATION_HYBRID = "HYBRID"
ISOLATION_UNKNOWN = "ISOLATION_UNKNOWN"

ISOLATION_MODELS: tuple[str, ...] = (
    ISOLATION_SHARED_WORKSPACE,
    ISOLATION_ISOLATED_PER_MEMBER,
    ISOLATION_HYBRID,
    ISOLATION_UNKNOWN,
)

ISOLATION_MEANINGS: dict[str, str] = {
    ISOLATION_SHARED_WORKSPACE: (
        "the consortium operates as one organisation; members see each other's pursuits"
    ),
    ISOLATION_ISOLATED_PER_MEMBER: (
        "each member Tribe is its own tenant. One member's pursuits, "
        "documents and decisions are invisible to the others, and the "
        "consortium sees only what members publish to it"
    ),
    ISOLATION_HYBRID: (
        "shared discovery and a common calendar, isolated pursuits — the "
        "arrangement most consortia actually ask for"
    ),
    ISOLATION_UNKNOWN: (
        "not stated yet. This is an outcome, not a default: a consortium "
        "that has not decided this is not quotable"
    ),
}

#: Isolation models a quote can be prepared against.
QUOTABLE_ISOLATION: frozenset[str] = frozenset(
    {ISOLATION_SHARED_WORKSPACE, ISOLATION_ISOLATED_PER_MEMBER, ISOLATION_HYBRID}
)

# ---- complexity --------------------------------------------------------
COMPLEXITY_STANDARD = "STANDARD"
COMPLEXITY_ELEVATED = "ELEVATED"
COMPLEXITY_BESPOKE = "BESPOKE"
COMPLEXITY_UNKNOWN = "COMPLEXITY_UNKNOWN"

COMPLEXITY_LEVELS: tuple[str, ...] = (
    COMPLEXITY_STANDARD,
    COMPLEXITY_ELEVATED,
    COMPLEXITY_BESPOKE,
    COMPLEXITY_UNKNOWN,
)

COMPLEXITY_MEANINGS: dict[str, str] = {
    COMPLEXITY_STANDARD: "the product as it ships, for every member",
    COMPLEXITY_ELEVATED: (
        "additional reporting, a consortium-level rollup, or member "
        "onboarding beyond the usual"
    ),
    COMPLEXITY_BESPOKE: (
        "work that does not exist yet: custom integrations, a governance "
        "model the product does not have, or data migration"
    ),
    COMPLEXITY_UNKNOWN: "not yet assessed",
}

#: The factors a person weighs. Named so a quote can say WHY, and so two
#: quotes prepared by different people are comparable.
COMPLEXITY_FACTORS: tuple[str, ...] = (
    "MEMBER_ONBOARDING_EFFORT",
    "CONSORTIUM_LEVEL_REPORTING",
    "CROSS_MEMBER_GOVERNANCE",
    "EXISTING_SYSTEM_INTEGRATION",
    "DATA_MIGRATION",
    "TRAINING_AND_ENABLEMENT",
    "COMPLIANCE_OR_AUDIT_REQUIREMENTS",
)

QUOTE_FIELDS: tuple[str, ...] = (
    "quote_request_id",
    "offering",
    "consortium_name",
    "member_organization_ids",
    "member_count",
    "isolation_model",
    "complexity_level",
    "complexity_factors",
    "seats_requested",
    "seats_per_member",
    "notes",
    "requested_by",
    "requested_at",
    "price_cents",
    "requires_human_quote",
    "quotable",
    "blocking_unknowns",
    "reference_single_license_price_cents",
    "policy_version",
)


def build_quote_request_id(
    *, consortium_name: Any, requested_at: Any, member_count: Any
) -> str:
    parts = [str(consortium_name or ""), str(requested_at or ""), str(member_count)]
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()


def build_consortium_quote_request(
    *,
    consortium_name: Any,
    member_organization_ids: list[str] | None = None,
    isolation_model: str = ISOLATION_UNKNOWN,
    complexity_level: str = COMPLEXITY_UNKNOWN,
    complexity_factors: list[str] | None = None,
    seats_requested: int | None = None,
    seats_per_member: dict[str, int] | None = None,
    requested_by: Any = None,
    requested_at: Any = None,
    notes: Any = None,
) -> dict[str, Any]:
    """Capture what a consortium suite quote depends on. Price nothing.

    Returns a request a person prices. `price_cents` is `None` and stays
    `None`: this module has no arithmetic that could produce one.
    """
    members = sorted(str(m) for m in (member_organization_ids or []))
    factors = sorted(f for f in (complexity_factors or []) if f in COMPLEXITY_FACTORS)
    unrecognised = sorted(
        str(f) for f in (complexity_factors or []) if f not in COMPLEXITY_FACTORS
    )
    when = requested_at or dt.datetime.now(dt.UTC).isoformat()

    # What stops this being quotable. Named individually rather than folded
    # into one "incomplete" flag, so the person chasing it knows what to ask.
    blocking: list[str] = []
    if str(isolation_model) not in QUOTABLE_ISOLATION:
        blocking.append("isolation_model_not_stated")
    if str(complexity_level) == COMPLEXITY_UNKNOWN:
        blocking.append("complexity_not_assessed")
    if not seats_requested or int(seats_requested) < 1:
        blocking.append("seats_not_stated")
    if len(members) < 2:
        blocking.append("fewer_than_two_member_organizations")

    return {
        "schema_version": SCHEMA_VERSION,
        "quote_request_id": build_quote_request_id(
            consortium_name=consortium_name,
            requested_at=when,
            member_count=len(members),
        ),
        "offering": OFFERING_INTERTRIBAL_CONSORTIUM,
        "consortium_name": str(consortium_name) if consortium_name else None,
        "member_organization_ids": members,
        "member_count": len(members),
        "isolation_model": str(isolation_model),
        "complexity_level": str(complexity_level),
        "complexity_factors": factors,
        "unrecognised_complexity_factors": unrecognised,
        "seats_requested": int(seats_requested) if seats_requested else None,
        "seats_per_member": dict(seats_per_member or {}),
        "notes": str(notes) if notes else None,
        "requested_by": str(requested_by) if requested_by else None,
        "requested_at": when,
        # The refusal this module exists for.
        "price_cents": None,
        "requires_human_quote": True,
        "quotable": not blocking,
        "blocking_unknowns": sorted(blocking),
        # Context for the person quoting, NOT a formula. A consortium is not
        # priced by multiplying this by anything.
        "reference_single_license_price_cents": PERSISTENT_LICENSE_PRICE_CENTS,
        "reference_single_license_price": dollars(PERSISTENT_LICENSE_PRICE_CENTS),
        "reference_annual_maintenance_price": dollars(ANNUAL_MAINTENANCE_PRICE_CENTS),
        "reference_included_maintenance_months": INCLUDED_MAINTENANCE_MONTHS,
        "reference_is_not_a_formula": True,
        "policy_version": POLICY_VERSION,
    }


def describe_quote_dimensions() -> dict[str, Any]:
    """What a person weighing this quote is being asked to weigh."""
    return {
        "schema_version": SCHEMA_VERSION,
        "dimensions": ["ISOLATION_NEED", "COMPLEXITY", "SEATS"],
        "isolation_models": list(ISOLATION_MODELS),
        "isolation_meanings": dict(ISOLATION_MEANINGS),
        "complexity_levels": list(COMPLEXITY_LEVELS),
        "complexity_meanings": dict(COMPLEXITY_MEANINGS),
        "complexity_factors": list(COMPLEXITY_FACTORS),
        "quotable_isolation_models": sorted(QUOTABLE_ISOLATION),
    }


def quote_invariant_failures(request: dict[str, Any]) -> list[str]:
    """Refuse a quote request that priced itself."""
    failures: list[str] = []

    for field in QUOTE_FIELDS:
        if field not in request:
            failures.append(f"quote_missing_field:{field}")

    if str(request.get("offering")) != OFFERING_INTERTRIBAL_CONSORTIUM:
        failures.append(f"quote_offering_is_not_a_consortium:{request.get('offering')}")

    # The load-bearing one. A consortium suite price is a commercial
    # judgement; a computed one would be wrong confidently.
    if request.get("price_cents") is not None:
        failures.append("consortium_quote_carries_a_computed_price")
    if not request.get("requires_human_quote"):
        failures.append("consortium_quote_does_not_require_a_human")

    isolation = str(request.get("isolation_model") or "")
    if isolation not in ISOLATION_MODELS:
        failures.append(f"isolation_outside_the_vocabulary:{isolation or 'missing'}")
    complexity = str(request.get("complexity_level") or "")
    if complexity not in COMPLEXITY_LEVELS:
        failures.append(f"complexity_outside_the_vocabulary:{complexity or 'missing'}")

    # A quotable request must actually have its three dimensions.
    if request.get("quotable"):
        if isolation not in QUOTABLE_ISOLATION:
            failures.append("quotable_request_has_no_isolation_model")
        if complexity == COMPLEXITY_UNKNOWN:
            failures.append("quotable_request_has_no_complexity_assessment")
        if not request.get("seats_requested"):
            failures.append("quotable_request_states_no_seats")
        if int(request.get("member_count") or 0) < 2:
            failures.append("quotable_consortium_has_fewer_than_two_members")
    elif not request.get("blocking_unknowns"):
        failures.append("unquotable_request_does_not_say_what_is_missing")

    seats = request.get("seats_requested")
    if seats is not None and int(seats) < 1:
        failures.append("seats_requested_is_not_a_count")

    per_member = request.get("seats_per_member") or {}
    if per_member and seats:
        if sum(int(v) for v in per_member.values()) > int(seats):
            failures.append("seats_per_member_exceeds_seats_requested")

    return sorted(set(failures))


def describe_offering_model() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "policy_version": POLICY_VERSION,
        "offerings": list(OFFERINGS),
        "every_offering_has_a_meaning": set(OFFERING_MEANINGS) == set(OFFERINGS),
        "offerings_with_a_published_price": sorted(PUBLISHED_PRICE),
        "single_organization_price_cents": PERSISTENT_LICENSE_PRICE_CENTS,
        "single_organization_price": dollars(PERSISTENT_LICENSE_PRICE_CENTS),
        "annual_maintenance_price": dollars(ANNUAL_MAINTENANCE_PRICE_CENTS),
        # The refusals.
        "consortium_has_no_published_price": (
            OFFERING_INTERTRIBAL_CONSORTIUM not in PUBLISHED_PRICE
        ),
        "consortium_price_is_never_computed": True,
        "consortium_quote_requires_a_human": True,
        "quote_dimensions_are_named": ["ISOLATION_NEED", "COMPLEXITY", "SEATS"],
        "isolation_unknown_is_an_outcome_not_a_default": (
            ISOLATION_UNKNOWN not in QUOTABLE_ISOLATION
        ),
        "every_isolation_model_has_a_meaning": set(ISOLATION_MEANINGS)
        == set(ISOLATION_MODELS),
        "every_complexity_level_has_a_meaning": set(COMPLEXITY_MEANINGS)
        == set(COMPLEXITY_LEVELS),
        "isolated_per_member_is_the_tenant_isolation_gate_179_proved": True,
        "blocking_unknowns_are_named_individually": True,
    }
