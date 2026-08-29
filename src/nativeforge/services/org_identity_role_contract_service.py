"""Org identity role contract (Gate 110B).

What each identity name is for, and what it may never be used for.

## Five names, one authority

Gate 110A found five identity vocabularies and settled which one the database
actually enforces on:

```text
organization_id          UUID, 21 columns, 21 RLS policies    rls_authority
app.current_org_id       the session GUC those policies read  rls session context
org_id                   uuid.UUID in routes, free-form in
                         contract services                     service_alias
customer_org_id          6 services, 0 db columns              customer surface
tenant_id                20 services, 0 db columns             product label
```

Every RLS policy reads
`organization_id = current_setting('app.current_org_id', true)::uuid`. That is
not an interpretation; it is the text in the migrations.

## Shape is checked, not assumed

`classify_identity_value_shape` looks at a value and reports `uuid`,
`gate51_derived` or `free_form`. The `::uuid` cast in every policy means a
free-form value cannot satisfy an RLS check even by accident - the database
refuses it - so shape is the difference between an identifier that can carry
authority and one that cannot.

An `org_id` may act as an alias for `organization_id` **only where its value is
actually a UUID**. The name alone proves nothing: the same name is a free-form
string in most of the ~70 services that use it.

## tenant_id is never the authority

Not because it is untrusted, but because it is a different kind of thing. It
names a product lane, has no column, no repository, no route, and no service
authorizes on it. Making it an authority would give the database two answers to
"whose row is this", and two answers eventually disagree.

Demo identifiers are refused separately and explicitly. A demo tenant id in an
RLS path is the specific accident this contract exists to make impossible.
"""

from __future__ import annotations

import json
import re
from typing import Any

SCHEMA_VERSION = "nf_org_identity_role_contract_v1"

IDENTITY_NAMES = frozenset(
    {
        "organization_id",
        "org_id",
        "customer_org_id",
        "tenant_id",
        "current_org_id",
    }
)

IDENTITY_ROLES = frozenset(
    {
        "rls_authority",
        "rls_session_context",
        "db_foreign_key",
        "service_alias",
        "customer_surface_alias",
        "product_tenant_label",
        "derived_product_label",
        "demo_fixture_label",
        "unknown",
    }
)

AUTHORITY_LEVELS = frozenset(
    {"authority", "session_context", "alias_of_authority", "label", "none"}
)

IDENTITY_SHAPES = frozenset({"uuid", "gate51_derived", "free_form", "absent"})

# Only a UUID can satisfy the ::uuid cast every RLS policy performs.
RLS_CAPABLE_SHAPES = frozenset({"uuid"})

_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.IGNORECASE
)
_GATE51_RE = re.compile(r"^tn_[0-9a-f]{16}$")

# Prefixes that mark an identifier as demo data.
DEMO_VALUE_PREFIXES: tuple[str, ...] = ("nf-demo-", "demo-")

ROLE_FIELDS: tuple[str, ...] = (
    "identity_name",
    "role",
    "shape",
    "authority_level",
    "rls_allowed",
    "persistence_allowed",
    "product_surface_allowed",
    "demo_allowed",
    "derived_allowed",
    "requires_binding",
    "blocked_reasons",
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def classify_identity_value_shape(value: Any) -> str:
    """What kind of identifier is this? Read from the value, never the name."""
    text = str(value or "").strip()
    if not text:
        return "absent"
    if _UUID_RE.match(text):
        return "uuid"
    if _GATE51_RE.match(text):
        return "gate51_derived"
    return "free_form"


def is_demo_identity_value(value: Any) -> bool:
    text = str(value or "").strip().lower()
    return any(text.startswith(prefix) for prefix in DEMO_VALUE_PREFIXES)


def describe_identity_role(
    *, identity_name: Any, identity_value: Any = None
) -> dict[str, Any]:
    """The role this identity may play, given its name and its actual value."""
    name = str(identity_name or "").strip()
    if name not in IDENTITY_NAMES:
        name = "unknown"

    shape = classify_identity_value_shape(identity_value)
    is_demo = is_demo_identity_value(identity_value)

    blocked_reasons: list[str] = []

    # Roles are assigned from what the survey proved, not from the name's
    # resemblance to a concept.
    if name == "organization_id":
        role = "rls_authority"
        authority_level = "authority"
    elif name == "current_org_id":
        role = "rls_session_context"
        authority_level = "session_context"
    elif name == "org_id":
        # An alias only where the value really is the authority's shape.
        if shape in RLS_CAPABLE_SHAPES:
            role = "service_alias"
            authority_level = "alias_of_authority"
        else:
            role = "service_alias"
            authority_level = "label"
            blocked_reasons.append(f"org_id_value_is_not_a_uuid:{shape}")
    elif name == "customer_org_id":
        role = "customer_surface_alias"
        authority_level = "label"
    elif name == "tenant_id":
        if shape == "gate51_derived":
            role = "derived_product_label"
        elif is_demo:
            role = "demo_fixture_label"
        else:
            role = "product_tenant_label"
        authority_level = "label"
    else:
        role = "unknown"
        authority_level = "none"
        blocked_reasons.append("unrecognised_identity_name")

    if is_demo:
        blocked_reasons.append("demo_identity_value")
    if shape == "absent" and name != "unknown":
        blocked_reasons.append("identity_value_absent")

    # RLS permission is derived affirmatively: the name must be an authority or
    # its session context, the value must be UUID-shaped, and it must not be
    # demo data. Nothing is subtracted from a permissive default.
    rls_allowed = (
        name in {"organization_id", "current_org_id"}
        and shape in RLS_CAPABLE_SHAPES
        and not is_demo
    )
    if name in {"organization_id", "current_org_id"} and not rls_allowed:
        if shape not in RLS_CAPABLE_SHAPES:
            blocked_reasons.append(f"rls_requires_a_uuid_value:{shape}")

    # Persistence needs a value the RLS boundary can protect. An org_id alias
    # qualifies only when its value is the authority's shape.
    persistence_allowed = (
        name in {"organization_id", "org_id"}
        and shape in RLS_CAPABLE_SHAPES
        and not is_demo
    )

    # A label may name a product surface; it may not scope storage.
    product_surface_allowed = name in {
        "tenant_id",
        "customer_org_id",
        "org_id",
        "organization_id",
    }

    # A binding to organization_id is required before a label reaches storage.
    requires_binding = name in {"tenant_id", "customer_org_id"} or (
        name == "org_id" and shape not in RLS_CAPABLE_SHAPES
    )

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "identity_name": name,
            "identity_value": identity_value,
            "role": role,
            "shape": shape,
            "authority_level": authority_level,
            "rls_allowed": rls_allowed,
            "persistence_allowed": persistence_allowed,
            "product_surface_allowed": product_surface_allowed,
            "demo_allowed": bool(is_demo),
            "derived_allowed": role == "derived_product_label",
            "requires_binding": requires_binding,
            "blocked_reasons": sorted(set(blocked_reasons)),
            # Constants the whole contract holds.
            "tenant_id_is_rls_authority": False,
            "demo_tenant_ids_rls_allowed": False,
            "identities_assumed_equivalent": False,
            "migration_applied": False,
            "fabricated": False,
        }
    )


def build_identity_role_matrix(
    *, samples: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Every identity name, against a representative value for each."""
    samples = samples or {
        "organization_id": "11111111-2222-3333-4444-555555555555",
        "current_org_id": "11111111-2222-3333-4444-555555555555",
        "org_id": "11111111-2222-3333-4444-555555555555",
        "customer_org_id": "nf-demo-org-01",
        "tenant_id": "nf-demo-tenant-01",
    }

    rows = [
        describe_identity_role(identity_name=name, identity_value=samples.get(name))
        for name in sorted(IDENTITY_NAMES)
    ]

    authorities = [r for r in rows if r["role"] == "rls_authority"]

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "rows": rows,
            "row_count": len(rows),
            "rls_authority_names": sorted(r["identity_name"] for r in authorities),
            "organization_id_is_rls_authority": bool(authorities)
            and all(r["identity_name"] == "organization_id" for r in authorities),
            "names_allowing_rls": sorted(
                r["identity_name"] for r in rows if r["rls_allowed"]
            ),
            "names_allowing_persistence": sorted(
                r["identity_name"] for r in rows if r["persistence_allowed"]
            ),
            "names_requiring_binding": sorted(
                r["identity_name"] for r in rows if r["requires_binding"]
            ),
            "tenant_id_is_rls_authority": False,
            "demo_tenant_ids_rls_allowed": False,
            "migration_applied": False,
            "fabricated": False,
        }
    )


def identity_role_invariant_failures(row: dict[str, Any]) -> list[str]:
    fails: list[str] = []

    if row.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")

    for field in ROLE_FIELDS:
        if field not in row:
            fails.append(f"identity_role_missing_field:{field}")

    for constant in (
        "tenant_id_is_rls_authority",
        "demo_tenant_ids_rls_allowed",
        "identities_assumed_equivalent",
        "migration_applied",
        "fabricated",
    ):
        if row.get(constant) is not False:
            fails.append(f"identity_role_claimed:{constant}")

    if row.get("role") not in IDENTITY_ROLES:
        fails.append("identity_role_out_of_vocabulary")
    if row.get("shape") not in IDENTITY_SHAPES:
        fails.append("identity_shape_out_of_vocabulary")
    if row.get("authority_level") not in AUTHORITY_LEVELS:
        fails.append("authority_level_out_of_vocabulary")

    name = row.get("identity_name")

    # tenant_id is never the RLS authority, whatever its value looks like.
    if name == "tenant_id":
        if row.get("rls_allowed"):
            fails.append("tenant_id_permitted_rls")
        if row.get("persistence_allowed"):
            fails.append("tenant_id_permitted_persistence")
        if row.get("role") == "rls_authority":
            fails.append("tenant_id_assigned_the_authority_role")

    # customer_org_id is not automatically a foreign key.
    if name == "customer_org_id":
        if row.get("role") == "db_foreign_key":
            fails.append("customer_org_id_treated_as_a_foreign_key")
        if row.get("persistence_allowed"):
            fails.append("customer_org_id_permitted_persistence_without_a_binding")
        if not row.get("requires_binding"):
            fails.append("customer_org_id_did_not_require_a_binding")

    # A demo identity never reaches RLS or storage.
    if row.get("demo_allowed"):
        if row.get("rls_allowed"):
            fails.append("demo_identity_permitted_rls")
        if row.get("persistence_allowed"):
            fails.append("demo_identity_permitted_persistence")

    # Only a UUID-shaped value may carry RLS or persistence.
    if row.get("rls_allowed") and row.get("shape") not in RLS_CAPABLE_SHAPES:
        fails.append("rls_permitted_for_a_non_uuid_value")
    if row.get("persistence_allowed") and row.get("shape") not in RLS_CAPABLE_SHAPES:
        fails.append("persistence_permitted_for_a_non_uuid_value")

    # An org_id whose value is not a UUID is a label and must say so.
    if (
        name == "org_id"
        and row.get("shape") not in RLS_CAPABLE_SHAPES
        and row.get("authority_level") != "label"
    ):
        fails.append("non_uuid_org_id_claimed_alias_authority")

    # A refusal must name itself.
    if row.get("blocked_reasons") == [] and row.get("role") == "unknown":
        fails.append("unknown_identity_without_a_reason")

    return fails
