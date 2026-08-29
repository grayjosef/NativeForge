"""Customer session and state artifacts (Gate 118H).

Five files describing the session format, the verifier, the state store, and
what none of it makes true. Written to `artifacts/customer_session_state/`.

```text
customer_session_format_contract.json        the format, with no session in it
customer_session_verifier_matrix.csv         seven cases and their verdicts
customer_auth_redirect_state_store_contract.json  scopes, expiry, single use
customer_session_state_demo_fixtures.json    the fixture set entire
customer_session_state_readiness_summary.md  what none of it permits
```

## No credential reaches a file, and it is checked three ways

```text
1. by field name   a nested walk refuses any payload carrying a field named
                   like a cookie, a state, a verifier or a signing key
2. by value        the assembled payload is scanned for the fixture cookie,
                   the fixture state and the fixture verifier
3. by env value    Gate 115's scanner looks for every configured OIDC_* value
```

The second is the one worth explaining. The fixture values are not secrets -
they are committed constants signing nothing anybody would accept. Scanning for
them anyway means the rule does not depend on remembering which values were
fake, and a real value substituted later is caught by the same check.

## The format contract carries no session

`customer_session_format_contract.json` describes the *shape*: the version
prefix, the payload fields, the rules a verifier applies. It contains no
`session_cookie_value`, because a file full of plausible session strings is a
file somebody eventually pastes into a browser.
"""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "nf_customer_session_state_artifact_v1"

ARTIFACT_DIR = "artifacts/customer_session_state"

# Claims that must always carry the same value, whatever is measured.
FIXED_CLAIMS: dict[str, bool] = {
    "session_format_contract_available": True,
    "session_verifier_contract_available": True,
    "redirect_state_store_contract_available": True,
    "session_cookie_valid_actual_environment": False,
    "production_sessions_created": False,
    "real_users_created": False,
    "real_secrets_exposed": False,
    "state_store_production": False,
    "customer_auth_live": False,
    "login_live": False,
    "customer_persistence_live": False,
    "beta_onboarding_ready": False,
}

# Field names that would mean a credential had entered an artifact.
FORBIDDEN_VALUE_FIELDS: frozenset[str] = frozenset(
    {
        "session_cookie_value",
        "cookie_value",
        "signing_key",
        "signing_key_value",
        "state_value",
        "code_verifier",
        "pkce_verifier",
        "verifier",
    }
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _csv(columns: tuple[str, ...], rows: list[list[Any]]) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(columns)
    for row in rows:
        writer.writerow(row)
    return buffer.getvalue()


def _flag(value: Any) -> str:
    return str(bool(value)).lower()


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


def scan_for_fixture_values(text: str) -> list[str]:
    """Which fixture credential values appear in this text.

    The fixture values are not secrets - they sign nothing anybody would
    accept. Scanning for them anyway means the rule does not depend on
    remembering which values were fake.
    """
    from nativeforge.services.customer_session_format_service import (
        FIXTURE_SIGNING_KEY,
        build_fixture_session,
    )
    from nativeforge.services.customer_session_state_demo_fixture_service import (
        FIXTURE_STATE_VALUE,
        FIXTURE_VERIFIER,
    )

    found: list[str] = []
    for name, value in (
        ("fixture_signing_key", FIXTURE_SIGNING_KEY),
        ("fixture_state_value", FIXTURE_STATE_VALUE),
        ("fixture_pkce_verifier", FIXTURE_VERIFIER),
        ("fixture_session_cookie", build_fixture_session()["session_cookie_value"]),
    ):
        if value and value in text:
            found.append(name)
    return found


def build_session_format_contract() -> dict[str, Any]:
    """The format's shape and rules. Carries no session value."""
    from nativeforge.services.customer_session_format_service import (
        MAX_SESSION_SECONDS,
        SESSION_FORMAT_VERSION,
        SIGNING_KEY_ENV,
        signing_key_present,
    )

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "session_format_contract_available": True,
            "format_version": SESSION_FORMAT_VERSION,
            "shape": "<version>.<base64url(payload_json)>.<base64url(hmac_sha256)>",
            "signature_algorithm": "HMAC-SHA256",
            "payload_fields": [
                "v",
                "sid",
                "pid",
                "sub",
                "org",
                "roles",
                "iat",
                "exp",
                "src",
                "email_omitted",
            ],
            "email_carried_in_payload": False,
            "email_omission_rationale": (
                "an email in a cookie is personal data travelling on every "
                "request to every route, readable by anything that can see the "
                "cookie jar. The subject and the organization are what a route "
                "needs; the email is looked up when it is actually wanted"
            ),
            "organization_id_must_be_uuid": True,
            "expiry_carried_in_payload": True,
            "expiry_rationale": (
                "a cookie Max-Age is a request to the browser. A browser that "
                "ignores it, or an attacker replaying a captured cookie, is "
                "unaffected - so the value carries its own expiry and the "
                "verifier checks it server-side"
            ),
            "max_session_seconds": MAX_SESSION_SECONDS,
            "signing_key_env": SIGNING_KEY_ENV,
            # Presence only. The value is compared inside hmac.digest and never
            # read into a field.
            "signing_key_present": signing_key_present(),
            "revocation_supported": False,
            "revocation_note": (
                "a signed session needs no storage to verify, and cannot be "
                "revoked before it expires. Logout clears the cookie; it cannot "
                "un-sign a value already issued. That is why the lifetime is "
                "bounded and rotation is required"
            ),
            # Constants.
            "session_cookie_value_included": False,
            "signing_key_value_included": False,
            "production_sessions_created": False,
            "real_users_created": False,
            "fabricated": False,
        }
    )


def build_state_store_contract() -> dict[str, Any]:
    """The store's scopes and rules. Carries no state or verifier value."""
    from nativeforge.services.customer_auth_redirect_state_store_service import (
        DEFAULT_SCOPE,
        DEFAULT_STATE_TTL_SECONDS,
        MAX_STATE_TTL_SECONDS,
        PRODUCTION_SCOPES,
        STORAGE_SCOPES,
    )

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "redirect_state_store_contract_available": True,
            "storage_scopes": sorted(STORAGE_SCOPES),
            "current_scope": DEFAULT_SCOPE,
            "production_scopes": sorted(PRODUCTION_SCOPES),
            "state_store_production": DEFAULT_SCOPE in PRODUCTION_SCOPES,
            "default_ttl_seconds": DEFAULT_STATE_TTL_SECONDS,
            "max_ttl_seconds": MAX_STATE_TTL_SECONDS,
            "state_expiry_required": True,
            "state_single_use": True,
            "replay_detection": True,
            "replay_rationale": (
                "an expired state stopped being usable; a consumed state was "
                "already used, and reusing it is the signature of somebody "
                "resubmitting a captured callback URL. They are reported "
                "separately because only one is worth alerting on"
            ),
            "database_table_added_by_this_gate": False,
            "database_table_rationale": (
                "a table nothing writes to. No session can be created - no "
                "provider is configured, no signing key exists, and the token "
                "exchange is behind a network flag nothing raises"
            ),
            # Constants.
            "state_value_included": False,
            "pkce_verifier_included": False,
            "persisted_to_database": False,
            "fabricated": False,
        }
    )


def build_session_state_declaration() -> dict[str, Any]:
    """Every required claim, each read from the service that owns it."""
    from nativeforge.services.customer_auth_activation_gate_service import (
        build_customer_auth_activation_gate,
    )
    from nativeforge.services.customer_auth_redirect_state_store_service import (
        DEFAULT_SCOPE,
        PRODUCTION_SCOPES,
    )
    from nativeforge.services.customer_auth_route_readiness_service import (
        build_route_readiness,
    )
    from nativeforge.services.customer_persistence_capability_service import (
        build_capability_matrix,
    )
    from nativeforge.services.customer_session_format_service import (
        signing_key_present,
    )
    from nativeforge.services.customer_session_verifier_service import (
        verify_session_cookie,
    )
    from nativeforge.services.tenant_beta_readiness_service import (
        build_tenant_beta_readiness,
    )

    gate = build_customer_auth_activation_gate()
    routes = build_route_readiness()
    persistence = build_capability_matrix()
    beta = build_tenant_beta_readiness()
    # The actual environment: no cookie, no key, nothing valid.
    actual = verify_session_cookie(cookie_value=None)

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "session_format_contract_available": True,
            "session_verifier_contract_available": True,
            "redirect_state_store_contract_available": True,
            # Measured against the real environment.
            "session_cookie_valid_actual_environment": bool(
                actual["session_cookie_valid"]
            ),
            "session_signing_key_present": signing_key_present(),
            "state_store_scope": DEFAULT_SCOPE,
            "state_store_production": DEFAULT_SCOPE in PRODUCTION_SCOPES,
            "route_auth_enforced": bool(routes["route_auth_enforced"]),
            "ready_for_live_login": bool(routes["ready_for_live_login"]),
            # Unchanged by this gate.
            "customer_auth_live": bool(gate["customer_auth_live"]),
            "login_live": bool(gate["login_live"]),
            "missing_auth_gate_count": len(gate["missing_auth_gates"]),
            "missing_auth_gates": list(gate["missing_auth_gates"]),
            "customer_persistence_live": bool(
                persistence["customer_persistence_live"]
            ),
            "beta_onboarding_ready": bool(beta["ready_for_beta_onboarding"]),
            # Constants.
            "production_sessions_created": False,
            "real_users_created": False,
            "real_secrets_exposed": False,
            "session_cookie_value_committed": False,
            "state_value_committed": False,
            "pkce_verifier_committed": False,
            "provider_called": False,
            "network_calls": False,
            "database_table_added": False,
            "source_monitoring_live": False,
            "source_coverage_claimed": False,
            "fabricated": False,
        }
    )


def render_verifier_matrix(fixture: dict[str, Any]) -> str:
    columns = (
        "case",
        "cookie_present",
        "cookie_parseable",
        "signature_valid",
        "session_expired",
        "organization_id_valid",
        "principal_resolved",
        "membership_verified",
        "session_cookie_valid",
        "rls_context_allowed",
        "customer_auth_live",
        "blocked_reasons",
    )
    rows = [
        [
            row["case"],
            _flag(row["cookie_present"]),
            _flag(row["cookie_parseable"]),
            _flag(row["signature_valid"]),
            _flag(row["session_expired"]),
            _flag(row["organization_id_valid"]),
            _flag(row["principal_resolved"]),
            _flag(row["membership_verified"]),
            _flag(row["session_cookie_valid"]),
            _flag(row["rls_context_allowed"]),
            _flag(row["customer_auth_live"]),
            "; ".join(row["blocked_reasons"]),
        ]
        for row in fixture["rows"]
        if row["kind"] == "session"
    ]
    return _csv(columns, rows)


def render_readiness_summary(declaration: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# Customer session and state readiness (Gate 118)")
    lines.append("")
    lines.append(
        "NativeForge now has a session format, a verifier and a redirect state "
        "store contract. **No production session exists, customer auth is not "
        "live, and login is not live.** No signing key is configured, so no "
        "cookie can verify."
    )
    lines.append("")
    lines.append("## A contract is not a session")
    lines.append("")
    lines.append("```text")
    for key, label in (
        ("session_format_contract_available", "session format contract"),
        ("session_verifier_contract_available", "session verifier contract"),
        ("redirect_state_store_contract_available", "redirect state store"),
        ("session_signing_key_present", "signing key configured"),
        ("session_cookie_valid_actual_environment", "any cookie verifies today"),
        ("state_store_production", "state store is production"),
        ("customer_auth_live", "customer auth live"),
        ("login_live", "login live"),
    ):
        lines.append(f"{label:38s} {_flag(declaration[key])}")
    lines.append("```")
    lines.append("")
    lines.append(
        "The first three are true and the rest are false. Gate 117's verifier "
        "reported `session_cookie_valid: false` because nothing could be "
        "checked; it now reports false because the check runs and fails - "
        "there is no key to check against."
    )
    lines.append("")
    lines.append("## The state store is contract-only")
    lines.append("")
    lines.append(
        "Scope is `contract_only`: nothing is stored anywhere. An "
        "`in_memory_test` scope exists for tests and is a dict that dies with "
        "the process, which disqualifies it for a deployment with more than "
        "one worker. `database` is the only production scope and no table was "
        "added - it would be a table nothing writes to."
    )
    lines.append("")
    lines.append("## What still blocks activation")
    lines.append("")
    lines.append("```text")
    for name in declaration["missing_auth_gates"]:
        lines.append(name)
    lines.append("```")
    lines.append("")
    lines.append(
        "A session format moved none of them. Not one is a session-format fact."
    )
    lines.append("")
    lines.append("## No credential reaches this directory")
    lines.append("")
    lines.append(
        "No session cookie, state value, PKCE verifier or signing key is "
        "committed. The writer refuses on three independent checks: nested "
        "field names, fixture values by content, and every configured `OIDC_*` "
        "environment value."
    )
    lines.append("")
    lines.append("## What is true")
    lines.append("")
    lines.append("```text")
    for claim in sorted(FIXED_CLAIMS):
        if FIXED_CLAIMS[claim]:
            lines.append(f"{claim:48s} {_flag(declaration[claim])}")
    lines.append("```")
    lines.append("")
    lines.append("## Claims this gate does not make")
    lines.append("")
    lines.append("```text")
    for claim in sorted(FIXED_CLAIMS):
        if not FIXED_CLAIMS[claim]:
            lines.append(f"{claim:48s} {_flag(declaration[claim])}")
    lines.append("```")
    lines.append("")
    lines.append(
        "No identity provider was contacted, no network call was made, no user "
        "or production session was created, no database table was added, no "
        "URL was fetched, no collector ran and no source was monitored."
    )
    lines.append("")
    return "\n".join(lines) + "\n"


def write_session_state_artifacts(*, repo_root: Any = None) -> dict[str, Any]:
    """Write all five artifacts. Refuses if any credential appears."""
    from nativeforge.services.customer_auth_activation_artifact_service import (
        scan_for_secret_values,
    )
    from nativeforge.services.customer_session_state_demo_fixture_service import (
        build_session_state_demo_fixture_set,
    )

    root = Path(repo_root) if repo_root else Path(__file__).resolve().parents[3]
    out_dir = root / ARTIFACT_DIR

    declaration = build_session_state_declaration()
    session_format = build_session_format_contract()
    state_store = build_state_store_contract()
    fixture = build_session_state_demo_fixture_set()

    contents = {
        "customer_session_format_contract.json": json.dumps(
            session_format, indent=2, sort_keys=True
        )
        + "\n",
        "customer_session_verifier_matrix.csv": render_verifier_matrix(fixture),
        "customer_auth_redirect_state_store_contract.json": json.dumps(
            state_store, indent=2, sort_keys=True
        )
        + "\n",
        "customer_session_state_demo_fixtures.json": json.dumps(
            fixture, indent=2, sort_keys=True
        )
        + "\n",
        "customer_session_state_readiness_summary.md": render_readiness_summary(
            declaration
        ),
    }

    blob = "".join(contents.values())

    leaked = scan_for_secret_values(blob)
    if leaked:
        raise RuntimeError(
            "refusing to write session state artifacts: a configured "
            f"environment value appears in the payload for {sorted(leaked)}"
        )

    credentials = scan_for_credential_fields(
        [declaration, session_format, state_store, fixture]
    )
    if credentials:
        raise RuntimeError(
            "refusing to write session state artifacts: a credential-shaped "
            f"field appears in the payload: {credentials}"
        )

    fixtures_found = scan_for_fixture_values(blob)
    if fixtures_found:
        raise RuntimeError(
            "refusing to write session state artifacts: a fixture credential "
            f"value appears in the payload: {fixtures_found}"
        )

    out_dir.mkdir(parents=True, exist_ok=True)
    written: dict[str, Any] = {}
    for name, body in contents.items():
        path = out_dir / name
        path.write_text(body, encoding="utf-8")
        written[name] = str(path)

    written["declaration"] = declaration
    written["session_format"] = session_format
    written["state_store"] = state_store
    written["fixture"] = fixture
    return written


def session_state_artifact_invariant_failures(
    declaration: dict[str, Any],
    *,
    summary_text: str = "",
    verifier_matrix_text: str = "",
) -> list[str]:
    fails: list[str] = []

    if declaration.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")

    for claim, expected in FIXED_CLAIMS.items():
        if claim not in declaration:
            fails.append(f"artifact_missing_claim:{claim}")
        elif declaration[claim] is not expected:
            fails.append(f"artifact_claim_wrong:{claim}")

    for constant in (
        "session_cookie_value_committed",
        "state_value_committed",
        "pkce_verifier_committed",
        "provider_called",
        "network_calls",
        "database_table_added",
        "source_monitoring_live",
        "source_coverage_claimed",
        "fabricated",
    ):
        if declaration.get(constant) is not False:
            fails.append(f"session_state_artifact_claimed:{constant}")

    # A cookie cannot verify without a key.
    if declaration.get("session_cookie_valid_actual_environment") and not (
        declaration.get("session_signing_key_present")
    ):
        fails.append("cookie_reported_valid_without_a_signing_key")

    # Only a database-backed store is a production store.
    if declaration.get("state_store_production") and declaration.get(
        "state_store_scope"
    ) != "database":
        fails.append("production_store_claimed_for_a_non_database_scope")

    # Login readiness needs a key.
    if declaration.get("ready_for_live_login") and not declaration.get(
        "session_signing_key_present"
    ):
        fails.append("login_ready_without_a_session_signing_key")

    if summary_text:
        plain = summary_text.replace("**", "")
        if "customer auth is not live, and login is not live" not in plain:
            fails.append("summary_does_not_say_auth_is_not_live")
        if "A contract is not a session" not in summary_text:
            fails.append("summary_does_not_separate_contract_from_session")
        if "contract_only" not in summary_text:
            fails.append("summary_omits_the_state_store_scope")
        for name in declaration.get("missing_auth_gates") or []:
            if name not in summary_text:
                fails.append(f"summary_omits_missing_gate:{name}")

    if verifier_matrix_text:
        parsed = list(csv.reader(io.StringIO(verifier_matrix_text)))
        header, body = parsed[0], parsed[1:]
        valid = header.index("session_cookie_valid")
        rls = header.index("rls_context_allowed")
        live = header.index("customer_auth_live")
        org = header.index("organization_id_valid")
        member = header.index("membership_verified")
        case = header.index("case")

        if not any(row[valid] == "true" for row in body):
            fails.append("verifier_matrix_demonstrates_no_valid_session")
        if not any(row[valid] == "false" for row in body):
            fails.append("verifier_matrix_demonstrates_no_refusal")
        for row in body:
            if row[live] == "true":
                fails.append(f"verifier_matrix_reports_auth_live:{row[case]}")
            if row[rls] == "true" and (
                row[org] != "true" or row[member] != "true" or row[valid] != "true"
            ):
                fails.append(f"verifier_matrix_rls_without_prerequisites:{row[case]}")

    return fails
