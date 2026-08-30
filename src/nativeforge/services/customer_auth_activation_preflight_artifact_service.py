"""Auth activation preflight artifacts (Gate 121G).

Five files describing what is missing before customer auth could be turned on.
Written to `artifacts/customer_auth_activation_preflight/`.

```text
customer_auth_environment_preflight.json          key names and booleans
customer_auth_provider_readiness.json             provider gates, redacted URLs
customer_auth_activation_runbook.json             28 operator items
customer_auth_activation_preflight_demo_fixtures.json  the eight cases
customer_auth_activation_preflight_summary.md     what none of it permits
```

## Four scans, and two of them are new

```text
1  by field name       nested walk for anything named like a secret
2  by env value        every configured value of every key, from Gate 115
3  by URL query        any published URL carrying a query string or fragment
4  by command shape    any runbook command that could print a variable
```

The third and fourth are this gate's. A preflight artifact is *made of*
configuration, so the usual "does it contain a credential" question is not
enough — a URL with a query string could carry a token, and a verification
command an operator copies out of a JSON file could print a secret on their
terminal and then into a ticket.

## Why the environment file is safe to commit

It contains key *names* and booleans. `OIDC_CLIENT_SECRET` appearing in
`secret_env_missing_keys` says a variable is unset; it says nothing about what
the value would be. There is deliberately no list of keys that *are* set.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "nf_customer_auth_activation_preflight_artifact_v1"

ARTIFACT_DIR = "artifacts/customer_auth_activation_preflight"

# Claims that must always carry the same value, whatever is measured.
FIXED_CLAIMS: dict[str, bool] = {
    "auth_activation_preflight_available": True,
    "provider_readiness_available": True,
    "activation_runbook_available": True,
    "verified_binding_ready_actual": False,
    "operator_authorization_present": False,
    "customer_auth_live": False,
    "login_live": False,
    "customer_persistence_live": False,
    "beta_onboarding_ready": False,
    "production_rollout_ready": False,
    "secret_values_exposed": False,
    "provider_called": False,
    "network_calls_made": False,
    "source_monitoring_live": False,
    "source_coverage_claimed": False,
}

FIXED_COUNTS: dict[str, int] = {
    "production_verified_bindings_created": 0,
    "real_customer_rows_written": 0,
    "real_users_created": 0,
    "production_sessions_created": 0,
}

# Field names that would mean a value had entered an artifact.
FORBIDDEN_VALUE_FIELDS: frozenset[str] = frozenset(
    {
        "client_secret",
        "client_secret_value",
        "secret",
        "secret_value",
        "signing_key",
        "signing_key_value",
        "database_url",
        "access_token",
        "id_token",
        "refresh_token",
        "session_cookie_value",
        "state_value",
        "code_verifier",
    }
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def scan_for_credential_fields(payload: Any) -> list[str]:
    """Which forbidden field names appear anywhere. Names, never values."""
    found: set[str] = set()

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                if key in FORBIDDEN_VALUE_FIELDS:
                    found.add(key)
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(payload)
    return sorted(found)


def scan_for_unredacted_urls(payload: Any) -> list[str]:
    """Which published URLs carry a query string or a fragment.

    A preflight artifact is made of configuration, so "does it contain a
    credential" is not enough on its own. A redirect URI with a query string is
    already malformed and could carry anything; every URL here should have been
    reduced to scheme, host and path before it was published.
    """
    found: set[str] = set()

    def walk(node: Any, key: str = "") -> None:
        if isinstance(node, dict):
            for k, v in node.items():
                walk(v, str(k))
        elif isinstance(node, list):
            for item in node:
                walk(item, key)
        elif isinstance(node, str) and "://" in node:
            if "?" in node or "#" in node:
                found.add(f"unredacted_url_in:{key or 'unnamed_field'}")

    walk(payload)
    return sorted(found)


def scan_for_unsafe_commands(runbook: dict[str, Any]) -> list[str]:
    """Which runbook commands could print the contents of a variable.

    An operator copies these out of a JSON file and pastes the output into a
    ticket. A command that echoes a variable turns a checklist into a leak.
    """
    from nativeforge.services.customer_auth_activation_runbook_service import (
        SECTIONS,
        command_is_secret_safe,
    )

    found: list[str] = []
    items = runbook.get("items") or {}
    for section in SECTIONS:
        for item in items.get(section) or []:
            if not command_is_secret_safe(item.get("verification_command", "")):
                found.append(f"unsafe_command:{item.get('item_id')}")
    return sorted(set(found))


def build_preflight_declaration() -> dict[str, Any]:
    """What Gate 121 measured, and the claims it does not make."""
    from nativeforge.services.customer_auth_activation_gate_service import (
        REQUIRED_AUTH_GATES,
        build_customer_auth_activation_gate,
    )
    from nativeforge.services.customer_auth_environment_preflight_service import (
        build_environment_preflight,
    )
    from nativeforge.services.customer_auth_provider_readiness_service import (
        build_provider_readiness,
    )

    gate = build_customer_auth_activation_gate()
    pre = build_environment_preflight()
    prov = build_provider_readiness()

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "required_auth_gate_count": len(REQUIRED_AUTH_GATES),
            "missing_auth_gates": list(gate["missing_auth_gates"]),
            "activation_blocker_names": list(gate["activation_blocker_names"]),
            # Measured against the real environment, which has none of it.
            "provider_env_present_actual": bool(pre["provider_env_present"]),
            "secret_env_present_actual": bool(pre["secret_env_present"]),
            "signing_key_present_actual": bool(pre["signing_key_present"]),
            "database_revision_ready_actual": bool(pre["database_revision_ready"]),
            "callback_url_ready_actual": bool(pre["callback_path_matches_route"]),
            "role_mapping_ready_actual": bool(gate["role_mapping_passed"]),
            "provider_ready_actual": bool(prov["provider_ready"]),
            "required_database_revision": pre["required_database_revision"],
            **FIXED_CLAIMS,
            **FIXED_COUNTS,
        }
    )


def render_preflight_summary() -> str:
    """What Gate 121 measured, and the sentence to refuse."""
    from nativeforge.services.customer_auth_activation_gate_service import (
        REQUIRED_AUTH_GATES,
        build_customer_auth_activation_gate,
    )
    from nativeforge.services.customer_auth_activation_preflight_demo_fixture_service import (  # noqa: E501
        build_preflight_demo_fixture_set,
    )
    from nativeforge.services.customer_auth_activation_runbook_service import (
        build_activation_runbook,
    )
    from nativeforge.services.customer_auth_environment_preflight_service import (
        build_environment_preflight,
    )

    gate = build_customer_auth_activation_gate()
    pre = build_environment_preflight()
    runbook = build_activation_runbook()
    fixture = build_preflight_demo_fixture_set()
    missing = list(gate["missing_auth_gates"])

    lines = [
        "# Customer auth activation preflight (Gate 121)",
        "",
        "## The sentence to refuse",
        "",
        '> "The preflight exists, so we know how to turn auth on."',
        "",
        "The preflight says what is missing. Nothing in it configures anything,",
        "and every remaining blocker is outside this repository:",
        f"{len(missing)} of {len(REQUIRED_AUTH_GATES)} activation gates are",
        "unsatisfied and **not one of them can be satisfied by writing code**.",
        "",
        "## What moved",
        "",
        "```text",
        "environment preflight       none      key names and booleans",
        "provider readiness          none      10 gates, all measurable offline",
        "operator runbook            none      28 items, 9 sections, 6 do-not-do",
        "activation blockers         a list    named by who has to act",
        "callback URL correctness    unchecked measured, and it is wrong",
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
        "verified_binding_ready_actual",
        "operator_authorization_present",
        "beta_onboarding_ready",
        "production_rollout_ready",
        "provider_called",
        "network_calls_made",
        "source_monitoring_live",
        "source_coverage_claimed",
    ):
        lines.append(f"{name:44s}{str(FIXED_CLAIMS[name]).lower()}")
    for name, value in FIXED_COUNTS.items():
        lines.append(f"{name:44s}{value}")
    lines.extend(
        [
            "```",
            "",
            "## The defect this gate found",
            "",
            "```text",
            f"configured callback   {pre['callback_url_redacted']}",
            f"API callback route    {pre['callback_route_path']}",
            "frontend route        none - the frontend declares no routes",
            "```",
            "",
            "The value an operator would copy into the provider console points at",
            "a path that exists in neither the API nor the frontend. Registering",
            "it and completing a login would land a browser on a 404 holding a",
            "live authorization code, and the failure would look like a provider",
            "problem rather than a configuration one.",
            "",
            "## The eight named blockers",
            "",
            "```text",
        ]
    )
    lines.extend(sorted(gate["activation_blocker_names"]))
    lines.extend(
        [
            "```",
            "",
            "## The unsatisfied activation gates",
            "",
            "```text",
        ]
    )
    lines.extend(missing)
    lines.extend(
        [
            "```",
            "",
            "## The runbook",
            "",
            "```text",
            f"items                    {runbook['item_count']}",
            f"blocking activation      {runbook['blocking_item_count']}",
            f"already done             {runbook['done_item_count']}",
            f"prohibited (do not do)   {runbook['prohibited_item_count']}",
            f"commands secret-safe     "
            f"{str(runbook['all_commands_secret_safe']).lower()}",
            "```",
            "",
            "## The fixture set",
            "",
            "```text",
            f"cases                    {fixture['case_count']}",
            f"disagreeing              "
            f"{len(fixture['cases_disagreeing_with_expectation'])}",
            f"any claiming auth live   {str(fixture['customer_auth_live']).lower()}",
            "```",
            "",
            "Eight cases walk one hypothetical deployment from nothing configured",
            "to everything configured. The last one has every preflight gate",
            "green, carries the owner's signature, and auth is still off - three",
            "of the sixteen gates need a real browser and nobody has run one.",
            "",
            "## Next operator actions, in dependency order",
            "",
            "```text",
            "1  create the provider application",
            "2  set OIDC_ISSUER, OIDC_CLIENT_ID, OIDC_CLIENT_SECRET, OIDC_AUDIENCE",
            "3  set NF_SESSION_SIGNING_KEY from an environment or secret manager",
            "4  fix the redirect URI so it matches a route, and register it",
            "5  apply migrations to the runtime database, to head 0030",
            "6  define provider roles and map them explicitly",
            "7  run the callback smoke once, with a real browser",
            "8  replace X-NF-Org-Id across 15 route modules, then disable it",
            "9  set NF_CUSTOMER_AUTH_ACTIVATION_APPROVAL",
            "```",
            "",
            "Step 9 is last on purpose: the approval variable is an owner's",
            "signature, not a switch, and signing before 1-8 would authorize an",
            "activation that cannot happen.",
            "",
        ]
    )
    return "\n".join(lines)


def write_preflight_artifacts(*, repo_root: Any = None) -> dict[str, Any]:
    """Write all five artifacts. Refuses if anything forbidden appears."""
    from nativeforge.services.customer_auth_activation_artifact_service import (
        scan_for_secret_values,
    )
    from nativeforge.services.customer_auth_activation_preflight_demo_fixture_service import (  # noqa: E501
        build_preflight_demo_fixture_set,
    )
    from nativeforge.services.customer_auth_activation_runbook_service import (
        build_activation_runbook,
    )
    from nativeforge.services.customer_auth_environment_preflight_service import (
        build_environment_preflight,
    )
    from nativeforge.services.customer_auth_provider_readiness_service import (
        build_provider_readiness,
    )

    root = Path(repo_root) if repo_root else Path(__file__).resolve().parents[3]
    out_dir = root / ARTIFACT_DIR

    preflight = build_environment_preflight()
    provider = build_provider_readiness()
    runbook = build_activation_runbook()
    fixture = build_preflight_demo_fixture_set()
    declaration = build_preflight_declaration()

    contents = {
        "customer_auth_environment_preflight.json": json.dumps(
            preflight, indent=2, sort_keys=True
        )
        + "\n",
        "customer_auth_provider_readiness.json": json.dumps(
            provider, indent=2, sort_keys=True
        )
        + "\n",
        "customer_auth_activation_runbook.json": json.dumps(
            runbook, indent=2, sort_keys=True
        )
        + "\n",
        "customer_auth_activation_preflight_demo_fixtures.json": json.dumps(
            {"declaration": declaration, "fixture": fixture},
            indent=2,
            sort_keys=True,
        )
        + "\n",
        "customer_auth_activation_preflight_summary.md": render_preflight_summary(),
    }

    blob = "".join(contents.values())
    payloads = [preflight, provider, runbook, fixture, declaration]

    credential_fields = sorted(
        {field for payload in payloads for field in scan_for_credential_fields(payload)}
    )
    if credential_fields:
        raise ValueError(
            f"refusing to write: credential field names present {credential_fields}"
        )

    unredacted = sorted(
        {found for payload in payloads for found in scan_for_unredacted_urls(payload)}
    )
    if unredacted:
        raise ValueError(f"refusing to write: {unredacted}")

    unsafe_commands = scan_for_unsafe_commands(runbook)
    if unsafe_commands:
        raise ValueError(f"refusing to write: {unsafe_commands}")

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
            "credential_fields_found": credential_fields,
            "unredacted_urls_found": unredacted,
            "unsafe_commands_found": unsafe_commands,
            "configured_secret_values_found": env_secrets,
        }
    )


def preflight_artifact_invariant_failures(result: dict[str, Any]) -> list[str]:
    """What a written artifact set must never be able to claim."""
    fails: list[str] = []

    if result.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")

    if result.get("file_count") != 5:
        fails.append("expected_five_artifacts")

    for field in (
        "credential_fields_found",
        "unredacted_urls_found",
        "unsafe_commands_found",
        "configured_secret_values_found",
    ):
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

    if not declaration.get("activation_blocker_names"):
        fails.append("declaration_claims_no_blockers_remain")

    return sorted(set(fails))
