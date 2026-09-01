"""Gate 132: one answer to "is this organization a demo organization".

## The disagreement this resolves

Three places claimed to know, and they did not agree.

```text
organizations.org_type          'demo' for bbbbbbbb-...
NF_DEMO_ORG_IDS                 unset, so demo_org_uuid_set() is empty
demo_isolation.org_type_for()   'real' for that same organization
nf_org_memberships.is_demo      whatever the caller passed
```

`org_type_for()` classifies by settings allowlist alone, so with the allowlist
empty **every organization is real** - including the row whose own `org_type`
column says `demo`. Measured, not inferred.

That is not cosmetic. Every tenant table carries the RLS predicate

```sql
organization_id = current_setting('app.current_org_id')::uuid
AND is_demo = current_setting('app.current_org_is_demo')::boolean
```

so a demo organization classified `real` puts demo rows in the real partition,
where a real-org session would read them.

## The authority

**The `organizations` row.** It is the only one of the three that is a fact
about the organization rather than a statement about the deployment: the
allowlist is configuration a deployment may not have set, and
`nf_org_memberships.is_demo` is whatever a caller wrote.

So `is_demo` is derived from `organizations.org_type` and from nothing else. A
caller cannot pass it. `classify_organization` has no `is_demo` parameter, which
is the point: a value that cannot be supplied cannot be supplied wrongly.

## The allowlist is not ignored

It is compared. When settings and the database disagree the classification is
**refused** rather than silently preferring one - a deployment that has listed
its demo orgs and a database that disagrees is a misconfiguration somebody needs
to see, not a tie for this module to break.

An empty allowlist is not a disagreement. It is a deployment that has not
configured one, which is the state this repository is in, and the database
answers alone.
"""

from __future__ import annotations

import json
import uuid
from typing import Any

SCHEMA_VERSION = "nf_demo_org_classification_v1"

#: What `organizations.org_type` may say.
ORG_TYPES: frozenset[str] = frozenset({"demo", "real"})

RESULT_FIELDS: tuple[str, ...] = (
    "schema_version",
    "organization_id",
    "organization_found",
    "org_type_in_database",
    "org_type_from_settings",
    "settings_allowlist_configured",
    "sources_agree",
    "is_demo",
    "classification_available",
    "blocked_reasons",
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _as_uuid(value: Any) -> uuid.UUID | None:
    try:
        return uuid.UUID(str(value))
    except (ValueError, AttributeError, TypeError):
        return None


def classify_organization(
    organization_id: Any,
    *,
    connection: Any = None,
    demo_org_ids: frozenset[uuid.UUID] | None = None,
    org_type_in_database: str | None = None,
) -> dict[str, Any]:
    """Is this organization a demo organization? The row decides.

    ``org_type_in_database`` is injectable so every branch is reachable without
    a database. It is not a way for a caller to assert the answer: when a
    connection is supplied the row wins, and the injected value is only used
    when there is no connection to ask.
    """
    from nativeforge.lib.settings import demo_org_uuid_set

    organization_uuid = _as_uuid(organization_id)
    blocked_reasons: list[str] = []

    if organization_uuid is None:
        blocked_reasons.append("organization_id_is_not_uuid_shaped")

    # -- the database, which is the authority --------------------------------
    db_type = ""
    found = False
    if connection is not None and organization_uuid is not None:
        try:
            import sqlalchemy as sa

            row = (
                connection.execute(
                    sa.text("SELECT org_type FROM organizations WHERE id = :oid"),
                    {"oid": organization_uuid.hex},
                )
                .mappings()
                .first()
            )
            if row is not None:
                found = True
                db_type = str(row["org_type"] or "").strip().lower()
        except Exception:
            blocked_reasons.append("organization_lookup_failed")
    elif org_type_in_database is not None:
        found = True
        db_type = str(org_type_in_database).strip().lower()
    else:
        blocked_reasons.append("no_connection_and_no_org_type_supplied")

    if found and db_type not in ORG_TYPES:
        blocked_reasons.append(f"org_type_outside_vocabulary:{db_type or 'empty'}")
    if connection is not None and not found and organization_uuid is not None:
        blocked_reasons.append("organization_not_found")

    # -- the allowlist, which is compared rather than trusted -----------------
    allowlist = demo_org_uuid_set() if demo_org_ids is None else demo_org_ids
    allowlist_configured = bool(allowlist)
    settings_type = ""
    if allowlist_configured and organization_uuid is not None:
        settings_type = "demo" if organization_uuid in allowlist else "real"

    # An unconfigured allowlist is not a disagreement; it is silence.
    sources_agree = True
    if allowlist_configured and found and db_type in ORG_TYPES:
        sources_agree = settings_type == db_type
        if not sources_agree:
            blocked_reasons.append(
                f"settings_says_{settings_type}_database_says_{db_type}"
            )

    classification_available = bool(
        found and db_type in ORG_TYPES and sources_agree and not blocked_reasons
    )
    # Derived from the row. There is no caller-supplied path to this value.
    is_demo = bool(classification_available and db_type == "demo")

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "organization_id": str(organization_uuid) if organization_uuid else "",
            "organization_found": found,
            "org_type_in_database": db_type,
            "org_type_from_settings": settings_type,
            "settings_allowlist_configured": allowlist_configured,
            "sources_agree": sources_agree,
            "is_demo": is_demo,
            "classification_available": classification_available,
            "blocked_reasons": sorted(set(blocked_reasons)),
        }
    )


def classification_invariant_failures(result: dict[str, Any]) -> list[str]:
    fails: list[str] = []

    # The whole point: is_demo may only be true when the row said demo.
    if result.get("is_demo") and result.get("org_type_in_database") != "demo":
        fails.append("is_demo_true_without_the_database_saying_demo")

    if result.get("is_demo") and not result.get("classification_available"):
        fails.append("is_demo_true_without_an_available_classification")

    if result.get("classification_available") and result.get("blocked_reasons"):
        fails.append("classification_available_alongside_blockers")

    if result.get("classification_available") and not result.get("sources_agree"):
        fails.append("classification_available_while_sources_disagree")

    if result.get("classification_available") and not result.get("organization_found"):
        fails.append("classification_available_for_an_organization_not_found")

    org_type = result.get("org_type_in_database")
    if org_type and org_type not in ORG_TYPES:
        fails.append("org_type_outside_vocabulary")

    return fails


def reconcile_demo_org_allowlist(
    connection: Any,
    *,
    demo_org_ids: frozenset[uuid.UUID] | None = None,
) -> dict[str, Any]:
    """Compare every organization row against the settings allowlist.

    The deployment-wide view of the question :func:`classify_organization`
    answers one organization at a time: does ``NF_DEMO_ORG_IDS`` say what the
    ``organizations`` table says?

    ``allowlist_that_would_agree`` is what the setting would have to hold for
    the two to match. It is reported, never applied - an allowlist that silently
    heals itself from the database is not a second source, and comparing a value
    against its own origin is vacuous.
    """
    import sqlalchemy as sa

    from nativeforge.lib.settings import demo_org_uuid_set

    allowlist = demo_org_uuid_set() if demo_org_ids is None else demo_org_ids

    rows = (
        connection.execute(
            sa.text("SELECT id, org_type FROM organizations ORDER BY id")
        )
        .mappings()
        .all()
    )

    organizations: list[dict[str, Any]] = []
    disagreements: list[str] = []
    should_be_listed: list[str] = []

    for row in rows:
        oid = _as_uuid(row["id"])
        db_type = str(row["org_type"] or "").strip().lower()
        listed = oid is not None and oid in allowlist
        settings_type = "demo" if listed else "real"
        agrees = (not allowlist) or settings_type == db_type
        organizations.append(
            {
                "organization_id": str(oid) if oid else str(row["id"]),
                "org_type_in_database": db_type,
                "listed_in_allowlist": listed,
                "org_type_from_settings": settings_type if allowlist else "",
                "sources_agree": agrees,
            }
        )
        if db_type == "demo" and oid is not None:
            should_be_listed.append(str(oid))
        if not agrees:
            disagreements.append(
                f"{oid}:settings_says_{settings_type}_database_says_{db_type}"
            )

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "organization_count": len(organizations),
            "organizations": organizations,
            "settings_allowlist_configured": bool(allowlist),
            "settings_allowlist": sorted(str(x) for x in allowlist),
            "allowlist_that_would_agree": sorted(should_be_listed),
            "allowlist_matches_database": (
                sorted(str(x) for x in allowlist) == sorted(should_be_listed)
            ),
            "disagreements": sorted(disagreements),
        }
    )
