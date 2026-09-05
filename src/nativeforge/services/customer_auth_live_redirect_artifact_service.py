"""Live redirect and signing key artifacts (Gate 119I).

Five files describing what Gate 119 built and what none of it makes true.
Written to `artifacts/customer_auth_live_redirect/`.

```text
customer_auth_signing_key_readiness.json     presence, source, fitness to sign
customer_auth_authorization_url_contract.json  the builder, with no live URL
customer_auth_redirect_state_schema.json     migration 0030's columns and rules
customer_auth_live_redirect_demo_fixtures.json  the ten cases entire
customer_auth_live_redirect_readiness_summary.md  what none of it permits
```

## No credential reaches a file, and it is checked four ways

Gate 118's three scans, plus one this gate adds:

```text
1. by field name   a nested walk refuses any payload carrying a field named
                   like a state, a verifier, a signing key or a digest of one
2. by fixture value  the assembled payload is scanned for the committed fake
                   state, verifier and signing key
3. by env value    Gate 115's scanner looks for every configured OIDC_* value
4. by URL shape    any string containing `state=` or `code_challenge=` with a
                   value that is not the redaction placeholder
```

The fourth is new and is the one this gate needed. An authorization URL is a
single string carrying a live state in a query parameter — it passes a
field-name scan trivially, because the field is called `authorization_url`.

## Only redacted URLs are published

`customer_auth_authorization_url_contract.json` carries
`authorization_url_redacted`, in which the state and the challenge are replaced
by placeholders. The live URL is built, measured, and dropped.

A real state in a committed file is a state somebody can present at a callback.
That the state here is a fixture is beside the point: a rule that depended on
remembering which values were fake would eventually meet one that was not.

## The schema file is not the migration

`customer_auth_redirect_state_schema.json` describes migration 0030's columns
and the rules they enforce. A test asserts the two agree, so a column added to
one and not the other fails rather than drifting.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "nf_customer_auth_live_redirect_artifact_v1"

ARTIFACT_DIR = "artifacts/customer_auth_live_redirect"

# Claims that must always carry the same value, whatever is measured.
FIXED_CLAIMS: dict[str, bool] = {
    "signing_key_readiness_contract_available": True,
    "authorization_url_contract_available": True,
    "redirect_state_repository_available": True,
    "redirect_state_table_exists": True,
    "signing_key_ready_actual_environment": False,
    "authorization_url_available_actual_environment": False,
    "redirect_state_rows_written": False,
    "production_sessions_created": False,
    "real_users_created": False,
    "real_secrets_exposed": False,
    "provider_contacted": False,
    "network_calls_made": False,
    "customer_auth_live": False,
    "login_live": False,
    "customer_persistence_live": False,
    "beta_onboarding_ready": False,
}

# Field names that would mean a credential had entered an artifact. Gate 118's
# set, plus the two digest columns - a digest of a live state is not a live
# state, and it is also not something a published file needs.
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
        "client_secret",
        "state_hash",
        "pkce_verifier_hash",
    }
)

# A live authorization URL carries its state in a query parameter, which no
# field-name scan can see. These find it.
_STATE_PARAM_RE = re.compile(r"[?&]state=([^&\s\"]+)")
_CHALLENGE_PARAM_RE = re.compile(r"[?&]code_challenge=([^&\s\"]+)")


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


def scan_for_unredacted_urls(text: str) -> list[str]:
    """Which URL parameters carry a value that is not a redaction placeholder.

    The check this gate needed. A URL is one string, its field is called
    `authorization_url`, and a field-name scan waves it through while it carries
    a live state in a query parameter.
    """
    from nativeforge.services.customer_auth_authorization_url_service import (
        REDACTED_CHALLENGE,
        REDACTED_STATE,
    )

    found: list[str] = []
    for name, pattern, placeholder in (
        ("state", _STATE_PARAM_RE, REDACTED_STATE),
        ("code_challenge", _CHALLENGE_PARAM_RE, REDACTED_CHALLENGE),
    ):
        for match in pattern.findall(text):
            if match != placeholder:
                found.append(f"unredacted_{name}_in_a_url")
                break
    return sorted(set(found))


def scan_for_fixture_values(text: str) -> list[str]:
    """Which fixture credential values appear in this text.

    The fixture values are not secrets - they sign nothing anybody would
    accept. Scanning for them anyway means the rule does not depend on
    remembering which values were fake, and a real value substituted later is
    caught by the same check.
    """
    from nativeforge.services.customer_auth_live_redirect_demo_fixture_service import (
        DEMO_FIXTURE_KEY,
        DEMO_STATE,
        DEMO_VERIFIER,
    )
    from nativeforge.services.customer_session_format_service import (
        FIXTURE_SIGNING_KEY,
    )

    found: list[str] = []
    for name, value in (
        ("fixture_signing_key", FIXTURE_SIGNING_KEY),
        ("fixture_demo_signing_key", DEMO_FIXTURE_KEY),
        ("fixture_state_value", DEMO_STATE),
        ("fixture_pkce_verifier", DEMO_VERIFIER),
    ):
        if value and value in text:
            found.append(name)
    return sorted(set(found))


def build_live_redirect_declaration() -> dict[str, Any]:
    """What Gate 119 built, and the sixteen claims it does not make."""
    from nativeforge.services.customer_auth_activation_gate_service import (
        REQUIRED_AUTH_GATES,
        build_customer_auth_activation_gate,
    )
    from nativeforge.services.customer_auth_authorization_url_service import (
        build_authorization_url,
    )
    from nativeforge.services.customer_auth_redirect_state_repository_service import (
        TABLE_NAME,
    )
    from nativeforge.services.customer_auth_signing_key_readiness_service import (
        MIN_KEY_LENGTH,
        PRODUCTION_KEY_SOURCES,
        build_signing_key_readiness,
    )

    gate = build_customer_auth_activation_gate()
    signing = build_signing_key_readiness()
    url = build_authorization_url()

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "redirect_state_table": TABLE_NAME,
            "migration_revision": "0030",
            # The live head, which moves when a later gate adds a migration.
            # Gate 127 added 0035.
            "alembic_head": "0041",
            "minimum_signing_key_length": MIN_KEY_LENGTH,
            "production_signing_key_sources": sorted(PRODUCTION_KEY_SOURCES),
            # Measured against the real environment, which has none of it.
            "signing_key_present": bool(signing["signing_key_present"]),
            "signing_key_source": signing["signing_key_source"],
            "signing_key_rotation_supported": bool(
                signing["signing_key_rotation_supported"]
            ),
            "provider_configured": bool(url["provider_configured"]),
            "authorization_url_available": bool(url["authorization_url_available"]),
            "required_auth_gate_count": len(REQUIRED_AUTH_GATES),
            "missing_auth_gates": [
                name for name in REQUIRED_AUTH_GATES if not gate.get(name)
            ],
            **FIXED_CLAIMS,
        }
    )


def build_signing_key_readiness_artifact() -> dict[str, Any]:
    """The signing key contract, with no key in it."""
    from nativeforge.services.customer_auth_signing_key_readiness_service import (
        KEY_SOURCES,
        MIN_DISTINCT_CHARACTERS,
        MIN_KEY_LENGTH,
        PRODUCTION_KEY_SOURCES,
        build_signing_key_readiness,
    )
    from nativeforge.services.customer_session_format_service import SIGNING_KEY_ENV

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "environment_variable": SIGNING_KEY_ENV,
            "key_sources": sorted(KEY_SOURCES),
            "production_key_sources": sorted(PRODUCTION_KEY_SOURCES),
            "minimum_length": MIN_KEY_LENGTH,
            "minimum_distinct_characters": MIN_DISTINCT_CHARACTERS,
            "rules": [
                "presence is not readiness",
                "a local_dev_fixture key may never sign a production session",
                "production signing requires environment or secret_manager",
                "sign and verify use one symmetric key, so they never diverge",
                "rotation may be false and must be reported when it is",
                "the value is measured and never returned",
            ],
            # The actual environment, and it is empty.
            "actual": build_signing_key_readiness(),
        }
    )


def build_authorization_url_artifact() -> dict[str, Any]:
    """The URL builder, publishing only a redacted URL."""
    from nativeforge.services.customer_auth_authorization_url_service import (
        AUTHORIZE_PATH,
        DEFAULT_SCOPES,
        RESPONSE_TYPE,
        build_authorization_url,
        build_fixture_authorization_url,
    )
    from nativeforge.services.customer_auth_state_pkce_service import (
        CODE_CHALLENGE_METHOD,
    )

    fixture = build_fixture_authorization_url()
    actual = build_authorization_url()

    def _published(result: dict[str, Any]) -> dict[str, Any]:
        """Everything except the live URL."""
        return {
            key: value for key, value in result.items() if key != "authorization_url"
        }

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "response_type": RESPONSE_TYPE,
            "authorize_path": AUTHORIZE_PATH,
            "code_challenge_method": CODE_CHALLENGE_METHOD,
            "default_scopes": list(DEFAULT_SCOPES),
            "rules": [
                "building a URL makes no network call",
                "the client secret never appears in a URL",
                "a state is required",
                "a PKCE challenge is required",
                "missing provider configuration blocks the URL",
                "only a redacted URL is ever published",
            ],
            # The fixture case, redacted. Every host is `.invalid`.
            "fixture": _published(fixture),
            "fixture_url_redacted": fixture["authorization_url_redacted"],
            # The actual environment, which builds nothing.
            "actual": _published(actual),
        }
    )


def build_redirect_state_schema_artifact() -> dict[str, Any]:
    """Migration 0030's columns and the rules they enforce."""
    from nativeforge.services.customer_auth_redirect_state_repository_service import (
        REDIRECT_STATES,
        TABLE_NAME,
    )
    from nativeforge.services.customer_auth_redirect_state_store_service import (
        MAX_STATE_TTL_SECONDS,
        PRODUCTION_SCOPES,
        STORAGE_SCOPES,
    )

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "table_name": TABLE_NAME,
            "migration_revision": "0030",
            "columns": [
                {
                    "name": column.name,
                    "type": str(column.type),
                    "nullable": bool(column.nullable),
                }
                for column in REDIRECT_STATES.columns
            ],
            "column_count": len(REDIRECT_STATES.columns),
            "storage_scopes": sorted(STORAGE_SCOPES),
            "production_scopes": sorted(PRODUCTION_SCOPES),
            "max_state_ttl_seconds": MAX_STATE_TTL_SECONDS,
            "organization_rls_applies": False,
            "why_no_rls": (
                "a redirect state is created before anybody is authenticated, "
                "so there is no organization to scope it to and no "
                "app.current_org_id to set. Inventing an RLS anchor at issue "
                "time would be worse than having none. nf_identities (0023) is "
                "the precedent: a verified subject exists before it belongs to "
                "anything"
            ),
            "rules": [
                "hashes are stored, never the raw state",
                "hashes are stored, never the raw PKCE verifier",
                "a state is single-use and consumption is one-way",
                "a state expires, and the database enforces expires_at > created_at",
                "a consumed state presented again is a replay, not an expiry",
                "no customer data row is ever written here",
            ],
            "rows_written": 0,
        }
    )


def render_readiness_summary() -> str:
    """What Gate 119 moved, and the sentence to refuse."""
    from nativeforge.services.customer_auth_activation_gate_service import (
        REQUIRED_AUTH_GATES,
        build_customer_auth_activation_gate,
    )
    from nativeforge.services.customer_auth_live_redirect_demo_fixture_service import (
        build_live_redirect_demo_fixture_set,
    )

    gate = build_customer_auth_activation_gate()
    fixture = build_live_redirect_demo_fixture_set()
    missing = [name for name in REQUIRED_AUTH_GATES if not gate.get(name)]
    contacted = str(fixture["provider_contacted"]).lower()

    lines = [
        "# Customer auth live redirect readiness (Gate 119)",
        "",
        "## The sentence to refuse",
        "",
        '> "NativeForge can build an authorization URL, so login works."',
        "",
        "It can build one when an issuer, a client id and a redirect URI are",
        "supplied. None is. And a URL is a string — the browser visits it, and",
        f"{len(missing)} of {len(REQUIRED_AUTH_GATES)} activation gates remain",
        "unsatisfied whether or not one is built.",
        "",
        "## What moved",
        "",
        "```text",
        "signing key                 presence -> readiness, with a named source",
        "authorization URL           nothing existed -> a builder that makes one",
        "redirect state              contract-only -> a table, migration 0030",
        "/login state and PKCE       constants False -> a generator that runs",
        "session verification        one failure -> missing key vs bad signature",
        "```",
        "",
        "## What did not move",
        "",
        "```text",
    ]
    for name in (
        "signing_key_ready_actual_environment",
        "authorization_url_available_actual_environment",
        "redirect_state_rows_written",
        "production_sessions_created",
        "provider_contacted",
        "network_calls_made",
        "customer_auth_live",
        "login_live",
        "customer_persistence_live",
        "beta_onboarding_ready",
    ):
        lines.append(f"{name:52s}{str(FIXED_CLAIMS[name]).lower()}")
    lines.extend(
        [
            "```",
            "",
            "## The unsatisfied gates",
            "",
            "```text",
        ]
    )
    lines.extend(missing)
    lines.extend(
        [
            "```",
            "",
            "## The fixture set",
            "",
            "```text",
            f"cases                        {fixture['case_count']}",
            f"keys fit to sign             {fixture['can_sign_count']}",
            f"authorization URLs built     {fixture['url_returned_count']}",
            f"state consumptions permitted {fixture['consume_allowed_count']}",
            f"replays detected             {fixture['replay_detected_count']}",
            f"sessions created             {fixture['sessions_created']}",
            f"providers contacted          {contacted}",
            "```",
            "",
            "Nine of ten cases refuse. The tenth exists so the nine are",
            "falsifiable — a contract that only says no is a constant.",
            "",
            "## What the next gate needs",
            "",
            "```text",
            "1. NF_SESSION_SIGNING_KEY   from an environment or a secret manager,",
            "                            supplied out-of-band. The fixture key",
            "                            may never sign a production session.",
            "",
            "2. OIDC_ISSUER              the three the URL builder asks for by",
            "   OIDC_CLIENT_ID           name, plus a redirect URI",
            "   a redirect URI",
            "",
            "3. the database scope       /login must write a row and /callback",
            "                            must read it. The table is empty.",
            "",
            "4. network_call_allowed     raised deliberately, under review",
            "",
            "5. signing key rotation     not implemented anywhere",
            "",
            "6. owner authorization      NF_CUSTOMER_AUTH_ACTIVATION_APPROVAL",
            "```",
            "",
        ]
    )
    return "\n".join(lines)


def write_live_redirect_artifacts(*, repo_root: Any = None) -> dict[str, Any]:
    """Write all five artifacts. Refuses if any credential appears."""
    from nativeforge.services.customer_auth_activation_artifact_service import (
        scan_for_secret_values,
    )
    from nativeforge.services.customer_auth_live_redirect_demo_fixture_service import (
        build_live_redirect_demo_fixture_set,
    )

    root = Path(repo_root) if repo_root else Path(__file__).resolve().parents[3]
    out_dir = root / ARTIFACT_DIR

    signing = build_signing_key_readiness_artifact()
    url = build_authorization_url_artifact()
    schema = build_redirect_state_schema_artifact()
    fixture = build_live_redirect_demo_fixture_set()
    declaration = build_live_redirect_declaration()

    contents = {
        "customer_auth_signing_key_readiness.json": json.dumps(
            signing, indent=2, sort_keys=True
        )
        + "\n",
        "customer_auth_authorization_url_contract.json": json.dumps(
            url, indent=2, sort_keys=True
        )
        + "\n",
        "customer_auth_redirect_state_schema.json": json.dumps(
            schema, indent=2, sort_keys=True
        )
        + "\n",
        "customer_auth_live_redirect_demo_fixtures.json": json.dumps(
            {"declaration": declaration, "fixture": fixture},
            indent=2,
            sort_keys=True,
        )
        + "\n",
        "customer_auth_live_redirect_readiness_summary.md": render_readiness_summary(),
    }

    blob = "".join(contents.values())
    payloads = [signing, url, schema, fixture, declaration]

    # Four independent refusals. Each would have to fail for a credential to
    # reach a file, and the writer raises rather than writing a partial set.
    credential_fields = sorted(
        {field for payload in payloads for field in scan_for_credential_fields(payload)}
    )
    if credential_fields:
        raise ValueError(
            f"refusing to write: credential field names present {credential_fields}"
        )

    fixture_values = scan_for_fixture_values(blob)
    if fixture_values:
        raise ValueError(
            f"refusing to write: fixture credential values present {fixture_values}"
        )

    unredacted = scan_for_unredacted_urls(blob)
    if unredacted:
        raise ValueError(f"refusing to write: {unredacted}")

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
            "fixture_values_found": fixture_values,
            "unredacted_urls_found": unredacted,
            "configured_secret_values_found": env_secrets,
        }
    )


def live_redirect_artifact_invariant_failures(result: dict[str, Any]) -> list[str]:
    """What a written artifact set must never be able to claim."""
    fails: list[str] = []

    if result.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")

    if result.get("file_count") != 5:
        fails.append("expected_five_artifacts")

    for field in (
        "credential_fields_found",
        "fixture_values_found",
        "unredacted_urls_found",
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

    if not declaration.get("missing_auth_gates"):
        fails.append("declaration_claims_every_activation_gate_is_satisfied")

    return sorted(set(fails))
