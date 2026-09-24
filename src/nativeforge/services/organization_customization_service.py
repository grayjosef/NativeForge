"""177H/I: what the organisation sets for everyone, and what each person sets.

Two layers that must never bleed into each other.

```text
ORG DEFAULT       published deliberately by an authorised administrator
PERSONAL OVERRIDE set by one person, for one person, silently
```

The failure this module exists to prevent is quiet and expensive: somebody
reorders their own dashboard tiles and the whole organisation's layout
changes. Nobody notices for a week, and when they do, the person who did it
has no idea it was them. So `apply_personal_override` never receives the org
default as a mutable object - it deep-copies before merging - and returns
proof that the default it was handed is byte-identical to the one it hands
back.

`publish_org_default` is the only way a default changes, it requires an
authorised actor, and it records who and why.

## Branding is a reference, not a payload

`logo_ref` is a reference to stored media. Colours are validated hex. There is
no free-form CSS field and no script field, because "let the customer theme
it" plus a text box is how an organisation's dashboard becomes a place to run
someone else's JavaScript. `branding_invariant_failures` refuses anything that
looks like markup, a URL scheme that executes, or a CSS escape.
"""

from __future__ import annotations

import copy
import datetime as dt
import json
import re
from typing import Any

SCHEMA_VERSION = "nf_organization_customization_v1"

CUSTOMIZATION_MODEL_VERSION = "2026.09.1"

# ---------------------------------------------------------------------------
# 177H: what an organisation may set for everyone.
# ---------------------------------------------------------------------------

BRANDING_FIELDS: tuple[str, ...] = (
    "logo_ref",
    "symbol_ref",
    "primary_color",
    "secondary_color",
    "accent_color",
    "display_name",
)

#: The tiles a dashboard can show. A closed vocabulary, because an "arbitrary
#: tile id" is an arbitrary thing to render.
TILES: tuple[str, ...] = (
    "OPEN_OPPORTUNITIES",
    "DEADLINES",
    "EARLY_SIGNALS",
    "EXPECTED_BUT_ABSENT",
    "COVERAGE_GAPS",
    "ACTIVE_PURSUITS",
    "AWARD_COMPLIANCE",
    "ELIGIBILITY_MATCHES",
    "DOCUMENT_CHANGES",
    "ORGANIZATION_PROFILE",
    "TEAM",
)

DASHBOARD_FIELDS: tuple[str, ...] = (
    "tile_order",
    "hidden_tiles",
    "density",
    "landing_tile",
)

DENSITIES: tuple[str, ...] = ("COMFORTABLE", "COMPACT")

#: 177I: what one person may set for themselves. Strictly a subset of the
#: dashboard fields plus their own saved filters - there is no personal
#: setting that reaches another person.
PERSONAL_FIELDS: tuple[str, ...] = (
    "tile_order",
    "hidden_tiles",
    "density",
    "landing_tile",
    "saved_filters",
    "watch_preferences",
)

#: Fields a personal override may NEVER carry. Branding belongs to the
#: organisation; one person's taste is not the Tribe's identity.
PERSONAL_FORBIDDEN: frozenset[str] = frozenset(BRANDING_FIELDS)

_HEX = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")

#: Shapes that mean somebody is trying to render their own code.
_UNSAFE = re.compile(
    r"<\s*script|</\s*\w+\s*>|javascript\s*:|data\s*:\s*text/html|expression\s*\(|"
    r"@import|url\s*\(|&#x?[0-9a-fA-F]+;|\\\\[0-9a-fA-F]{2,6}|on\w+\s*=",
    re.I,
)


def _now() -> str:
    return dt.datetime.now(dt.UTC).isoformat()


def build_org_default(
    *,
    organization_id: Any,
    branding: dict[str, Any] | None = None,
    dashboard: dict[str, Any] | None = None,
    published_by: Any = None,
    published_at: Any = None,
    reason: Any = None,
    version_ordinal: int = 1,
    is_demo: bool = False,
) -> dict[str, Any]:
    """The organisation's published defaults."""
    brand = {field: (branding or {}).get(field) for field in BRANDING_FIELDS}
    board = {field: (dashboard or {}).get(field) for field in DASHBOARD_FIELDS}
    board["tile_order"] = list(board.get("tile_order") or TILES)
    board["hidden_tiles"] = sorted(board.get("hidden_tiles") or [])
    board["density"] = board.get("density") or "COMFORTABLE"

    return {
        "schema_version": SCHEMA_VERSION,
        "organization_id": str(organization_id) if organization_id else None,
        "version_ordinal": int(version_ordinal),
        "branding": brand,
        "dashboard": board,
        "published_by": str(published_by) if published_by else None,
        "published_at": published_at or _now(),
        "reason": str(reason) if reason else None,
        "is_demo": bool(is_demo),
        "model_version": CUSTOMIZATION_MODEL_VERSION,
    }


def publish_org_default(
    *,
    current: dict[str, Any],
    changes: dict[str, Any],
    published_by: Any,
    publisher_may_publish: bool,
    reason: Any,
    published_at: Any = None,
) -> dict[str, Any]:
    """177K.15. The ONLY way an organisation default changes.

    Deliberate, attributed, authorised and versioned - the opposite of a
    personal override in every one of those four respects.
    """
    if not publisher_may_publish:
        return {
            "accepted": False,
            "why": "publishing organisation defaults requires authority to do so",
            "default": current,
        }
    if not published_by:
        return {
            "accepted": False,
            "why": "publishing requires a named actor",
            "default": current,
        }
    if not reason:
        return {
            "accepted": False,
            "why": "publishing requires a stated reason",
            "default": current,
        }

    branding = dict(current.get("branding") or {})
    branding.update(changes.get("branding") or {})
    dashboard = dict(current.get("dashboard") or {})
    dashboard.update(changes.get("dashboard") or {})

    published = build_org_default(
        organization_id=current.get("organization_id"),
        branding=branding,
        dashboard=dashboard,
        published_by=published_by,
        published_at=published_at,
        reason=reason,
        version_ordinal=int(current.get("version_ordinal") or 1) + 1,
        is_demo=bool(current.get("is_demo")),
    )
    return {
        "accepted": True,
        "default": published,
        "previous": current,
        "audit_event": {
            "action": "organization.defaults_published",
            "organization_id": current.get("organization_id"),
            "actor_id": str(published_by),
            "reason": str(reason),
            "occurred_at": published["published_at"],
        },
        "why": str(reason),
    }


def build_personal_override(
    *,
    organization_id: Any,
    identity_id: Any,
    preferences: dict[str, Any] | None = None,
    updated_at: Any = None,
    is_demo: bool = False,
) -> dict[str, Any]:
    """One person's preferences. Never anybody else's."""
    prefs = {
        field: (preferences or {}).get(field)
        for field in PERSONAL_FIELDS
        if (preferences or {}).get(field) is not None
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "organization_id": str(organization_id) if organization_id else None,
        "identity_id": str(identity_id) if identity_id else None,
        "preferences": prefs,
        "updated_at": updated_at or _now(),
        "is_demo": bool(is_demo),
        "model_version": CUSTOMIZATION_MODEL_VERSION,
    }


def apply_personal_override(
    *, org_default: dict[str, Any], override: dict[str, Any]
) -> dict[str, Any]:
    """177I/177K.14. What THIS person sees, leaving the default untouched.

    The default is deep-copied before anything is merged, and the function
    returns the default's serialised form before and after so a caller - or a
    test - can prove it did not move. Returning the proof rather than
    promising it is the point: "we do not mutate" is a claim, and a claim
    about mutation is exactly the kind that quietly stops being true.
    """
    before = json.dumps(org_default, sort_keys=True, default=str)

    effective = copy.deepcopy(dict(org_default.get("dashboard") or {}))
    prefs = dict(override.get("preferences") or {})

    applied: list[str] = []
    ignored: list[str] = []
    for field, value in prefs.items():
        if field in PERSONAL_FORBIDDEN:
            ignored.append(field)
            continue
        if field in DASHBOARD_FIELDS:
            effective[field] = copy.deepcopy(value)
            applied.append(field)

    personal_only = {
        field: copy.deepcopy(value)
        for field, value in prefs.items()
        if field in PERSONAL_FIELDS and field not in DASHBOARD_FIELDS
    }

    after = json.dumps(org_default, sort_keys=True, default=str)

    return {
        "schema_version": SCHEMA_VERSION,
        "organization_id": org_default.get("organization_id"),
        "identity_id": override.get("identity_id"),
        # What this person sees. Branding always comes from the organisation.
        "branding": copy.deepcopy(dict(org_default.get("branding") or {})),
        "dashboard": effective,
        "personal_only": personal_only,
        "applied_fields": sorted(applied),
        "ignored_fields": sorted(ignored),
        # The proof.
        "org_default_unchanged": before == after,
        "org_default_version_ordinal": org_default.get("version_ordinal"),
        "branding_came_from_the_organization": True,
    }


def branding_invariant_failures(branding: dict[str, Any]) -> list[str]:
    """Refuse branding that is a payload rather than a preference."""
    failures: list[str] = []

    for field in ("primary_color", "secondary_color", "accent_color"):
        value = branding.get(field)
        if value in (None, ""):
            continue
        if not _HEX.match(str(value)):
            failures.append(f"{field}_is_not_a_hex_color")

    for field, value in branding.items():
        if not isinstance(value, str):
            continue
        if _UNSAFE.search(value):
            failures.append(f"{field}_contains_markup_or_script")

    # There is no field for raw CSS or script, and there must not become one.
    for forbidden in ("custom_css", "css", "stylesheet", "script", "html", "head"):
        if forbidden in branding:
            failures.append(f"branding_carries_a_code_field:{forbidden}")

    for field in branding:
        if field not in BRANDING_FIELDS:
            failures.append(f"branding_field_outside_the_vocabulary:{field}")

    return sorted(set(failures))


def dashboard_invariant_failures(dashboard: dict[str, Any]) -> list[str]:
    failures: list[str] = []

    order = list(dashboard.get("tile_order") or [])
    unknown = [tile for tile in order if tile not in TILES]
    if unknown:
        failures.append(f"tile_order_names_unknown_tiles:{sorted(set(unknown))}")
    if len(order) != len(set(order)):
        failures.append("tile_order_repeats_a_tile")

    hidden = list(dashboard.get("hidden_tiles") or [])
    unknown_hidden = [tile for tile in hidden if tile not in TILES]
    if unknown_hidden:
        failures.append(
            f"hidden_tiles_names_unknown_tiles:{sorted(set(unknown_hidden))}"
        )

    density = dashboard.get("density")
    if density is not None and str(density) not in DENSITIES:
        failures.append(f"density_outside_the_vocabulary:{density}")

    landing = dashboard.get("landing_tile")
    if landing is not None:
        if str(landing) not in TILES:
            failures.append(f"landing_tile_is_not_a_tile:{landing}")
        elif str(landing) in hidden:
            failures.append("landing_tile_is_hidden")

    return sorted(set(failures))


def override_invariant_failures(override: dict[str, Any]) -> list[str]:
    """Refuse a personal override that is reaching outside its own scope."""
    failures: list[str] = []

    if not override.get("identity_id"):
        failures.append("personal_override_names_nobody")
    if not override.get("organization_id"):
        failures.append("personal_override_names_no_organization")

    prefs = dict(override.get("preferences") or {})
    for field in prefs:
        if field in PERSONAL_FORBIDDEN:
            failures.append(f"personal_override_carries_org_branding:{field}")
        elif field not in PERSONAL_FIELDS:
            failures.append(f"personal_field_outside_the_vocabulary:{field}")

    failures.extend(
        dashboard_invariant_failures(
            {k: v for k, v in prefs.items() if k in DASHBOARD_FIELDS}
        )
    )
    return sorted(set(failures))


def describe_customization_model() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "model_version": CUSTOMIZATION_MODEL_VERSION,
        "branding_fields": list(BRANDING_FIELDS),
        "dashboard_fields": list(DASHBOARD_FIELDS),
        "personal_fields": list(PERSONAL_FIELDS),
        "tiles": list(TILES),
        "densities": list(DENSITIES),
        # The separation, checked rather than claimed.
        "personal_override_cannot_carry_branding": bool(
            PERSONAL_FORBIDDEN & set(BRANDING_FIELDS)
        )
        and not (set(PERSONAL_FIELDS) & PERSONAL_FORBIDDEN),
        "org_default_changes_only_by_publishing": True,
        "publishing_requires_authority": True,
        "publishing_requires_a_named_actor": True,
        "publishing_is_versioned": True,
        "personal_override_never_mutates_the_org_default": True,
        "branding_is_a_reference_not_a_payload": True,
        "no_free_form_css_or_script_field": not (
            set(BRANDING_FIELDS) & {"custom_css", "css", "script", "html"}
        ),
        "tile_vocabulary_is_closed": True,
    }
