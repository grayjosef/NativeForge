"""Customer persistence capabilities (Gate 114B).

Eight persistence lanes, and four separate questions asked of each: does a table
exist, is it under row-level security, can anything write to it, and may anything
actually be written today. The answers differ per lane and the four are never
collapsed into one word.

## Why the questions are separate

Gate 114A found the same fact stated three different ways across three readiness
surfaces:

```text
awarded lane   customer_persistence_live = _module_importable(
                   "nativeforge.repositories.awarded_grant")
digest lane    customer_persistence = False        hard-coded
beta lane      customer_persistence_live = False   hard-coded
```

All three report `False` and all three are currently correct, for three
unrelated reasons. Two are constants of the kind Gate 113 removed from
`migration_applied` — they would still say `False` after persistence became
real. The third is worse: it moves in the *unsafe* direction, because creating
an empty `repositories/awarded_grant.py` would flip a lane to
"persistence live" with no table, no policy, no organization anchor, and nobody
able to authenticate.

This service is the one place that answers the question, and it answers it by
reading the schema, the migrations and the repositories directory.

## Schema available is not operational

A table is a container. Reaching `operational` requires every one of:

```text
schema_available                  a table is declared
organization_id_anchor_available  it carries the column RLS enforces on
rls_backed                        a migration installs a policy on it
repository_available              something can address it
service_contract_available        something decides what may go in it
write_path_available              derived from the four above
customer_auth_live                somebody can be accountable for the row
```

Seven conjuncts, and today the last one is false for every lane, so every lane
is non-operational regardless of how much schema it has. That is the correct
answer and it is derived, not declared.

## Detection roots are injectable

`models_path`, `versions_dir` and `repositories_dir` are parameters so a test can
point them at an empty directory and observe the negative branch. Without that,
`schema_available: False` would be unreachable for the lanes that have a table,
and an unreachable branch is an untested one.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

# Bridged from Gate 113's binding store, never restated. `RLS_ANCHOR_COLUMN` is
# the column every RLS policy in this repository enforces on - Gate 114A
# verified all nineteen install the identical predicate - and
# `FORBIDDEN_ANCHOR_NAMES` are the labels that may never anchor anything. A
# capability that could only be keyed on one of those is not a capability, and a
# second copy of these two names is how the two layers would come to disagree.
from nativeforge.services.tenant_customer_org_binding_store_service import (
    FORBIDDEN_ANCHOR_NAMES,
    RLS_ANCHOR_COLUMN,
)

SCHEMA_VERSION = "nf_customer_persistence_capability_v1"

CAPABILITIES: tuple[str, ...] = (
    "tenant_profile_persistence",
    "awarded_grants_persistence",
    "award_requirements_persistence",
    "proof_audit_persistence",
    "tenant_digest_persistence",
    "document_library_persistence",
    "source_watchlist_persistence",
    "identity_binding_persistence",
    "beta_onboarding_persistence",
)

# What each lane would be backed by. A table named here does not imply it
# exists - existence is read off the schema, and six of these eight are absent.
CAPABILITY_TABLES: dict[str, str] = {
    "tenant_profile_persistence": "nf_tribal_profiles",
    "awarded_grants_persistence": "nf_awarded_grants",
    "award_requirements_persistence": "nf_award_requirements",
    "proof_audit_persistence": "nf_award_requirement_proof_events",
    "tenant_digest_persistence": "nf_tenant_digest_records",
    "document_library_persistence": "nf_document_library_items",
    "source_watchlist_persistence": "nf_source_watchlist_entries",
    "identity_binding_persistence": "nf_tenant_customer_org_bindings",
    "beta_onboarding_persistence": "nf_beta_onboarding_records",
}

# A repository that lives in `services/` rather than `repositories/`, detected
# by import. Gate 120B built the identity binding repository as a service, in
# the shape the other binding contracts use, and the file probe below would not
# have seen it.
#
# The probe measures a *filename convention*. That is the declared-versus-derived
# defect this campaign keeps finding: what matters is whether anything can
# address the table, not where it happens to live. This map is the derived
# answer for the lanes that have one; the rest fall through to the probe and
# stay false, because they are still false.
CAPABILITY_REPOSITORY_MODULES: dict[str, str] = {
    "identity_binding_persistence": (
        "nativeforge.services.tenant_customer_org_binding_repository_service"
    ),
    # Gate 124C. Built as a service, like Gate 120's, so the filename probe
    # below cannot see it either.
    "awarded_grants_persistence": (
        "nativeforge.services.awarded_grants_repository_service"
    ),
    # Gate 125C, the other half of awarded tracking.
    "award_requirements_persistence": (
        "nativeforge.services.award_requirements_repository_service"
    ),
    # Gate 126C, the last post-award lane. This map is now the single place a
    # repository module is named - Gate 125 also named one inside the readiness
    # service and the two disagreed, which is the defect Gate 126A found.
    "proof_audit_persistence": (
        "nativeforge.services.award_requirement_proof_audit_repository_service"
    ),
}

# Gate 123: the *behaviour* profile, which is a different object from the
# grant-application identity profile the tenant_profile lane already tracks.
#
# `nf_tribal_profiles`      who this Tribe is when a form is submitted
# `nf_tenant_beta_profiles` how this tenant wants NativeForge to behave
#
# Gate 123A found the two share not one column. Reported as its own fact rather
# than folded into the tenant_profile lane, because a lane that counted two
# unrelated repositories as one would report a write path for a table that has
# none.
TENANT_BETA_PROFILE_REPOSITORY_MODULE = (
    "nativeforge.services.tenant_profile_repository_service"
)
TENANT_BETA_PROFILE_TABLE = "nf_tenant_beta_profiles"

# The repository module that would address each lane's table.
CAPABILITY_REPOSITORIES: dict[str, str] = {
    "tenant_profile_persistence": "tribal_profiles",
    "awarded_grants_persistence": "awarded_grants",
    "award_requirements_persistence": "award_requirements",
    "proof_audit_persistence": "award_requirement_proof_events",
    "tenant_digest_persistence": "tenant_digest",
    "document_library_persistence": "document_library",
    "source_watchlist_persistence": "source_watchlist",
    "identity_binding_persistence": "identity_binding",
    "beta_onboarding_persistence": "beta_onboarding",
}

# The service that decides what may enter each lane. Detected by import, and
# several of these genuinely exist while their tables do not - a contract
# without a store, which is the state most of this campaign has been building.
#
# Gate 124A found two of these named a module that does not exist, one token
# away from one that does:
#
#     awarded_grant_record_contract_service -> awarded_grant_record_service
#     award_requirements_model_service      -> award_requirement_model_service
#
# Both lanes reported `no_service_decides_what_may_be_written` while a 432-line
# and a 494-line service decided exactly that. Same family as Gate 120's
# filename probe and Gate 122's provider miscount: a detector reporting on a
# *name* rather than a capability. A test now asserts every module in this map
# imports, so a third typo cannot hide as a false negative.
#
# The remaining three absences are real and stay false.
CAPABILITY_CONTRACT_MODULES: dict[str, str] = {
    "tenant_profile_persistence": "nativeforge.services.tribal_profile_service",
    "awarded_grants_persistence": "nativeforge.services.awarded_grant_record_service",
    "award_requirements_persistence": (
        "nativeforge.services.award_requirement_model_service"
    ),
    "proof_audit_persistence": (
        "nativeforge.services.award_requirement_proof_audit_service"
    ),
    "tenant_digest_persistence": (
        "nativeforge.services.tenant_nofo_digest_builder_service"
    ),
    "document_library_persistence": (
        "nativeforge.services.award_document_store_service"
    ),
    "source_watchlist_persistence": (
        "nativeforge.services.tenant_source_watchlist_service"
    ),
    "identity_binding_persistence": (
        "nativeforge.services.tenant_customer_org_binding_store_service"
    ),
    "beta_onboarding_persistence": (
        "nativeforge.services.tenant_beta_onboarding_service"
    ),
}

# Every lane writes customer data, so every lane requires customer auth. Stated
# as a mapping rather than a constant so a lane that genuinely did not would
# have somewhere to say so - and so that a reader can see none currently does.
CAPABILITY_REQUIRES_AUTH: dict[str, bool] = dict.fromkeys(CAPABILITIES, True)

CAPABILITY_FIELDS: tuple[str, ...] = (
    "capability",
    "schema_available",
    "repository_available",
    "service_contract_available",
    "rls_backed",
    "organization_id_anchor_available",
    "write_path_available",
    "read_path_available",
    "customer_auth_required",
    "customer_auth_live",
    "operational",
    "demo_only",
    "blocked_reasons",
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _module_importable(name: str) -> bool:
    import importlib.util

    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ValueError):
        return False


def detect_schema_facts(
    *, models_path: Path | None = None, versions_dir: Path | None = None
) -> dict[str, dict[str, bool]]:
    """Which tables exist, carry the anchor, and have an RLS policy.

    Read off the ORM models and the migrations directory. A table declared in a
    migration but absent from the models is still a table - the binding store is
    exactly that - so both sources are consulted.
    """
    root = _repo_root()
    models = (
        models_path
        if models_path is not None
        else root / "src/nativeforge/db/models.py"
    )
    versions = versions_dir if versions_dir is not None else root / "alembic/versions"

    modelled: dict[str, str] = {}
    if models.is_file():
        body = models.read_text(encoding="utf-8", errors="replace")
        for match in re.finditer(r"^class (\w+)\(Base\):", body, re.M):
            nxt = body.find("\nclass ", match.start() + 1)
            block = body[match.start() : nxt if nxt > 0 else len(body)]
            name = re.search(r'__tablename__\s*=\s*"([^"]+)"', block)
            if name:
                modelled[name.group(1)] = block

    migration_tables: dict[str, str] = {}
    rls_tables: set[str] = set()
    if versions.is_dir():
        for path in sorted(versions.glob("*.py")):
            body = path.read_text(encoding="utf-8", errors="replace")
            for match in re.finditer(r'op\.create_table\(\s*"?(\w+)"?', body):
                token = match.group(1)
                # Migrations that name their table through a module constant.
                if token in {"TABLE", "table", "TABLE_NAME"}:
                    const = re.search(rf'{token}\s*=\s*"(\w+)"', body)
                    if const:
                        token = const.group(1)
                migration_tables[token] = body
            if "ROW LEVEL SECURITY" in body:
                for name in re.findall(
                    r"ALTER TABLE (\w+) ENABLE ROW LEVEL SECURITY", body
                ):
                    rls_tables.add(name)
                if "{TABLE}" in body:
                    const = re.search(r'TABLE\s*=\s*"(\w+)"', body)
                    if const:
                        rls_tables.add(const.group(1))

    facts: dict[str, dict[str, bool]] = {}
    for table in set(modelled) | set(migration_tables):
        source = modelled.get(table) or migration_tables.get(table) or ""
        facts[table] = {
            "schema_available": True,
            "organization_id_anchor_available": RLS_ANCHOR_COLUMN in source,
            "rls_backed": table in rls_tables,
        }
    return facts


def build_capability(
    capability: str,
    *,
    schema_facts: dict[str, dict[str, bool]] | None = None,
    repositories_dir: Path | None = None,
    customer_auth_live: bool | None = None,
) -> dict[str, Any]:
    """One lane's four questions, each answered from evidence."""
    name = str(capability)
    blocked_reasons: list[str] = []

    if name not in CAPABILITIES:
        # An unrecognised lane is not a lane. Deny, and say which one it was.
        return _json_safe(
            {
                "schema_version": SCHEMA_VERSION,
                "capability": name,
                "schema_available": False,
                "repository_available": False,
                "service_contract_available": False,
                "rls_backed": False,
                "organization_id_anchor_available": False,
                "write_path_available": False,
                "read_path_available": False,
                "customer_auth_required": True,
                "customer_auth_live": False,
                "operational": False,
                "demo_only": False,
                "expected_table": None,
                "rls_anchor": RLS_ANCHOR_COLUMN,
                "blocked_reasons": [f"unknown_persistence_capability:{name}"],
                "rows_written": 0,
                "persisted": False,
                "fabricated": False,
                "live_fetch_performed": False,
            }
        )

    facts = schema_facts if schema_facts is not None else detect_schema_facts()
    table = CAPABILITY_TABLES[name]
    table_facts = facts.get(table, {})

    schema_available = bool(table_facts.get("schema_available"))
    anchor_available = bool(table_facts.get("organization_id_anchor_available"))
    rls_backed = bool(table_facts.get("rls_backed"))

    root = _repo_root()
    repos = (
        repositories_dir
        if repositories_dir is not None
        else root / "src/nativeforge/repositories"
    )
    repository_available = bool(
        (repos / f"{CAPABILITY_REPOSITORIES[name]}.py").is_file()
        or (
            name in CAPABILITY_REPOSITORY_MODULES
            and _module_importable(CAPABILITY_REPOSITORY_MODULES[name])
        )
    )

    contract_available = _module_importable(CAPABILITY_CONTRACT_MODULES[name])

    if customer_auth_live is None:
        customer_auth_live = _detect_customer_auth_live()
    customer_auth_required = CAPABILITY_REQUIRES_AUTH[name]

    if not schema_available:
        blocked_reasons.append(f"no_table_declares_this_capability:{table}")
    if schema_available and not anchor_available:
        # A table with no organization_id cannot be scoped to a customer at all.
        blocked_reasons.append(f"table_has_no_{RLS_ANCHOR_COLUMN}_anchor:{table}")
    if schema_available and not rls_backed:
        blocked_reasons.append(f"no_rls_policy_on:{table}")
    if not repository_available:
        blocked_reasons.append("no_repository_can_address_this_capability")
    if not contract_available:
        blocked_reasons.append("no_service_decides_what_may_be_written")
    if customer_auth_required and not customer_auth_live:
        blocked_reasons.append("no_customer_auth_so_nobody_owns_the_row")

    # A write path is the schema half of the question: is there somewhere to
    # write, scoped correctly, that something can address? It is deliberately
    # independent of auth, so a lane can report "built but unusable".
    write_path_available = bool(
        schema_available
        and anchor_available
        and rls_backed
        and repository_available
        and contract_available
    )
    # Reading needs the same scoping. An unscoped read is a cross-tenant read.
    read_path_available = bool(
        schema_available and anchor_available and rls_backed and repository_available
    )

    operational = bool(
        write_path_available
        and (customer_auth_live or not customer_auth_required)
        and not blocked_reasons
    )

    # Everything that exists but cannot be operated is demo-only by definition.
    demo_only = bool(write_path_available and not operational)

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "capability": name,
            "expected_table": table,
            "rls_anchor": RLS_ANCHOR_COLUMN,
            "schema_available": schema_available,
            "repository_available": repository_available,
            # Gate 123. A second repository, named rather than counted: it
            # addresses a different table and moves no lane on its own.
            "tenant_beta_profile_repository_available": _module_importable(
                TENANT_BETA_PROFILE_REPOSITORY_MODULE
            ),
            "tenant_beta_profile_table": TENANT_BETA_PROFILE_TABLE,
            "service_contract_available": contract_available,
            "rls_backed": rls_backed,
            "organization_id_anchor_available": anchor_available,
            "write_path_available": write_path_available,
            "read_path_available": read_path_available,
            "customer_auth_required": customer_auth_required,
            "customer_auth_live": bool(customer_auth_live),
            "operational": operational,
            "demo_only": demo_only,
            "blocked_reasons": sorted(set(blocked_reasons)),
            # Constants: a capability report reads schema and writes nothing.
            "rows_written": 0,
            "persisted": False,
            "fabricated": False,
            "live_fetch_performed": False,
        }
    )


def _detect_customer_auth_live() -> bool:
    """Can anything in this repository authenticate a real customer?

    Gate 114 answered this by asking whether a customer-session module existed -
    a module-existence proxy standing in for a fact nobody could measure yet. It
    was one conjunct of seven and could not on its own make a lane operational,
    but it was still a proxy.

    Gate 115 built an activation gate that measures the question properly:
    provider configuration, secret presence, issuer validation, callback route,
    session policy, org binding, role mapping, the Gate 111/112 contracts, the
    dev-header posture, and an explicit owner authorization. This now asks that.

    The detector is used rather than the gate directly because the gate reads
    the application's route table, which imports `nativeforge.main` - and this
    module is called from the readiness services that `nativeforge.main`
    transitively imports. The detector short-circuits on two cheap necessary
    conditions before paying that cost.
    """
    from nativeforge.services.customer_auth_live_detector_service import (
        detect_customer_auth_live,
    )

    return detect_customer_auth_live()


def build_capability_matrix(
    *,
    schema_facts: dict[str, dict[str, bool]] | None = None,
    repositories_dir: Path | None = None,
    customer_auth_live: bool | None = None,
) -> dict[str, Any]:
    """Every lane, plus the roll-up nobody may shorten to one word."""
    facts = schema_facts if schema_facts is not None else detect_schema_facts()
    rows = [
        build_capability(
            name,
            schema_facts=facts,
            repositories_dir=repositories_dir,
            customer_auth_live=customer_auth_live,
        )
        for name in CAPABILITIES
    ]

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "rls_anchor": RLS_ANCHOR_COLUMN,
            "forbidden_anchor_names": sorted(FORBIDDEN_ANCHOR_NAMES),
            "capabilities": CAPABILITIES,
            "rows": rows,
            "schema_available_count": sum(1 for r in rows if r["schema_available"]),
            "rls_backed_count": sum(1 for r in rows if r["rls_backed"]),
            "write_path_count": sum(1 for r in rows if r["write_path_available"]),
            "operational_count": sum(1 for r in rows if r["operational"]),
            "operational_capabilities": [
                r["capability"] for r in rows if r["operational"]
            ],
            # The contract exists; what it describes does not yet operate.
            "customer_persistence_contract_available": True,
            "customer_persistence_live": any(r["operational"] for r in rows),
            "customer_auth_live": (
                bool(rows[0]["customer_auth_live"]) if rows else False
            ),
            "rows_written": 0,
            "persisted": False,
            "fabricated": False,
            "live_fetch_performed": False,
        }
    )


def capability_invariant_failures(row: dict[str, Any]) -> list[str]:
    """What must never be true of one capability row."""
    fails: list[str] = []

    if row.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")

    for field in CAPABILITY_FIELDS:
        if field not in row:
            fails.append(f"capability_missing_field:{field}")

    if row.get("rows_written") != 0:
        fails.append("capability_report_wrote_rows")

    for constant in ("persisted", "fabricated", "live_fetch_performed"):
        if row.get(constant) is not False:
            fails.append(f"capability_claimed:{constant}")

    # Persistence may only ever be anchored on the authority column.
    if row.get("rls_anchor") != RLS_ANCHOR_COLUMN:
        fails.append("capability_anchored_on_a_label")

    # Schema is not operation. This is the whole point of the service, so it is
    # also the invariant that matters most.
    if row.get("operational"):
        for required in (
            "schema_available",
            "rls_backed",
            "organization_id_anchor_available",
            "repository_available",
            "service_contract_available",
            "write_path_available",
        ):
            if not row.get(required):
                fails.append(f"operational_without:{required}")
        if row.get("customer_auth_required") and not row.get("customer_auth_live"):
            fails.append("operational_without_customer_auth")
        if row.get("blocked_reasons"):
            fails.append("operational_with_blocked_reasons")

    # A write path is scoped or it is not a write path.
    if row.get("write_path_available"):
        if not row.get("organization_id_anchor_available"):
            fails.append("write_path_without_an_organization_id_anchor")
        if not row.get("rls_backed"):
            fails.append("write_path_without_rls")

    # Reading unscoped data is reading somebody else's data.
    if row.get("read_path_available") and not row.get("rls_backed"):
        fails.append("read_path_without_rls")

    # Operational and demo-only are exclusive; being both is a contradiction.
    if row.get("operational") and row.get("demo_only"):
        fails.append("capability_both_operational_and_demo_only")

    # A refusal must name itself.
    if not row.get("operational") and not row.get("blocked_reasons"):
        fails.append("capability_refused_without_a_reason")

    return fails


def capability_matrix_invariant_failures(matrix: dict[str, Any]) -> list[str]:
    fails: list[str] = []

    if matrix.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")

    rows = matrix.get("rows") or []
    if len(rows) != len(CAPABILITIES):
        fails.append("capability_matrix_does_not_cover_every_capability")

    covered = {r.get("capability") for r in rows}
    for name in CAPABILITIES:
        if name not in covered:
            fails.append(f"capability_not_covered:{name}")

    for row in rows:
        fails.extend(
            f"{row.get('capability')}:{f}" for f in capability_invariant_failures(row)
        )

    # The roll-up must agree with the rows it summarises rather than being set.
    expected_live = any(r.get("operational") for r in rows)
    if matrix.get("customer_persistence_live") is not expected_live:
        fails.append("customer_persistence_live_disagrees_with_the_rows")

    if matrix.get("operational_count") != sum(1 for r in rows if r.get("operational")):
        fails.append("operational_count_disagrees_with_the_rows")

    # Nothing here may be keyed on a label, at any level.
    for name in FORBIDDEN_ANCHOR_NAMES:
        if name not in (matrix.get("forbidden_anchor_names") or []):
            fails.append(f"forbidden_anchor_name_missing:{name}")

    if matrix.get("rows_written") != 0:
        fails.append("capability_matrix_wrote_rows")

    return fails
