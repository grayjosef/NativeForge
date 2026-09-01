"""Dev header replacement artifacts (Gate 122G).

Four files describing what still depends on `X-NF-Org-Id`, what replaces it, and
what none of it makes true. Written to `artifacts/dev_header_replacement/`.

```text
dev_header_usage_inventory.csv                 one row per module, by relationship
auth_org_context_dependency_contract.json      the three modes and their rules
dev_header_replacement_demo_fixtures.json      the nine cases
dev_header_replacement_readiness_summary.md    what remains, and why
```

## The inventory has three relationships, not two

```text
route      a route module that obtains an organization through the dev header
provider   the module that defines the chain - it depends on its own providers
prose      a module that names the dependency without wiring it
```

Gate 122A found the provider being counted as a route, which overstated the
migration by one in four separate places since Gate 116. The CSV keeps the three
apart so a reader counting rows gets the right answer whichever column they
filter on.

## Every remaining module is listed with a reason

The gate converts no routes, and a list of fourteen modules with no explanation
would read as an oversight. Each row carries why it stays: converting today
would return 401 to every caller, because the only trusted claim source needs
customer auth, which is eleven activation gates away.
"""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "nf_dev_header_replacement_artifact_v1"

ARTIFACT_DIR = "artifacts/dev_header_replacement"

# Why every remaining module stays. One reason, because there is one reason.
REMAINS_REASON = (
    "converting today returns 401 to every caller: the only claim source the "
    "RLS guard trusts is verified_auth_claim, which needs customer auth, which "
    "Gate 121 measured as 11 activation gates away with zero code-only blockers"
)

PROVIDER_REASON = (
    "defines the dev-header dependency chain and depends on its own providers "
    "internally; it is the thing to be replaced, not a consumer of it"
)

PROSE_REASON = (
    "names the dependency in prose without wiring it into a route; several of "
    "these document why they do not use it"
)

# Claims that must always carry the same value, whatever is measured.
FIXED_CLAIMS: dict[str, bool] = {
    "dev_header_replacement_contract_available": True,
    "central_replacement_module_available": True,
    "customer_auth_live": False,
    "login_live": False,
    "customer_persistence_live": False,
    "safe_to_disable_now": False,
    "dev_header_is_production_safe": False,
    "current_org_id_set_by_this_gate": False,
}

FIXED_COUNTS: dict[str, int] = {
    "production_safe_dev_header_uses": 0,
    "real_customer_data_written": 0,
    "routes_converted": 0,
}

INVENTORY_COLUMNS: tuple[str, ...] = (
    "module",
    "relationship",
    "counts_toward_migration",
    "production_safe",
    "reason",
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def build_usage_inventory() -> list[dict[str, Any]]:
    """One row per module, by its relationship to the dev header."""
    from nativeforge.services.dev_org_header_shutdown_readiness_service import (
        detect_dev_header_route_usage,
    )

    usage = detect_dev_header_route_usage()
    rows: list[dict[str, Any]] = []

    for name in sorted(usage["modules"]):
        rows.append(
            {
                "module": name,
                "relationship": "route",
                "counts_toward_migration": True,
                "production_safe": False,
                "reason": REMAINS_REASON,
            }
        )
    for name in sorted(usage["provider_modules"]):
        rows.append(
            {
                "module": name,
                "relationship": "provider",
                "counts_toward_migration": False,
                "production_safe": False,
                "reason": PROVIDER_REASON,
            }
        )
    for name in sorted(usage["mention_only_modules"]):
        rows.append(
            {
                "module": name,
                "relationship": "prose",
                "counts_toward_migration": False,
                "production_safe": True,
                "reason": PROSE_REASON,
            }
        )
    return rows


def render_usage_inventory(rows: list[dict[str, Any]]) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(INVENTORY_COLUMNS)
    for row in rows:
        writer.writerow(
            [
                row["module"],
                row["relationship"],
                str(row["counts_toward_migration"]).lower(),
                str(row["production_safe"]).lower(),
                row["reason"],
            ]
        )
    return buffer.getvalue()


def build_dependency_contract() -> dict[str, Any]:
    """The three modes and the rules that separate them."""
    from nativeforge.services.customer_auth_org_context_dependency_service import (
        DEPENDENCY_MODES,
        DEV_HEADER_NAME,
        DEV_HEADER_SETTING,
        FORBIDDEN_IDENTITY_NAMES,
        RESULT_FIELDS,
    )
    from nativeforge.services.rls_context_claim_guard_service import (
        RLS_ELIGIBLE_IDENTITY_NAMES,
        TRUSTED_CLAIM_SOURCES,
    )

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "dependency_modes": sorted(DEPENDENCY_MODES),
            "result_fields": list(RESULT_FIELDS),
            "dev_header_name": DEV_HEADER_NAME,
            "dev_header_setting": DEV_HEADER_SETTING,
            "rls_eligible_identity_names": sorted(RLS_ELIGIBLE_IDENTITY_NAMES),
            "forbidden_identity_names": sorted(FORBIDDEN_IDENTITY_NAMES),
            "trusted_claim_sources": sorted(TRUSTED_CLAIM_SOURCES),
            "central_dependency_module": "nativeforge.api.deps_customer_auth",
            "central_dependency_functions": [
                "get_customer_org_context_required",
                "get_customer_org_context_optional",
                "get_dev_org_context_explicit_only",
            ],
            "rules": [
                "production mode never accepts X-NF-Org-Id as authority",
                "the dev header is honoured only in dev_demo_explicit mode, "
                "outside production, with the setting enabled",
                "an unknown app_env counts as production",
                "org context requires a valid session, a resolved "
                "organization_id and a verified membership",
                "optional mode returns no organization, never a default one",
                "tenant_id, customer_org_id and organization_profile_id never "
                "set an RLS context",
                "this contract sets no GUCs and creates nothing",
            ],
            **FIXED_CLAIMS,
            **FIXED_COUNTS,
        }
    )


def _converted_route_modules() -> list[str]:
    """Route modules on the session-backed organization dependency.

    Measured by walking the registered routes and reading each one's resolved
    dependency tree, the same way the remaining consumers are counted. A list
    maintained by hand would drift the moment somebody converted a module
    without editing it, and the guard that reads this would then pass a zero it
    should have refused.
    """
    try:
        from nativeforge.services.dev_header_exposure_matrix_service import (
            build_dev_header_exposure_matrix,
        )

        matrix = build_dev_header_exposure_matrix(ingress_patterns=[])
    except Exception:  # pragma: no cover - the app always imports here
        return []
    return sorted(
        f"{row['module']}.py"
        for row in matrix["rows"]
        if row["replacement_available"] == "converted"
    )


def render_readiness_summary() -> str:
    """What remains, and the sentence to refuse."""
    from nativeforge.services.dev_header_replacement_demo_fixture_service import (
        build_dev_header_replacement_fixture_set,
    )
    from nativeforge.services.dev_org_header_shutdown_readiness_service import (
        build_dev_header_shutdown_readiness,
    )

    shutdown = build_dev_header_shutdown_readiness()
    fixture = build_dev_header_replacement_fixture_set()
    modules = list(shutdown["dev_header_route_modules"])

    lines = [
        "# Dev header replacement readiness (Gate 122)",
        "",
        "## The sentence to refuse",
        "",
        '> "The replacement exists, so the dev header is gone."',
        "",
        "The replacement exists and is imported by no route. Fourteen route",
        "modules still obtain an organization through `X-NF-Org-Id`, and every",
        "one of them stays for the same reason: converting today would return",
        "401 to every caller, because the only claim source the RLS guard",
        "trusts needs customer auth.",
        "",
        "## The counting correction",
        "",
        "```text",
        "before   dev_header_used_by_routes: 15",
        f"after    route modules:     {len(modules)}",
        f"         provider modules:  {len(shutdown['dev_header_provider_modules'])}",
        f"         prose-only:        "
        f"{len(shutdown['dev_header_mention_only_modules'])}",
        "```",
        "",
        "`deps_db.py` defines the dev-header chain and depends on its own",
        "providers internally. It was being counted as one of the routes that",
        "consume it, which overstated the migration by one in four places since",
        "Gate 116.",
        "",
        "## What moved",
        "",
        "```text",
        "org context contract        none      3 modes, 12 reported fields",
        "central dependency          none      3 functions, imported by no route",
        "dev header posture          implicit  named dev_demo_explicit, refused",
        "                                      in production",
        "claim guard wiring          none      routed for the first time",
        "route module count          15        14, with the provider separated",
        "```",
        "",
        "## What did not move",
        "",
        "```text",
    ]
    for name in (
        "customer_auth_live",
        "login_live",
        "customer_persistence_live",
        "safe_to_disable_now",
        "dev_header_is_production_safe",
        "current_org_id_set_by_this_gate",
    ):
        lines.append(f"{name:44s}{str(FIXED_CLAIMS[name]).lower()}")
    for name, value in FIXED_COUNTS.items():
        lines.append(f"{name:44s}{value}")
    lines.extend(
        [
            "```",
            "",
            "## The fourteen route modules that remain",
            "",
            "```text",
        ]
    )
    lines.extend(modules)
    lines.extend(
        [
            "```",
            "",
            "Each is listed in `dev_header_usage_inventory.csv` with the same",
            "reason. None was converted, and converting any of them before a",
            "session can verify would make it unreachable.",
            "",
            "## Why converting now would gain nothing",
            "",
            "```text",
            "API paths called by frontend/src   0",
            "API paths called by frontend/e2e   0",
            "```",
            "",
            "The frontend calls the API zero times; the public demo is a static",
            "app fed by committed JSON. So no customer can reach the fourteen",
            "today, and the safety property a conversion would buy is one the",
            "deployment already has by accident.",
            "",
            "That is worth saying plainly rather than leaving as an assumption:",
            "the demo cannot break, and the reason it cannot is also the reason",
            "the conversion is not urgent.",
            "",
            "## The fixture set",
            "",
            "```text",
            f"cases                        {fixture['case_count']}",
            f"permitted org contexts       {fixture['org_context_available_count']}",
            f"dev-only contexts            {fixture['dev_context_available_count']}",
            f"refused with 401             {fixture['refused_401_count']}",
            f"any claiming auth live       "
            f"{str(fixture['customer_auth_live']).lower()}",
            "```",
            "",
            "Exactly one case reaches a production-safe organization context and",
            "exactly one reaches a dev-only one. Collapsing those two would undo",
            "the distinction this gate exists to make.",
            "",
            "## What the next gate needs",
            "",
            "```text",
            "1. customer auth activation   the 11 gates from Gate 121. Until a",
            "                              session can verify, no route can be",
            "                              converted without becoming",
            "                              unreachable.",
            "",
            "2. then convert the fourteen  one at a time, each with a test",
            "                              proving unauthenticated refusal or",
            "                              optional no-context behaviour",
            "",
            "3. then disable the header    safe_to_disable_now becomes true only",
            "                              when no route module depends on it",
            "```",
            "",
        ]
    )
    return "\n".join(lines)


def build_replacement_declaration() -> dict[str, Any]:
    """What Gate 122 built, and the claims it does not make."""
    from nativeforge.services.customer_auth_activation_gate_service import (
        build_customer_auth_activation_gate,
    )
    from nativeforge.services.dev_org_header_shutdown_readiness_service import (
        build_dev_header_shutdown_readiness,
    )

    shutdown = build_dev_header_shutdown_readiness()
    gate = build_customer_auth_activation_gate()

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "auth_replacement_available": bool(shutdown["auth_replacement_available"]),
            "remaining_dev_header_modules": int(shutdown["dev_header_used_by_routes"]),
            "remaining_dev_header_module_names": list(
                shutdown["dev_header_route_modules"]
            ),
            # Gate 134: what the remaining count is zero *because of*.
            "converted_dev_header_module_names": _converted_route_modules(),
            "dev_header_provider_modules": list(
                shutdown["dev_header_provider_modules"]
            ),
            "missing_auth_gates": list(gate["missing_auth_gates"]),
            "activation_blocker_names": list(gate["activation_blocker_names"]),
            **FIXED_CLAIMS,
            **FIXED_COUNTS,
        }
    )


def write_replacement_artifacts(*, repo_root: Any = None) -> dict[str, Any]:
    """Write all four artifacts. Refuses if anything forbidden appears."""
    from nativeforge.services.customer_auth_activation_artifact_service import (
        scan_for_secret_values,
    )
    from nativeforge.services.dev_header_replacement_demo_fixture_service import (
        build_dev_header_replacement_fixture_set,
    )

    root = Path(repo_root) if repo_root else Path(__file__).resolve().parents[3]
    out_dir = root / ARTIFACT_DIR

    inventory = build_usage_inventory()
    contract = build_dependency_contract()
    fixture = build_dev_header_replacement_fixture_set()
    declaration = build_replacement_declaration()

    contents = {
        "dev_header_usage_inventory.csv": render_usage_inventory(inventory),
        "auth_org_context_dependency_contract.json": json.dumps(
            contract, indent=2, sort_keys=True
        )
        + "\n",
        "dev_header_replacement_demo_fixtures.json": json.dumps(
            {"declaration": declaration, "fixture": fixture},
            indent=2,
            sort_keys=True,
        )
        + "\n",
        "dev_header_replacement_readiness_summary.md": render_readiness_summary(),
    }

    blob = "".join(contents.values())

    # Every module in the inventory must carry a reason. A list of fourteen
    # names with no explanation reads as an oversight rather than a decision.
    unexplained = sorted(
        row["module"] for row in inventory if not str(row.get("reason") or "").strip()
    )
    if unexplained:
        raise ValueError(f"refusing to write: modules with no reason {unexplained}")

    env_secrets = scan_for_secret_values(blob)
    if env_secrets:
        raise ValueError(
            f"refusing to write: configured secret values present {env_secrets}"
        )

    out_dir.mkdir(parents=True, exist_ok=True)
    written: dict[str, str] = {}
    for name, text in contents.items():
        path = out_dir / name
        path.write_text(text, encoding="utf-8")
        written[name] = str(path)

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "artifact_dir": str(out_dir),
            "files_written": written,
            "file_count": len(written),
            "declaration": declaration,
            "inventory_row_count": len(inventory),
            "unexplained_modules": unexplained,
            "configured_secret_values_found": env_secrets,
        }
    )


def replacement_artifact_invariant_failures(result: dict[str, Any]) -> list[str]:
    """What a written artifact set must never be able to claim."""
    fails: list[str] = []

    if result.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")

    if result.get("file_count") != 4:
        fails.append("expected_four_artifacts")

    for field in ("unexplained_modules", "configured_secret_values_found"):
        if result.get(field):
            fails.append(f"artifacts_written_with_{field}")

    declaration = dict(result.get("declaration") or {})
    for claim, expected in FIXED_CLAIMS.items():
        if claim not in declaration:
            fails.append(f"declaration_missing_claim:{claim}")
        elif bool(declaration[claim]) is not expected:
            fails.append(f"fixed_claim_changed:{claim}")

    for count, expected_count in FIXED_COUNTS.items():
        if declaration.get(count) != expected_count:
            fails.append(f"fixed_count_changed:{count}")

    if not declaration.get("missing_auth_gates"):
        fails.append("declaration_claims_every_activation_gate_is_satisfied")

    # Gate 134: same narrowing as the fixture service. A declaration may say
    # none remain only when it can also name what they were converted onto.
    if not declaration.get("remaining_dev_header_module_names") and not declaration.get(
        "converted_dev_header_module_names"
    ):
        fails.append("declaration_claims_no_dev_header_modules_remain")

    if declaration.get("remaining_dev_header_modules") != len(
        declaration.get("remaining_dev_header_module_names") or []
    ):
        fails.append("the_remaining_module_count_disagrees_with_the_names")

    return sorted(set(fails))
