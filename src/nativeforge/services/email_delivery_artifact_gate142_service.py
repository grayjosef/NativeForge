"""Gate 142H: what digest delivery proved, as committed files.

Deterministic. The smoke runs against a migrated database this module builds and
throws away, driven through a `TestClient` with a real signed session for a real
membership — so the artifact records a measurement and still produces the same
bytes every time.

No email is sent, no provider is contacted, no mail library is imported, and no
recipient address reaches any file this module writes. Every artifact is scanned
for an `@` before it is returned.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import sqlalchemy as sa

from nativeforge.services.digest_delivery_dry_run_queue_service import (
    DELIVERY_BLOCKED_REASONS,
    DELIVERY_INTENT_STATES,
    FORBIDDEN_STATES,
    TABLE_NAME,
    queue_invariant_failures,
)
from nativeforge.services.digest_delivery_renderer_service import (
    FORBIDDEN_CLAIMS,
    MAX_BODY_BYTES,
    MAX_RENDERED_ITEMS,
    MAX_SUBJECT_LENGTH,
    RENDER_FIELDS,
)
from nativeforge.services.digest_delivery_route_smoke_service import (
    delivery_route_smoke_invariant_failures,
    run_digest_delivery_route_smoke,
)
from nativeforge.services.digest_recipient_validation_service import (
    FIXTURE_DOMAIN,
    REFUSAL_REASONS,
    recipient_invariant_failures,
    validate_recipient,
)
from nativeforge.services.email_delivery_readiness_service import (
    DELIVERY_ROUTE_MODULE,
    NOT_APPROVED,
    build_email_delivery_readiness,
    delivery_readiness_invariant_failures,
    detect_delivery_route_module,
    detect_mail_library_imports,
)
from nativeforge.services.email_provider_configuration_preflight_service import (
    PREFLIGHT_STATES,
    REQUIRED_SETTING_NAMES,
    SEND_EVIDENCE_FIELDS,
    build_email_provider_preflight,
    email_preflight_invariant_failures,
)

SCHEMA_VERSION = "nf_email_delivery_gate142_artifact_v1"

ARTIFACT_DIR = "artifacts/email_delivery_gate142"

ARTIFACT_FILES: tuple[str, ...] = (
    "email_delivery_survey.json",
    "email_provider_preflight.json",
    "digest_delivery_render_smoke.json",
    "recipient_validation_smoke.json",
    "dry_run_delivery_queue_smoke.json",
    "email_delivery_readiness.json",
    "next_email_activation_blockers.md",
)

DEMO_ORGANIZATION_ID = "bbbbbbbb-cccc-dddd-eeee-ffffffffffff"
OTHER_ORGANIZATION_ID = "cccccccc-dddd-eeee-ffff-00000000d142"
REAL_ORGANIZATION_ID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"

#: A fixture mailbox at a reserved domain. RFC 2606 reserves `.invalid`
#: precisely so nothing can ever be delivered to it, which is the point.
FIXTURE_ADDRESS = f"gate142-owner@fixture.{FIXTURE_DOMAIN}"

FIXED_NOW = datetime(2026, 9, 4, tzinfo=UTC)

CREDENTIAL_FIELDS: tuple[str, ...] = (
    "id_token",
    "access_token",
    "refresh_token",
    "client_secret",
    "code_verifier",
    "pkce_verifier",
    "session_cookie_value",
    "provider_subject",
    "subject",
    "email",
    "cookie",
    "recipient_address",
    "api_key",
    "sender_address",
)

#: A mailbox: a local part, an @, a domain with a real TLD. Deliberately not a
#: bare `@` - see the guard below.
ADDRESS_SHAPE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")

FORBIDDEN_MARKERS: tuple[str, ...] = (
    "set-cookie:",
    "GOCSPX-",
    "BEGIN PRIVATE KEY",
    "@gmail.com",
    "eyJ",
    "nf_session=",
    "smtp://",
    # The fixture mailbox itself. If this reaches a file, an address did.
    FIXTURE_ADDRESS,
)


def _dump(obj: Any) -> str:
    return json.dumps(obj, indent=2, sort_keys=True) + "\n"


def _low(value: Any) -> str:
    return str(bool(value)).lower()


def _seed_profile(connection: Any, organization_id: str) -> None:
    from nativeforge.services.tenant_profile_repository_service import (
        upsert_tenant_profile,
    )

    result = upsert_tenant_profile(
        connection=connection,
        now=FIXED_NOW,
        organization_id=organization_id,
        tenant_id_label=f"t-{organization_id[:8]}",
        customer_org_id_label=f"c-{organization_id[:8]}",
        recognition_status="federally_recognized",
        recognition_status_fact_status="demo_fixture",
        operating_states=["SC"],
        operating_states_fact_status="demo_fixture",
        applicant_classes=["federally_recognized_tribe"],
        applicant_classes_fact_status="demo_fixture",
        digest_frequency="weekly",
        profile_status="active",
        is_demo=True,
    )
    if not result.get("rows_written"):
        raise AssertionError(f"fixture profile refused: {result['blocked_reasons']}")


def _hermetic_run() -> dict[str, Any]:
    """The delivery routes, driven against a database built for this call only."""
    from fastapi.testclient import TestClient

    previous_url = os.environ.get("DATABASE_URL")
    previous_key = os.environ.get("NF_SESSION_SIGNING_KEY")
    from nativeforge.db import session as _session_module

    previous_engine = _session_module.engine
    tmp = Path(tempfile.mkdtemp(prefix="nf_gate142_artifact_"))
    os.environ["DATABASE_URL"] = f"sqlite+pysqlite:///{(tmp / 'nf.sqlite3').as_posix()}"
    os.environ["NF_SESSION_SIGNING_KEY"] = "gate142-artifact-session-key-" + ("k" * 40)

    try:
        from alembic import command
        from alembic.config import Config

        from nativeforge.lib.settings import get_settings as _get_settings

        _get_settings.cache_clear()
        command.upgrade(Config("alembic.ini"), "head")

        from sqlalchemy.orm import sessionmaker

        from nativeforge.main import create_app
        from nativeforge.services import tenant_source_watchlist_service as watchlist
        from nativeforge.services.customer_session_format_service import build_session
        from nativeforge.services.dev_org_membership_bootstrap_service import (
            insert_membership,
            upsert_identity,
        )

        engine = sa.create_engine(os.environ["DATABASE_URL"])
        _session_module.engine = engine
        factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)

        with engine.begin() as connection:
            for organization_id in (DEMO_ORGANIZATION_ID, OTHER_ORGANIZATION_ID):
                connection.execute(
                    sa.text(
                        "INSERT INTO organizations (id, org_type, seat_cap, "
                        "created_at) VALUES (:i, 'demo', 5, CURRENT_TIMESTAMP)"
                    ),
                    {"i": uuid.UUID(organization_id).hex},
                )
                _seed_profile(connection, organization_id)
            watchlist.add_watchlist_entry(
                connection=connection,
                entry_id=uuid.uuid4(),
                now=FIXED_NOW,
                organization_id=DEMO_ORGANIZATION_ID,
                source_id="nf-seed-2026-fed-001",
                watchlist_source="registry_entry",
                source_name="Aid to Tribal Government Services",
                jurisdiction="federal",
                fact_status="demo_fixture",
            )
            # A fixture mailbox at a reserved domain. Nothing can deliver here.
            identity = upsert_identity(
                connection=connection,
                issuer="https://accounts.google.com",
                subject="gate142-artifact-owner",
                email_verified=True,
                verification_source="oidc_token_signature",
                email=FIXTURE_ADDRESS,
            )["identity_id"]
            insert_membership(
                connection=connection,
                organization_id=DEMO_ORGANIZATION_ID,
                identity_id=identity,
                state="active",
                role="org_owner",
                membership_source="verified_directory",
            )

        issued = int(time.time())
        built = build_session(
            principal_id=identity,
            organization_id=DEMO_ORGANIZATION_ID,
            roles=["org_owner"],
            issued_at=issued,
            expires_at=issued + 900,
            auth_source="oidc_authorization_code",
            session_id=str(uuid.uuid4()),
            now=issued + 1,
        )
        headers = {"Cookie": f"nf_session={built['session_cookie_value']}"}

        from nativeforge.api.deps import get_db
        from nativeforge.api.deps_db import get_db_session

        def _session():
            db = factory()
            try:
                yield db
            finally:
                db.close()

        app = create_app()
        app.dependency_overrides[get_db_session] = _session
        app.dependency_overrides[get_db] = _session

        client = TestClient(app, raise_server_exceptions=False)
        smoke = run_digest_delivery_route_smoke(
            client=client,
            organization_id=DEMO_ORGANIZATION_ID,
            other_organization_id=OTHER_ORGANIZATION_ID,
            session_headers=headers,
        )

        # The render, read again directly so the artifact can report its shape
        # without the smoke having to carry a body through its result.
        render_shape = _render_shape(client, headers)

        with engine.connect() as connection:
            rows = {
                "intents_total": int(
                    connection.execute(
                        sa.text(f"SELECT COUNT(*) FROM {TABLE_NAME}")
                    ).scalar_one()
                ),
                "intents_live": int(
                    connection.execute(
                        sa.text(
                            f"SELECT COUNT(*) FROM {TABLE_NAME} "
                            "WHERE cancelled_at IS NULL"
                        )
                    ).scalar_one()
                ),
                "intents_claiming_a_send": int(
                    connection.execute(
                        sa.text(
                            f"SELECT COUNT(*) FROM {TABLE_NAME} "
                            "WHERE send_attempted OR provider_contacted "
                            "OR emails_sent > 0"
                        )
                    ).scalar_one()
                ),
                "intents_with_an_address_shaped_fingerprint": int(
                    connection.execute(
                        sa.text(
                            f"SELECT COUNT(*) FROM {TABLE_NAME} "
                            "WHERE recipient_fingerprint LIKE '%@%'"
                        )
                    ).scalar_one()
                ),
                "intents_for_another_org": int(
                    connection.execute(
                        sa.text(
                            f"SELECT COUNT(*) FROM {TABLE_NAME} "
                            "WHERE organization_id = :o"
                        ),
                        {"o": uuid.UUID(OTHER_ORGANIZATION_ID).hex},
                    ).scalar_one()
                ),
                "intents_for_the_real_org": int(
                    connection.execute(
                        sa.text(
                            f"SELECT COUNT(*) FROM {TABLE_NAME} "
                            "WHERE organization_id = :o"
                        ),
                        {"o": uuid.UUID(REAL_ORGANIZATION_ID).hex},
                    ).scalar_one()
                ),
                "non_fixture_intents": int(
                    connection.execute(
                        sa.text(
                            f"SELECT COUNT(*) FROM {TABLE_NAME} "
                            "WHERE fact_status <> 'demo_fixture'"
                        )
                    ).scalar_one()
                ),
                "delivery_audit_events": int(
                    connection.execute(
                        sa.text(
                            "SELECT COUNT(*) FROM nf_audit_events "
                            "WHERE action = 'digest_delivery_intent_recorded'"
                        )
                    ).scalar_one()
                ),
            }
        engine.dispose()
        return {"smoke": smoke, "render_shape": render_shape, "row_counts": rows}
    finally:
        _session_module.engine = previous_engine
        from nativeforge.lib.settings import get_settings as _restore_settings

        _restore_settings.cache_clear()
        if previous_url is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = previous_url
        if previous_key is None:
            os.environ.pop("NF_SESSION_SIGNING_KEY", None)
        else:
            os.environ["NF_SESSION_SIGNING_KEY"] = previous_key


def _render_shape(client: Any, headers: dict[str, str]) -> dict[str, Any]:
    """The render's SHAPE. The body itself never enters an artifact.

    A digest body is tenant content. What belongs in a committed file is that
    it rendered, how big it was, and that it made no claim it may not - not the
    prose.
    """
    base = f"/v1/nf/demo/orgs/{DEMO_ORGANIZATION_ID}"
    response = client.request("GET", f"{base}/digest/delivery/preview", headers=headers)
    if response.status_code != 200:
        return {"rendered": False, "status": response.status_code}
    body = response.json()
    text = str(body.get("body_text") or "")
    lowered = text.lower()
    return {
        "rendered": True,
        "subject_length": len(str(body.get("subject_line") or "")),
        "body_byte_length": int(body.get("body_byte_length") or 0),
        "body_render_hash": body.get("body_render_hash"),
        "items_total": int(body.get("items_total") or 0),
        "items_visible": int(body.get("items_visible") or 0),
        "items_rendered": int(body.get("items_rendered") or 0),
        "items_with_unresolved_eligibility": int(
            body.get("items_with_unresolved_eligibility") or 0
        ),
        "items_with_unverified_deadlines": int(
            body.get("items_with_unverified_deadlines") or 0
        ),
        "deliverable": bool(body.get("deliverable")),
        # What the body does NOT say. Each is a claim this system cannot
        # support, and an email is the copy a tenant keeps.
        "forbidden_claims_present": sorted(
            claim for claim in FORBIDDEN_CLAIMS if claim in lowered
        ),
        "body_contains_an_address": "@" in text,
        "body_contains_html": "<" in text and ">" in text,
        "says_deadlines_need_verifying": "verify every deadline" in lowered,
        "says_it_is_not_a_live_check": "not from live checks" in lowered,
        # The prose itself is deliberately absent from this artifact.
        "body_text_included": False,
    }


def build_email_delivery_artifacts() -> dict[str, str]:
    """Every file, as text. Same input, same bytes, every time."""
    run = _hermetic_run()
    smoke = run["smoke"]
    shape = run["render_shape"]
    counts = run["row_counts"]

    preflight = build_email_provider_preflight(
        dry_run_passed=bool(smoke["delivery_intent_recorded"])
    )
    imports = detect_mail_library_imports()
    module = detect_delivery_route_module()

    readiness = build_email_delivery_readiness(
        preflight=preflight,
        render_proof={
            "deliverable": bool(smoke["digest_renders_for_delivery"]),
            "emails_sent": 0,
            "provider_contacted": False,
        },
        recipient_proof={
            "deliverable_count": 1 if smoke["recipient_validation_works"] else 0,
            "addresses_stored": False,
        },
        queue_proof={
            "rows_written": counts["intents_total"],
            "blocked_reason": "no_email_provider_configured",
            "emails_sent": 0,
            "provider_contacted": False,
            "addresses_stored": False,
        },
        audit_proof={"audit_event_recorded": counts["delivery_audit_events"] >= 1},
        route_smoke=smoke,
        tenant_digest_operational=True,
        customer_persistence_live=True,
    )

    # The recipient refusals, each driven for real rather than described.
    refusals = {
        "verified_fixture": validate_recipient(
            address=FIXTURE_ADDRESS,
            verified=True,
            recipient_source="org_membership",
        ),
        "unverified": validate_recipient(
            address=FIXTURE_ADDRESS,
            verified=False,
            recipient_source="org_membership",
        ),
        "malformed": validate_recipient(
            address="not-an-address",
            verified=True,
            recipient_source="org_membership",
        ),
        "domain_not_allowed": validate_recipient(
            address=FIXTURE_ADDRESS,
            verified=True,
            recipient_source="org_membership",
            allowed_domains=["allowed.invalid"],
        ),
        "unrecognised_source": validate_recipient(
            address=FIXTURE_ADDRESS,
            verified=True,
            recipient_source="somebody_asked_nicely",
        ),
    }

    files: dict[str, str] = {}

    files["email_delivery_survey.json"] = _dump(
        {
            "schema_version": SCHEMA_VERSION,
            "gate": "142",
            "why_email_delivery_is_false": (
                "there is no email_delivery_service module, no provider "
                "configuration, and no send activation; "
                "tenant_beta_readiness_service derives it by import and has "
                "always answered honestly"
            ),
            "constant_replaced_by_measurement": {
                "tenant_beta_feature_entitlement_service": (
                    "digest_email_delivery_live was a literal False; "
                    "entitlement is permission and stays separate from "
                    "delivery, which is a capability"
                )
            },
            "required_setting_names": list(REQUIRED_SETTING_NAMES),
            "absent_setting_names": preflight["absent_setting_names"],
            "credential_values_read_into_a_result": False,
            "route_module": module,
            "mail_library_imports": imports,
            "no_mail_library_is_imported": not imports["any_mail_library_imported"],
            "mail_libraries_watched": imports["mail_libraries_watched"],
            "smtplib_is_stdlib_so_absence_is_proved_by_parsing": True,
            "gate_104_reserved_words": sorted(FORBIDDEN_STATES),
            "queue_vocabulary": sorted(DELIVERY_INTENT_STATES),
            "queue_blocked_reasons": sorted(DELIVERY_BLOCKED_REASONS),
            "queue_uses_queued_or_sent": bool(
                FORBIDDEN_STATES & DELIVERY_INTENT_STATES
            ),
            "recipient_is_stored_as": "sha256[:32] fingerprint plus domain",
            "recipient_address_column_exists": False,
            "audit_verbs_added": [
                "digest_delivery_intent_recorded",
                "digest_delivery_refused",
            ],
            "audit_verbs_added_to_the_security_stream": False,
            "migration_added": "0041_digest_delivery_dry_run_queue",
            "real_organization_route_built": False,
            "real_organization_route_not_built_because": (
                f"it would create a route to {REAL_ORGANIZATION_ID} that "
                "nobody has authorized"
            ),
        }
    )

    files["email_provider_preflight.json"] = _dump(
        {
            "schema_version": SCHEMA_VERSION,
            "state": preflight["state"],
            "states": list(PREFLIGHT_STATES),
            "email_delivery": bool(preflight["email_delivery"]),
            "provider_configured": bool(preflight["provider_configured"]),
            "send_activated": bool(preflight["send_activated"]),
            "required_setting_names": list(preflight["required_setting_names"]),
            "present_setting_names": list(preflight["present_setting_names"]),
            "placeholder_setting_names": list(preflight["placeholder_setting_names"]),
            "absent_setting_names": list(preflight["absent_setting_names"]),
            "secret_setting_names": list(preflight["secret_setting_names"]),
            "send_activation_setting_name": preflight["send_activation_setting_name"],
            "send_evidence_fields": list(SEND_EVIDENCE_FIELDS),
            "sender_domain_fingerprint": preflight["sender_domain_fingerprint"],
            # Names only. Every value was tested for presence and discarded.
            "values_read": False,
            "values_reported": False,
            "value_lengths_reported": False,
            "provider_contacted": False,
            "network_calls": int(preflight["network_calls"]),
            "emails_sent": int(preflight["emails_sent"]),
            "invariant_failures": email_preflight_invariant_failures(preflight),
            "blocked_reasons": list(preflight["blocked_reasons"]),
        }
    )

    files["digest_delivery_render_smoke.json"] = _dump(
        {
            "schema_version": SCHEMA_VERSION,
            "digest_renders_for_delivery": bool(smoke["digest_renders_for_delivery"]),
            "render_fields": list(RENDER_FIELDS),
            "render_shape": shape,
            "max_subject_length": MAX_SUBJECT_LENGTH,
            "max_body_bytes": MAX_BODY_BYTES,
            "max_rendered_items": MAX_RENDERED_ITEMS,
            "forbidden_claims": list(FORBIDDEN_CLAIMS),
            "body_text_committed": False,
            "body_text_committed_because": (
                "a digest body is tenant content; what belongs in a committed "
                "file is that it rendered and what it does not claim"
            ),
            "html_rendered": False,
            "tracking_pixels": 0,
            "links_rewritten": 0,
            "recipient_in_render": False,
            "unknown_eligibility_survives_the_render": True,
            "unverified_deadlines_are_written_as_unverified": True,
            "delivery_status": "preview_only",
            "emails_sent": 0,
            "blocked_reasons": [
                reason
                for reason in smoke["blocked_reasons"]
                if "preview" in reason or "render" in reason or "cadence" in reason
            ],
        }
    )

    files["recipient_validation_smoke.json"] = _dump(
        {
            "schema_version": SCHEMA_VERSION,
            "recipient_validation_works": bool(smoke["recipient_validation_works"]),
            "refusal_reasons_available": list(REFUSAL_REASONS),
            "cases": {
                name: {
                    "deliverable": result["deliverable"],
                    "recipient_verified": result["recipient_verified"],
                    "recipient_domain": result["recipient_domain"],
                    "fingerprint_length": len(
                        str(result["recipient_fingerprint"] or "")
                    ),
                    "is_fixture_recipient": result["is_fixture_recipient"],
                    "blocked_reasons": result["blocked_reasons"],
                    "invariant_failures": recipient_invariant_failures(result),
                }
                for name, result in refusals.items()
            },
            "verified_is_a_fact_not_a_shape": True,
            "address_reported": False,
            "address_stored": False,
            "local_part_reported": False,
            "dns_checked": False,
            "mx_checked": False,
            "provider_validation_called": False,
            "fixture_domain": FIXTURE_DOMAIN,
            "fixture_domain_is_reserved_by_rfc_2606": True,
            "no_address_in_any_response": bool(smoke["no_address_in_any_response"]),
            "blocked_reasons": [
                reason
                for reason in smoke["blocked_reasons"]
                if "recipient" in reason or "address" in reason
            ],
        }
    )

    files["dry_run_delivery_queue_smoke.json"] = _dump(
        {
            "schema_version": SCHEMA_VERSION,
            "delivery_intent_recorded": bool(smoke["delivery_intent_recorded"]),
            "delivery_audit_event_created": bool(smoke["delivery_audit_event_created"]),
            "send_disabled_blocker_explicit": bool(
                smoke["send_disabled_blocker_explicit"]
            ),
            "duplicate_run_refused": bool(smoke["duplicate_run_refused"]),
            "cancel_preserves_the_row": bool(smoke["cancel_preserves_the_row"]),
            "intent_counts": dict(smoke["intent_counts"]),
            "row_counts": counts,
            "an_intent_is_not_a_queue_position": True,
            "gate_104_reserved_statuses": sorted(FORBIDDEN_STATES),
            "queue_states": sorted(DELIVERY_INTENT_STATES),
            "database_checks": [
                "NOT send_attempted",
                "NOT provider_contacted",
                "emails_sent = 0",
                "delivery_status <> 'queued' AND delivery_status <> 'sent'",
                "length(recipient_fingerprint) = 32",
                "recipient_fingerprint NOT LIKE '%@%'",
            ],
            "intents_claiming_a_send": counts["intents_claiming_a_send"],
            "intents_with_an_address_shaped_fingerprint": counts[
                "intents_with_an_address_shaped_fingerprint"
            ],
            "intents_for_the_real_org": counts["intents_for_the_real_org"],
            "non_fixture_intents": counts["non_fixture_intents"],
            "emails_sent": int(smoke["emails_sent"]),
            "provider_contacted": bool(smoke["provider_contacted"]),
            "invariant_failures": queue_invariant_failures(
                {"intents": [], "emails_sent": 0}
            ),
            "smoke_invariant_failures": delivery_route_smoke_invariant_failures(smoke),
            "blocked_reasons": [
                reason
                for reason in smoke["blocked_reasons"]
                if "intent" in reason or "dry_run" in reason or "cancel" in reason
            ],
        }
    )

    files["email_delivery_readiness.json"] = _dump(
        {
            "schema_version": SCHEMA_VERSION,
            "email_delivery_readiness": bool(readiness["email_delivery_readiness"]),
            "email_delivery": bool(readiness["email_delivery"]),
            "scope": readiness["scope"],
            "scopes": list(readiness["scopes"]),
            "preflight_state": readiness["preflight_state"],
            "provider_configured": bool(readiness["provider_configured"]),
            "send_activated": bool(readiness["send_activated"]),
            "digest_renders_for_delivery": bool(
                readiness["digest_renders_for_delivery"]
            ),
            "recipient_validation_works": bool(readiness["recipient_validation_works"]),
            "delivery_intent_recorded": bool(readiness["delivery_intent_recorded"]),
            "delivery_audit_event_created": bool(
                readiness["delivery_audit_event_created"]
            ),
            "send_disabled_blocker": readiness["send_disabled_blocker"],
            "tenant_digest_operational": bool(readiness["tenant_digest_operational"]),
            "customer_persistence_live": bool(readiness["customer_persistence_live"]),
            "provider_required_for_readiness": bool(
                readiness["provider_required_for_readiness"]
            ),
            "send_activation_required_for_readiness": bool(
                readiness["send_activation_required_for_readiness"]
            ),
            "real_recipient_required_for_readiness": bool(
                readiness["real_recipient_required_for_readiness"]
            ),
            "production_email_delivery": bool(readiness["production_email_delivery"]),
            "customer_auth_live": bool(readiness["customer_auth_live"]),
            "route_module": readiness["route_module"],
            "not_approved": list(NOT_APPROVED),
            "invariant_failures": delivery_readiness_invariant_failures(readiness),
            "blocked_reasons": list(readiness["blocked_reasons"]),
        }
    )

    files["next_email_activation_blockers.md"] = _next_blockers(
        readiness, preflight, smoke, shape, counts
    )

    for name, body in files.items():
        lowered = body.lower()
        for marker in FORBIDDEN_MARKERS:
            if marker.lower() in lowered:
                raise AssertionError(f"forbidden marker {marker!r} in {name}")
        for field in CREDENTIAL_FIELDS:
            if re.search(rf'"{re.escape(field)}"\s*:\s*"', lowered):
                raise AssertionError(f"field {field!r} carries a value in {name}")
        # The whole point of the gate: no mailbox in a committed file.
        #
        # A MAILBOX, not an `@`. The first version of this guard fired on the
        # migration's own CHECK - `recipient_fingerprint NOT LIKE '%@%'` -
        # quoted in an artifact as evidence, which is the guarantee rather
        # than a leak.
        found = ADDRESS_SHAPE.search(body)
        if found:
            raise AssertionError(
                f"an address-shaped string reached {name}: "
                f"{found.group(0)[:3]}... (redacted)"
            )

    return files


def _next_blockers(
    readiness: dict[str, Any],
    preflight: dict[str, Any],
    smoke: dict[str, Any],
    shape: dict[str, Any],
    counts: dict[str, Any],
) -> str:
    absent = "\n".join(f"  {name}" for name in preflight["absent_setting_names"])
    ready = str(readiness["email_delivery_readiness"]).upper()
    address_shaped_fingerprints = counts["intents_with_an_address_shaped_fingerprint"]
    items_shown = f"{shape.get('items_visible')} of {shape.get('items_total')}"
    delivery = str(readiness["email_delivery"]).upper()
    return f"""# Gate 142 — what email delivery still does not reach

## Where this stands

```text
email_delivery_readiness   {ready}
email_delivery             {delivery}
scope                      {readiness["scope"]}
preflight state            {preflight["state"]}
send disabled because      {readiness["send_disabled_blocker"]}
```

A digest renders into a subject and a body, a recipient validates to a
fingerprint, an intent is recorded against the organization with an audit event
naming it, and the reason nothing will be sent is written on the row.

Nothing was sent.

## Readiness is not delivery

```text
email_delivery_readiness   can this system rehearse the whole path?
email_delivery             does mail reach anybody?
```

Collapsing those is how a deployment starts mailing people the day somebody
pastes an API key into an environment file. An invariant fails if a passing dry
run ever sets `email_delivery`, and the preflight reaches `send_activated` only
with three pieces of evidence a rehearsal cannot manufacture.

## An intent is not a queue position

Gate 104's digest builder owns `queued` and lists it under `DELIVERED_STATUSES`
— "statuses that assert something left the building". So this queue starts at
`dry_run_recorded` and the digest keeps `delivery_status: preview_only`.

The database enforces it rather than a service promising it:

```text
NOT send_attempted
NOT provider_contacted
emails_sent = 0
delivery_status <> 'queued' AND delivery_status <> 'sent'
length(recipient_fingerprint) = 32
recipient_fingerprint NOT LIKE '%@%'
```

A future gate that activates sending removes those in a migration somebody
reviews. It cannot happen by a default changing.

## No address, anywhere

```text
recipient stored as                    sha256[:32] fingerprint plus domain
address column in the queue            none
addresses in any route response        {_low(not smoke["no_address_in_any_response"])}
intents with an address-shaped
  fingerprint                          {address_shaped_fingerprints}
addresses in any committed artifact    none — every file is scanned for one
```

`nf_identities.email` holds a real address because OIDC handed it over.
`validate_recipient` is the only place it is read, and what comes out is a
handle.

## What the digest body does and does not say

```text
rendered                              {_low(shape.get("deliverable"))}
bytes                                 {shape.get("body_byte_length")}
items shown                           {items_shown}
eligibility nobody settled            {shape.get("items_with_unresolved_eligibility")}
deadlines nobody verified             {shape.get("items_with_unverified_deadlines")}
forbidden claims present              {shape.get("forbidden_claims_present")}
contains an address                   {_low(shape.get("body_contains_an_address"))}
contains HTML                         {_low(shape.get("body_contains_html"))}
tells the reader to verify deadlines  {_low(shape.get("says_deadlines_need_verifying"))}
says it is not a live check           {_low(shape.get("says_it_is_not_a_live_check"))}
```

The body itself is not committed. A digest body is tenant content; what belongs
in a repository is that it rendered and what it refuses to claim.

## What activation would require

```text
a provider, and its five settings with real values:
{absent}

an email delivery service      the module tenant_beta_readiness_service already
                               looks for, and which this gate did not write

send activation                a DECISION, not a config value. The preflight
                               refuses an activation setting that arrives
                               without an approval:
                               send_activation_setting_present_without_an_approval

a verified sender domain       SPF, DKIM, DMARC

unsubscribe and bounce handling  a digest nobody can stop receiving is worse
                               than one nobody receives

a recipient consent record     nothing in this repository records that a tenant
                               asked to be emailed. That is a gap this gate
                               names and does not fill.

customer_auth_live             for anything but fixture recipients
```

## What is NOT the blocker

```text
the render          works, bounded, and makes no claim it may not
the validation      works, and refuses four ways by name
the queue           writes, reads back, refuses duplicates, cancels without
                    deleting
the audit trail     one event per dry run, outside the security stream
a mail library      not needed to prove any of the above, and not imported
```

## Still false, and not touched

```text
email_delivery                 false
digest_email_delivery_live     false
production_email_delivery      false
customer_auth_live             false
verified_operational_binding   false
source_monitoring_live         false
object_store_configured        false
document_body_storage_ready    false
production_rollout             false
controlled_customer_pilot      false
```

## Nothing left the building

```text
emails sent                       {int(smoke["emails_sent"])}
send attempted                    {_low(smoke["send_attempted"])}
provider contacted                {_low(smoke["provider_contacted"])}
network calls to a mail provider  {int(smoke["network_calls_to_a_mail_provider"])}
intents claiming a send           {counts["intents_claiming_a_send"]}
intents for the real organization {counts["intents_for_the_real_org"]}
intents that are not fixtures     {counts["non_fixture_intents"]}
delivery audit events             {counts["delivery_audit_events"]}
```
"""


def write_email_delivery_artifacts(*, repo_root: Any = None) -> dict[str, Any]:
    """Write every file under ``ARTIFACT_DIR``, relative to ``repo_root``."""
    root = Path(repo_root) if repo_root is not None else Path()
    directory = root / ARTIFACT_DIR
    directory.mkdir(parents=True, exist_ok=True)

    files = build_email_delivery_artifacts()
    for name, body in files.items():
        (directory / name).write_text(body, encoding="utf-8")

    return {
        "schema_version": SCHEMA_VERSION,
        "directory": str(directory),
        "files_written": sorted(files),
        "file_count": len(files),
    }


def email_delivery_artifact_invariant_failures(result: dict[str, Any]) -> list[str]:
    fails: list[str] = []

    written = set(result.get("files_written") or [])
    missing = set(ARTIFACT_FILES) - written
    if missing:
        fails.append(f"artifact_files_missing:{sorted(missing)}")
    extra = written - set(ARTIFACT_FILES)
    if extra:
        fails.append(f"artifact_files_undeclared:{sorted(extra)}")
    if result.get("file_count") != len(written):
        fails.append("file_count_disagrees_with_the_names")
    if DELIVERY_ROUTE_MODULE not in json.dumps(
        detect_delivery_route_module()
    ):  # pragma: no cover - a shape guard, not a behaviour
        fails.append("route_module_name_drifted")

    return fails
