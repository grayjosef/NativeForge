"""Gate 177A: what does NativeForge already know about who may act for a Tribe?

Gate 177's permanent principle is that these are three different questions:

```text
IDENTITY VERIFIED     we know who this person is
AFFILIATION VERIFIED  we know they belong to this organisation
AUTHORITY VERIFIED    we know they may ACT for it
```

Collapsing them is not a modelling preference, it is the failure that lets
somebody with a tribe.gov email address create a tenant and invite people in
the name of a sovereign government. Verifying a mailbox proves control of a
mailbox.

So this survey adds a classification the earlier ones did not have:

```text
COLLAPSED  the structure is real and populated, and folds two or more of
           identity / affiliation / authority into ONE field, so the
           distinction cannot be expressed at all
```

It is DERIVED, not asserted: a table is collapsed when it carries a single
state/status column governing an authority concern while naming no separate
column for the other two dimensions.

Three questions decide Gate 177's shape:

```text
1. is authority already separated from identity and affiliation, or is
   there one boolean somewhere doing all three jobs?
2. does the REAL organisation have any authorised administrator today?
3. is there a controlling-company boundary, or can an org admin grant
   itself controlling-company powers?
```

No network. No writes.
"""

from __future__ import annotations

import json
import pathlib
import re
import socket
import sqlite3
import sys

sys.path.insert(0, "src")
sys.path.insert(0, ".")

_NETWORK = {"attempts": 0}


class _Refused(socket.socket):
    def __init__(self, *a, **k):  # noqa: ANN002, ANN003
        _NETWORK["attempts"] += 1
        raise OSError("gate177 survey makes no network request")


socket.socket = _Refused  # type: ignore[misc,assignment]

REPO = pathlib.Path(__file__).resolve().parents[1]
SERVICES = REPO / "src" / "nativeforge" / "services"
PACKAGE = REPO / "src" / "nativeforge"
DB = REPO / "nativeforge.local.db"

#: The organisations named in the campaign brief. The real one is NO-TOUCH.
REAL_ORG = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
DEMO_ORG = "bbbbbbbb-cccc-dddd-eeee-ffffffffffff"


def _norm(value: str) -> str:
    return value.replace("-", "").lower()


#: Tables that carry any part of the authority question.
TABLES = (
    "organizations",
    "nf_org_memberships",
    "nf_membership_invites",
    "nf_authority_proof_records",
    "nf_tenant_customer_org_bindings",
    "nf_tribal_profiles",
    "nf_organization_capability_profiles",
    "nf_tenant_beta_profiles",
    "nf_audit_events",
)

#: Column names that speak to each dimension. A table naming columns from only
#: one family, while governing an authority concern, has collapsed the others.
IDENTITY_COLUMNS = ("identity_id", "identity_status", "subject_fingerprint")
AFFILIATION_COLUMNS = (
    "affiliation_status",
    "membership_source",
    "invited_email_domain",
)
AUTHORITY_COLUMNS = (
    "authority_status",
    "proof_types",
    "verified_by",
    "approved_by",
    "role_source",
)

#: A single column that governs whether somebody may act.
COLLAPSING_COLUMNS = ("state", "status", "binding_status", "approval_state")

#: Modules named individually. Gate 173 learned that a name prefix lies: a
#: `native_relevance_` marker matched modules importing the OLD unwired stack.
AUTHORITY_MODULES = (
    "authority_claim_resolver_service",
    "authority_proof_workflow_service",
    "authority_source_registry_service",
    "authority_verification_service",
    "applicant_authority_assembler_service",
    "applicant_authority_contract_service",
)
MEMBERSHIP_MODULES = (
    "customer_org_membership_verification_service",
    "dev_org_membership_bootstrap_service",
    "identity_org_session_resolution_service",
    "customer_auth_role_mapping_service",
    "customer_auth_role_mapping_evidence_service",
    "customer_auth_org_context_dependency_service",
)
INVITE_MODULES = (
    "invite_activation_artifact_gate136_service",
    "controlled_pilot_invite_design_service",
)
TENANT_MODULES = (
    "tenant_customer_org_identity_binding_service",
    "tenant_customer_org_resolution_guard_service",
    "demo_org_classification_service",
    "dev_org_header_containment_service",
    "dev_org_header_shutdown_readiness_service",
)
PROFILE_MODULES = (
    "tenant_profile_repository_service",
    "tribal_profile_service",
    "organization_capability_profile_service",
)
AUDIT_MODULES = (
    "unified_audit_event_service",
    "audit_event_collector_service",
    "evidence_audit_lifecycle_service",
)

ALL_MODULES = (
    AUTHORITY_MODULES
    + MEMBERSHIP_MODULES
    + INVITE_MODULES
    + TENANT_MODULES
    + PROFILE_MODULES
    + AUDIT_MODULES
)

#: 177E's organisation profile fields, checked against what is storable today.
PROFILE_FIELDS = (
    "legal_name",
    "display_name",
    "entity_type",
    "address",
    "service_geography",
    "primary_contact",
    "funding_sectors",
    "strategic_priorities",
    "populations_served",
    "applicant_capabilities",
    "matching_capability",
    "certifications",
)

#: 177H/177I. Branding and layout, org default versus personal override.
CUSTOMIZATION_FIELDS = (
    "logo",
    "brand_color",
    "dashboard_layout",
    "tile_order",
    "tile_visibility",
    "saved_filters",
)

SOURCES = {
    path.stem: path.read_text(encoding="utf-8") for path in SERVICES.glob("*.py")
}
PACKAGE_SOURCES = {
    str(path.relative_to(PACKAGE)): path.read_text(encoding="utf-8")
    for path in PACKAGE.rglob("*.py")
}


def _importers(module: str) -> int:
    marker = f"import {module}"
    alt = f"from nativeforge.services.{module} import"
    return sum(
        1
        for name, body in PACKAGE_SOURCES.items()
        if (marker in body or alt in body) and not name.endswith(f"{module}.py")
    )


def table_facts(conn: sqlite3.Connection, table: str) -> dict[str, object]:
    cols = [row[1] for row in conn.execute(f"PRAGMA table_info({table})")]
    if not cols:
        return {"exists": False}
    rows = conn.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
    demo = None
    if "is_demo" in cols:
        demo = conn.execute(
            f"SELECT count(*) FROM {table} WHERE is_demo = 1"
        ).fetchone()[0]

    real_org_rows = None
    if "organization_id" in cols:
        real_org_rows = conn.execute(
            f"SELECT count(*) FROM {table} "
            "WHERE replace(lower(organization_id),'-','') = ?",
            (_norm(REAL_ORG),),
        ).fetchone()[0]

    identity = [c for c in cols if c in IDENTITY_COLUMNS]
    affiliation = [c for c in cols if c in AFFILIATION_COLUMNS]
    authority = [c for c in cols if c in AUTHORITY_COLUMNS]
    collapsing = [c for c in cols if c in COLLAPSING_COLUMNS]

    return {
        "exists": True,
        "rows": rows,
        "demo_rows": demo,
        "real_rows": rows if demo is None else rows - demo,
        "rows_on_the_real_organization": real_org_rows,
        "columns": len(cols),
        "identity_columns": identity,
        "affiliation_columns": affiliation,
        "authority_columns": authority,
        "single_state_columns": collapsing,
        "dimensions_named": sum(
            1 for group in (identity, affiliation, authority) if group
        ),
    }


def classify_table(table: str, facts: dict[str, object]) -> tuple[str, str]:
    if not facts.get("exists"):
        return "UNKNOWN", "not_found_in_the_database"

    rows = int(facts.get("rows") or 0)
    dimensions = int(facts.get("dimensions_named") or 0)
    collapsing = list(facts.get("single_state_columns") or [])
    authority = list(facts.get("authority_columns") or [])

    # The Gate 177 classification. A table that governs authority through one
    # state column, while naming fewer than all three dimensions, cannot
    # express the distinction this gate exists to preserve.
    if authority and collapsing and dimensions < 3:
        return (
            "COLLAPSED",
            f"governs_authority_through_{collapsing}_naming_only_{dimensions}_of_3",
        )

    if rows == 0:
        return "READY_UNPOPULATED", f"schema_exists_with_{facts['columns']}_columns"
    return "POPULATED", f"{rows}_rows"


def main() -> int:
    out: dict[str, object] = {"schema_version": "nf_gate177_survey_v1"}

    if not DB.exists():
        print(json.dumps({"blocker": "no_local_database"}))
        return 1

    conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    try:
        tables = {t: table_facts(conn, t) for t in TABLES}
        for name, facts in tables.items():
            kind, why = classify_table(name, facts)
            facts["classification"] = kind
            facts["why"] = why

        # ---- question 1: is authority separated? --------------------
        proof = tables["nf_authority_proof_records"]
        out["authority_table_exists"] = bool(proof.get("exists"))
        out["authority_dimensions_named"] = proof.get("dimensions_named")
        out["identity_affiliation_authority_separated"] = bool(
            proof.get("dimensions_named") == 3
        )
        out["collapsed_structures"] = sorted(
            name
            for name, facts in tables.items()
            if facts["classification"] == "COLLAPSED"
        )

        # ---- question 2: does the REAL org have an admin? ------------
        real_members = conn.execute(
            "SELECT count(*) FROM nf_org_memberships "
            "WHERE replace(lower(organization_id),'-','') = ? AND state = 'active'",
            (_norm(REAL_ORG),),
        ).fetchone()[0]
        real_authority = conn.execute(
            "SELECT count(*) FROM nf_authority_proof_records "
            "WHERE replace(lower(organization_id),'-','') = ?",
            (_norm(REAL_ORG),),
        ).fetchone()[0]
        demo_members = conn.execute(
            "SELECT count(*) FROM nf_org_memberships "
            "WHERE replace(lower(organization_id),'-','') = ? AND state = 'active'",
            (_norm(DEMO_ORG),),
        ).fetchone()[0]

        out["real_organization_active_members"] = real_members
        out["real_organization_authority_records"] = real_authority
        out["demo_organization_active_members"] = demo_members
        out["real_organization_has_an_authorized_admin"] = bool(real_authority)
        out["adversarial_case_11_is_the_current_real_state"] = real_authority == 0

        # ---- roles in use, and whether the boundary exists -----------
        roles = [
            {"role": row[0], "source": row[1], "count": row[2]}
            for row in conn.execute(
                "SELECT role, role_source, count(*) FROM nf_org_memberships "
                "GROUP BY role, role_source ORDER BY 3 DESC"
            )
        ]
        out["roles_in_use"] = roles
        out["distinct_roles_in_use"] = len({r["role"] for r in roles})

        # ---- audit coverage ------------------------------------------
        actions = [
            {"action": row[0], "count": row[1]}
            for row in conn.execute(
                "SELECT action, count(*) FROM nf_audit_events "
                "GROUP BY action ORDER BY 2 DESC LIMIT 15"
            )
        ]
        out["audit_actions"] = actions
        out["audit_event_rows"] = int(tables["nf_audit_events"].get("rows") or 0)
        out["audit_actions_naming_authority"] = sorted(
            a["action"]
            for a in actions
            if re.search(r"authority|verif|approve|invit|role", str(a["action"]), re.I)
        )

        out["tables"] = tables
    finally:
        conn.close()

    # ---- the code surface -------------------------------------------
    modules: dict[str, object] = {}
    for name in ALL_MODULES:
        body = SOURCES.get(name)
        if body is None:
            modules[name] = {"exists": False, "classification": "UNKNOWN"}
            continue
        importers = _importers(name)
        modules[name] = {
            "exists": True,
            "imported_by": importers,
            "db_wired": bool(re.search(r"SessionLocal|sa\.text|sqlalchemy", body)),
            "lines": body.count("\n") + 1,
            "classification": "UNWIRED" if importers == 0 else "WIRED",
        }
    out["modules"] = modules
    out["module_count"] = len(modules)
    out["unwired_modules"] = sorted(
        name
        for name, facts in modules.items()
        if facts.get("classification") == "UNWIRED"
    )

    # ---- question 3: the controlling-company boundary ---------------
    whole = "\n".join(PACKAGE_SOURCES.values())
    out["controlling_company_phrase_present"] = bool(
        re.search(r"controlling[_ ]company", whole, re.I)
    )
    out["org_super_admin_phrase_present"] = bool(
        re.search(r"ORG_SUPER_ADMIN|org_super_admin", whole)
    )
    out["controlling_company_boundary_exists"] = bool(
        out["controlling_company_phrase_present"]
    )

    # ---- 177E / 177H / 177I: what is storable today -----------------
    profile_present = {}
    for field in PROFILE_FIELDS:
        profile_present[field] = bool(
            re.search(rf"\b{re.escape(field)}\b", whole, re.I)
        )
    out["profile_fields_present"] = profile_present
    out["profile_fields_missing"] = sorted(
        f for f, present in profile_present.items() if not present
    )

    customization = {}
    for field in CUSTOMIZATION_FIELDS:
        customization[field] = bool(re.search(rf"\b{re.escape(field)}\b", whole, re.I))
    out["customization_fields_present"] = customization
    out["customization_fields_missing"] = sorted(
        f for f, present in customization.items() if not present
    )
    out["org_default_versus_personal_override_exists"] = bool(
        re.search(r"org_default|organization_default", whole, re.I)
        and re.search(r"personal_override|user_override", whole, re.I)
    )

    # ---- header-based dev auth --------------------------------------
    out["dev_org_header_still_present"] = bool(
        re.search(r"X-NF-Org|x_nf_org|dev_org_header", whole, re.I)
    )

    out["network_requests"] = _NETWORK["attempts"]
    out["wrote_nothing"] = True

    # ---- what this survey concludes ---------------------------------
    out["gate177_must_build"] = sorted(
        item
        for item, needed in {
            "three_independent_states": not out[
                "identity_affiliation_authority_separated"
            ],
            "authority_evidence_records": int(proof.get("rows") or 0) == 0,
            "controlling_company_boundary": not out[
                "controlling_company_boundary_exists"
            ],
            "organization_profile_fields": bool(out["profile_fields_missing"]),
            "branding_and_dashboard_defaults": bool(
                out["customization_fields_missing"]
            ),
            "org_default_versus_personal_override": not out[
                "org_default_versus_personal_override_exists"
            ],
        }.items()
        if needed
    )

    print(json.dumps(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
