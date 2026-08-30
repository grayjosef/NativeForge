"""Customer auth activation runbook (Gate 121D).

A deterministic operator checklist for turning customer auth on safely, built
from what the preflight and provider readiness actually measured.

## Why generated rather than written

A checklist in a document goes stale the moment a gate moves, and nobody
notices, because a document cannot fail a test. Every item here carries a
`status` derived from a live measurement, so an item that says `done` says it
because something checked.

## Verification commands never echo a value

```text
allowed     test -n "${OIDC_ISSUER:-}" && echo set || echo missing
forbidden   echo "$OIDC_ISSUER"
```

Every command in this runbook prints a word, a count, or a status — never the
contents of a variable. Commands that could produce long or sensitive output
write to `/tmp` and print only the path, so an operator pasting the output into
a ticket does not paste a secret with it.

A test greps every generated command for `echo $`, `printf %s "$`, `env`,
`printenv` and `set -x`, and fails if one appears.

## blocks_activation is not the same as risk

```text
blocks_activation   auth cannot go live until this is done
risk                what goes wrong if it is done badly
```

The rollback items block nothing and carry the highest risk in the list: they
are what an operator needs *after* something has gone wrong, and an item that
only appeared once activation failed would appear too late to have been read.

## The do-not-do section

Six items, each naming a specific shortcut somebody under time pressure would
otherwise take. They are phrased as prohibitions rather than warnings because a
warning invites a judgement call and these are not judgement calls.
"""

from __future__ import annotations

import json
import re
from typing import Any

SCHEMA_VERSION = "nf_customer_auth_activation_runbook_v1"

SECTIONS: tuple[str, ...] = (
    "environment_variables",
    "provider_console",
    "database",
    "security",
    "callback_smoke",
    "role_mapping",
    "verified_binding",
    "rollback",
    "do_not_do",
)

ITEM_STATUSES = frozenset({"done", "blocked", "pending", "manual", "prohibited"})

OWNERS = frozenset({"owner", "operator", "engineering", "provider_admin"})

RISKS = frozenset({"low", "medium", "high", "critical"})

# Anything that would print the contents of a variable. A generated command
# containing one of these is a command that leaks when an operator pastes its
# output somewhere.
_UNSAFE_COMMAND_PATTERNS: tuple[str, ...] = (
    r"echo\s+[\"']?\$",
    r"printf\s+[^|]*%s[^|]*\"\$",
    r"\benv\b(?!\s*-)",
    r"\bprintenv\b",
    r"set\s+-x",
    r"\bcat\b\s+[^|]*\.env",
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def command_is_secret_safe(command: str) -> bool:
    """Would running this print the contents of a variable?"""
    text = str(command or "")
    return not any(re.search(p, text) for p in _UNSAFE_COMMAND_PATTERNS)


def _item(
    item_id: str,
    title: str,
    *,
    status: str,
    owner: str,
    risk: str,
    verification_command: str,
    blocks_activation: bool,
    blocked_reasons: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "item_id": item_id,
        "title": title,
        "status": status,
        "owner": owner,
        "risk": risk,
        "verification_command": verification_command,
        "blocks_activation": blocks_activation,
        "blocked_reasons": sorted(set(blocked_reasons or [])),
    }


def _status(done: bool, *, blocked: bool = True) -> str:
    if done:
        return "done"
    return "blocked" if blocked else "pending"


def build_activation_runbook(
    *,
    preflight: dict[str, Any] | None = None,
    provider: dict[str, Any] | None = None,
    activation_gate: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """The checklist, derived from live measurements.

    Every input is injectable so a fixture can render the checklist for a
    hypothetical environment without touching this one.
    """
    from nativeforge.services.customer_auth_activation_gate_service import (
        REQUIRED_AUTH_GATES,
        build_customer_auth_activation_gate,
    )
    from nativeforge.services.customer_auth_environment_preflight_service import (
        ACTIVATION_APPROVAL_ENV,
        PUBLIC_ORIGIN_ENV,
        REQUIRED_DATABASE_REVISION,
        build_environment_preflight,
    )
    from nativeforge.services.customer_auth_provider_readiness_service import (
        build_provider_readiness,
    )

    pre = preflight if preflight is not None else build_environment_preflight()
    prov = provider if provider is not None else build_provider_readiness()
    gate = (
        activation_gate
        if activation_gate is not None
        else build_customer_auth_activation_gate()
    )

    missing_keys = sorted(
        {
            *(pre.get("provider_env_missing_keys") or []),
            *(pre.get("secret_env_missing_keys") or []),
        }
    )
    missing_gates = [n for n in REQUIRED_AUTH_GATES if not gate.get(n)]

    items: dict[str, list[dict[str, Any]]] = {}

    # -- environment_variables ----------------------------------------------
    items["environment_variables"] = [
        _item(
            "env.provider",
            "Set OIDC_ISSUER, OIDC_CLIENT_ID and OIDC_AUDIENCE",
            status=_status(bool(pre.get("provider_env_present"))),
            owner="operator",
            risk="high",
            # Asks the preflight rather than the shell. A loop echoing "$k"
            # prints only a key name and is still refused by the scanner, which
            # cannot tell a name from a value - and the preflight already
            # guarantees names-only output and is tested for it.
            verification_command=(
                'uv run python -c "from nativeforge.services.'
                "customer_auth_environment_preflight_service import "
                "build_environment_preflight as b; "
                "print(b()['provider_env_missing_keys'])\""
            ),
            blocks_activation=True,
            blocked_reasons=[
                f"missing:{k}" for k in (pre.get("provider_env_missing_keys") or [])
            ],
        ),
        _item(
            "env.secret",
            "Supply OIDC_CLIENT_SECRET from a secret manager",
            status=_status(bool(pre.get("secret_env_present"))),
            owner="owner",
            risk="critical",
            verification_command=(
                'test -n "${OIDC_CLIENT_SECRET:-}" && echo present || echo missing'
            ),
            blocks_activation=True,
            blocked_reasons=[
                f"missing:{k}" for k in (pre.get("secret_env_missing_keys") or [])
            ],
        ),
        _item(
            "env.signing_key",
            "Supply NF_SESSION_SIGNING_KEY from an environment or secret manager",
            status=_status(
                str(pre.get("signing_key_source")) in {"environment", "secret_manager"}
            ),
            owner="owner",
            risk="critical",
            verification_command=(
                'test -n "${NF_SESSION_SIGNING_KEY:-}" && echo present || echo missing'
            ),
            blocks_activation=True,
            blocked_reasons=(
                [] if pre.get("signing_key_present") else ["no_signing_key_configured"]
            ),
        ),
        _item(
            "env.public_origin",
            f"Set {PUBLIC_ORIGIN_ENV} to the origin browsers actually reach",
            status=_status(bool(pre.get("public_origin_configured"))),
            owner="operator",
            risk="medium",
            verification_command=(
                f'test -n "${{{PUBLIC_ORIGIN_ENV}:-}}" && echo set || echo missing'
            ),
            blocks_activation=False,
            blocked_reasons=(
                []
                if pre.get("public_origin_configured")
                else ["no_public_origin_configured_to_compare_against"]
            ),
        ),
    ]

    # -- provider_console ----------------------------------------------------
    items["provider_console"] = [
        _item(
            "provider.application",
            "Create the application in the provider console",
            status=_status(bool(prov.get("issuer_configured"))),
            owner="provider_admin",
            risk="high",
            verification_command="# provider console; no local command",
            blocks_activation=True,
        ),
        _item(
            "provider.redirect_uri",
            "Register the redirect URI, matching a route that can consume it",
            status=_status(bool(prov.get("callback_route_matches_redirect_uri"))),
            owner="provider_admin",
            risk="critical",
            verification_command=(
                'uv run python -c "from nativeforge.services.'
                "customer_auth_provider_readiness_service import "
                "build_provider_readiness as b; "
                "print(b()['callback_route_matches_redirect_uri'])\""
            ),
            blocks_activation=True,
            blocked_reasons=(
                []
                if prov.get("callback_route_matches_redirect_uri")
                else ["configured_redirect_uri_matches_no_callback_route"]
            ),
        ),
        _item(
            "provider.jwks",
            "Validate the issuer JWKS once, deliberately, under review",
            status="manual" if not prov.get("jwks_validated") else "done",
            owner="engineering",
            risk="medium",
            verification_command=(
                "# the only step that touches the network; run under review"
            ),
            blocks_activation=True,
            blocked_reasons=(
                []
                if prov.get("jwks_validated")
                else ["jwks_never_checked_which_is_not_the_same_as_failed"]
            ),
        ),
    ]

    # -- database ------------------------------------------------------------
    items["database"] = [
        _item(
            "db.migrate",
            f"Apply migrations to the runtime database, to head "
            f"{REQUIRED_DATABASE_REVISION}",
            status=_status(bool(pre.get("database_revision_ready"))),
            owner="operator",
            risk="high",
            verification_command=(
                "uv run alembic current 2>/tmp/nf_alembic_current.err "
                "| tail -1; echo stderr=/tmp/nf_alembic_current.err"
            ),
            blocks_activation=True,
            blocked_reasons=(
                []
                if pre.get("database_revision_ready")
                else [f"database_not_at_revision_{REQUIRED_DATABASE_REVISION}"]
            ),
        ),
        _item(
            "db.rls_proof",
            "Re-run the RLS isolation proof against the migrated database",
            status="manual",
            owner="engineering",
            risk="critical",
            verification_command=(
                "./scripts/verify_nativeforge_rls_isolation.sh "
                "> /tmp/nf_rls_proof.log 2>&1; tail -1 /tmp/nf_rls_proof.log"
            ),
            blocks_activation=True,
        ),
    ]

    # -- security ------------------------------------------------------------
    items["security"] = [
        _item(
            "security.dev_header",
            "Replace X-NF-Org-Id across every route module, then disable it",
            status=_status(not bool(pre.get("dev_header_production_blocker"))),
            owner="engineering",
            risk="critical",
            verification_command=(
                'uv run python -c "from nativeforge.services.'
                "dev_org_header_shutdown_readiness_service import "
                "build_dev_header_shutdown_readiness as b; "
                "r=b(); print(r['dev_header_used_by_routes'], "
                "r['safe_to_disable_now'])\""
            ),
            blocks_activation=True,
            blocked_reasons=(
                ["dev_header_must_be_replaced_before_production_auth"]
                if pre.get("dev_header_production_blocker")
                else []
            ),
        ),
        _item(
            "security.cookie_policy",
            "Confirm the session cookie policy is production safe",
            status=_status(bool(pre.get("session_cookie_production_safe"))),
            owner="engineering",
            risk="high",
            verification_command=(
                'uv run python -c "from nativeforge.services.'
                "customer_session_cookie_policy_service import "
                "build_session_cookie_policy as b; print(b()['production_safe'])\""
            ),
            blocks_activation=True,
        ),
    ]

    # -- callback_smoke ------------------------------------------------------
    items["callback_smoke"] = [
        _item(
            "smoke.callback_session",
            "Complete one real redirect in a real browser and validate the session",
            status=_status(bool(gate.get("callback_session_validated"))),
            owner="operator",
            risk="high",
            verification_command="# a human with a browser; no local command",
            blocks_activation=True,
        ),
        _item(
            "smoke.org_binding",
            "Confirm the callback resolves to an organization_id and a membership",
            status=_status(bool(gate.get("org_binding_passed"))),
            owner="operator",
            risk="critical",
            verification_command="# a human with a browser; no local command",
            blocks_activation=True,
        ),
        _item(
            "smoke.invite_binding",
            "Confirm the invite path binds correctly",
            status=_status(bool(gate.get("invite_binding_passed"))),
            owner="operator",
            risk="high",
            verification_command="# a human with a browser; no local command",
            blocks_activation=True,
        ),
    ]

    # -- role_mapping --------------------------------------------------------
    items["role_mapping"] = [
        _item(
            "roles.provider",
            "Define roles in the provider console",
            status=_status(bool(gate.get("role_mapping_passed"))),
            owner="provider_admin",
            risk="high",
            verification_command="# provider console; no local command",
            blocks_activation=True,
        ),
        _item(
            "roles.explicit_mapping",
            "Map every provider role explicitly; unknown roles grant nothing",
            status=_status(bool(gate.get("role_mapping_passed"))),
            owner="engineering",
            risk="critical",
            verification_command=(
                'uv run python -c "from nativeforge.services.'
                'customer_auth_role_mapping_service import ROLES; print(sorted(ROLES))"'
            ),
            blocks_activation=True,
        ),
    ]

    # -- verified_binding ----------------------------------------------------
    items["verified_binding"] = [
        _item(
            "binding.verifier_identity",
            "Confirm a verified OIDC subject exists to name as the verifier",
            status=_status(bool(gate.get("customer_auth_live"))),
            owner="operator",
            risk="critical",
            verification_command=(
                'uv run python -c "from nativeforge.services.'
                "verified_binding_workflow_service import run_binding_workflow as w; "
                "print(w(operation='inspect_pending')['customer_auth_live'])\""
            ),
            blocks_activation=True,
            blocked_reasons=(
                []
                if gate.get("customer_auth_live")
                else ["no_verified_oidc_subject_exists_to_name_as_a_verifier"]
            ),
        ),
        _item(
            "binding.first_binding",
            "Create the first verified binding through the Gate 120 workflow",
            status="pending",
            owner="operator",
            risk="critical",
            verification_command=(
                'uv run python -c "from nativeforge.services.'
                "tenant_customer_org_binding_repository_service import "
                "list_bindings_for_organization as l; print('repository ready')\""
            ),
            blocks_activation=False,
        ),
    ]

    # -- rollback ------------------------------------------------------------
    items["rollback"] = [
        _item(
            "rollback.unset_approval",
            f"Unset {ACTIVATION_APPROVAL_ENV} to withdraw activation",
            status="manual",
            owner="owner",
            risk="critical",
            verification_command=(
                f"unset {ACTIVATION_APPROVAL_ENV}; "
                f'test -z "${{{ACTIVATION_APPROVAL_ENV}:-}}" && echo withdrawn'
            ),
            blocks_activation=False,
        ),
        _item(
            "rollback.rotate_signing_key",
            "Rotate NF_SESSION_SIGNING_KEY if a session may have leaked",
            status="manual",
            owner="owner",
            risk="critical",
            verification_command=(
                "# a signed session cannot be revoked before it expires - "
                "rotating the key invalidates every outstanding session at once"
            ),
            blocks_activation=False,
        ),
        _item(
            "rollback.revoke_bindings",
            "Revoke any verified binding created in error - never delete one",
            status="manual",
            owner="operator",
            risk="high",
            verification_command=(
                "# Gate 120's revoke_binding is an UPDATE; the row and its history stay"
            ),
            blocks_activation=False,
        ),
        _item(
            "rollback.provider_redirect",
            "Remove the redirect URI from the provider console",
            status="manual",
            owner="provider_admin",
            risk="high",
            verification_command="# provider console; no local command",
            blocks_activation=False,
        ),
    ]

    # -- do_not_do -----------------------------------------------------------
    items["do_not_do"] = [
        _item(
            "never.dev_header",
            "Do not leave X-NF-Org-Id enabled alongside live customer auth",
            status="prohibited",
            owner="engineering",
            risk="critical",
            verification_command=(
                "# an unauthenticated header that sets app.current_org_id is a "
                "cross-tenant read waiting to happen"
            ),
            blocks_activation=False,
        ),
        _item(
            "never.tenant_id_anchor",
            "Do not use tenant_id as an RLS authority",
            status="prohibited",
            owner="engineering",
            risk="critical",
            verification_command="# organization_id is the only anchor",
            blocks_activation=False,
        ),
        _item(
            "never.customer_org_id_anchor",
            "Do not use customer_org_id as an RLS authority",
            status="prohibited",
            owner="engineering",
            risk="critical",
            verification_command="# it is a label; it has no foreign key",
            blocks_activation=False,
        ),
        _item(
            "never.profile_id_anchor",
            "Do not use organization_profile_id as an organization_id",
            status="prohibited",
            owner="engineering",
            risk="critical",
            verification_command=(
                "# a real value from a real column in the wrong identity space"
            ),
            blocks_activation=False,
        ),
        _item(
            "never.fake_binding",
            "Do not insert a verified binding without a real verifier identity",
            status="prohibited",
            owner="operator",
            risk="critical",
            verification_command=(
                "# ck_nf_binding_verified_needs_verifier refuses it, and the "
                "workflow refuses before the database does"
            ),
            blocks_activation=False,
        ),
        _item(
            "never.fake_session",
            "Do not sign a production session with the committed fixture key",
            status="prohibited",
            owner="engineering",
            risk="critical",
            verification_command=(
                "# the fixture key is disqualified by source, not by length"
            ),
            blocks_activation=False,
        ),
    ]

    flat = [item for section in SECTIONS for item in items[section]]
    blocking = [i for i in flat if i["blocks_activation"] and i["status"] != "done"]

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "sections": list(SECTIONS),
            "items": items,
            "item_count": len(flat),
            "blocking_item_count": len(blocking),
            "blocking_item_ids": [i["item_id"] for i in blocking],
            "done_item_count": sum(1 for i in flat if i["status"] == "done"),
            "prohibited_item_count": sum(
                1 for i in flat if i["status"] == "prohibited"
            ),
            "missing_environment_key_names": missing_keys,
            "missing_activation_gates": missing_gates,
            "all_commands_secret_safe": all(
                command_is_secret_safe(i["verification_command"]) for i in flat
            ),
            # Constants. A runbook describes; it changes nothing.
            "activation_performed": False,
            "environment_mutated": False,
            "provider_contacted": False,
            "customer_auth_live": False,
            "login_live": False,
            "secret_values_included": False,
        }
    )


def runbook_invariant_failures(runbook: dict[str, Any]) -> list[str]:
    """What a runbook must never be able to contain."""
    failures: list[str] = []

    if runbook.get("schema_version") != SCHEMA_VERSION:
        failures.append("schema_version_mismatch")

    if list(runbook.get("sections") or []) != list(SECTIONS):
        failures.append("sections_do_not_match_the_contract")

    items = runbook.get("items") or {}
    for section in SECTIONS:
        if not items.get(section):
            failures.append(f"section_is_empty:{section}")

    flat = [item for section in SECTIONS for item in (items.get(section) or [])]

    for item in flat:
        label = item.get("item_id")
        if item.get("status") not in ITEM_STATUSES:
            failures.append(f"status_outside_vocabulary:{label}")
        if item.get("owner") not in OWNERS:
            failures.append(f"owner_outside_vocabulary:{label}")
        if item.get("risk") not in RISKS:
            failures.append(f"risk_outside_vocabulary:{label}")
        if not command_is_secret_safe(item.get("verification_command", "")):
            failures.append(f"verification_command_could_print_a_value:{label}")
        if item.get("status") == "done" and item.get("blocked_reasons"):
            failures.append(f"item_done_with_blocked_reasons:{label}")

    if not runbook.get("all_commands_secret_safe"):
        failures.append("a_verification_command_could_print_a_value")

    if runbook.get("secret_values_included"):
        failures.append("a_secret_value_reached_the_runbook")

    if runbook.get("activation_performed") or runbook.get("environment_mutated"):
        failures.append("a_runbook_changed_something")

    if runbook.get("provider_contacted"):
        failures.append("a_runbook_contacted_a_provider")

    if runbook.get("customer_auth_live") or runbook.get("login_live"):
        failures.append("a_runbook_claimed_auth_is_live")

    if not any(i["status"] == "prohibited" for i in flat):
        failures.append("no_do_not_do_items_present")

    return sorted(set(failures))
