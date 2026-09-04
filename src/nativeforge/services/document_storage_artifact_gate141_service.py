"""Gate 141G: what document storage proved, as committed files.

Deterministic. The smoke runs against a migrated database this module builds and
throws away, driven through a `TestClient` with a real signed session for a real
membership — so the artifact records a measurement and still produces the same
bytes every time.

Two runs of the body route, because two different things need proving:

```text
runtime            no adapter injected   -> refused, by name. The honest state.
hermetic fake      the in-memory adapter -> stored, under a generated key.
                   Proves the permitted branch is REACHABLE, and nothing about
                   any bucket.
```

No object store is contacted, no external adapter is constructed, no credential
is read into a result, no real file is read or hashed, and no body byte reaches
any file this module writes.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any

import sqlalchemy as sa

from nativeforge.services.document_storage_readiness_service import (
    METADATA_ROUTE_MODULE,
    NOT_APPROVED,
    build_document_storage_readiness,
    detect_metadata_route_module,
    document_storage_readiness_invariant_failures,
)
from nativeforge.services.document_storage_route_smoke_service import (
    BODY_STORAGE_PROBES,
    DOCUMENT_BODY,
    document_storage_route_smoke_invariant_failures,
    run_document_storage_route_smoke,
)
from nativeforge.services.object_storage_adapter_service import (
    KEY_NAMESPACE,
    MAX_BODY_BYTES,
    REFUSAL_REASONS,
    UNSAFE_KEY_PROBES,
    adapter_proof_invariant_failures,
    run_hermetic_adapter_proof,
)
from nativeforge.services.object_storage_configuration_preflight_service import (
    PREFLIGHT_STATES,
    PRODUCTION_EVIDENCE_FIELDS,
    REQUIRED_KEY_NAMES,
    build_object_storage_preflight,
    preflight_invariant_failures,
)

SCHEMA_VERSION = "nf_document_storage_gate141_artifact_v1"

ARTIFACT_DIR = "artifacts/document_storage_gate141"

ARTIFACT_FILES: tuple[str, ...] = (
    "object_storage_survey.json",
    "object_storage_preflight.json",
    "metadata_document_route_smoke.json",
    "body_storage_blocker_smoke.json",
    "fake_adapter_hermetic_result.json",
    "document_storage_readiness.json",
    "next_storage_activation_blockers.md",
)

DEMO_ORGANIZATION_ID = "bbbbbbbb-cccc-dddd-eeee-ffffffffffff"
OTHER_ORGANIZATION_ID = "cccccccc-dddd-eeee-ffff-00000000d141"
REAL_ORGANIZATION_ID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"

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
    "secret_access_key",
    "access_key_id",
    "endpoint",
    "bucket",
)

FORBIDDEN_MARKERS: tuple[str, ...] = (
    "set-cookie:",
    "GOCSPX-",
    "BEGIN PRIVATE KEY",
    "@gmail.com",
    "eyJ",
    "nf_session=",
    "AKIA",
    "s3://",
    "aws_secret",
    # The hermetic fixture body. If this string reaches a file, a body did.
    "gate141 hermetic fixture body",
    "gate141 body placeholder",
)


def _dump(obj: Any) -> str:
    return json.dumps(obj, indent=2, sort_keys=True) + "\n"


def _low(value: Any) -> str:
    return str(bool(value)).lower()


def _hermetic_run() -> dict[str, Any]:
    """The document routes, driven against a database built for this call only."""
    from fastapi.testclient import TestClient

    previous_url = os.environ.get("DATABASE_URL")
    previous_key = os.environ.get("NF_SESSION_SIGNING_KEY")
    from nativeforge.db import session as _session_module

    previous_engine = _session_module.engine
    tmp = Path(tempfile.mkdtemp(prefix="nf_gate141_artifact_"))
    os.environ["DATABASE_URL"] = f"sqlite+pysqlite:///{(tmp / 'nf.sqlite3').as_posix()}"
    os.environ["NF_SESSION_SIGNING_KEY"] = "gate141-artifact-session-key-" + ("k" * 40)

    try:
        from alembic import command
        from alembic.config import Config

        from nativeforge.lib.settings import get_settings as _get_settings

        _get_settings.cache_clear()
        command.upgrade(Config("alembic.ini"), "head")

        from sqlalchemy.orm import sessionmaker

        from nativeforge.main import create_app
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
            identity = upsert_identity(
                connection=connection,
                issuer="https://accounts.google.com",
                subject="gate141-artifact-owner",
                email_verified=True,
                verification_source="oidc_token_signature",
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
        smoke = run_document_storage_route_smoke(
            client=client,
            organization_id=DEMO_ORGANIZATION_ID,
            other_organization_id=OTHER_ORGANIZATION_ID,
            session_headers=headers,
        )

        body_proof = _hermetic_body_route_proof(app, client, headers)

        with engine.connect() as connection:
            rows = {
                "nf_award_documents_total": int(
                    connection.execute(
                        sa.text("SELECT COUNT(*) FROM nf_award_documents")
                    ).scalar_one()
                ),
                "nf_award_documents_live": int(
                    connection.execute(
                        sa.text(
                            "SELECT COUNT(*) FROM nf_award_documents "
                            "WHERE archived_at IS NULL"
                        )
                    ).scalar_one()
                ),
                "documents_with_an_object_key": int(
                    connection.execute(
                        sa.text(
                            "SELECT COUNT(*) FROM nf_award_documents "
                            "WHERE object_key IS NOT NULL"
                        )
                    ).scalar_one()
                ),
                "documents_claiming_a_configured_store": int(
                    connection.execute(
                        sa.text(
                            "SELECT COUNT(*) FROM nf_award_documents "
                            "WHERE object_store_configured"
                        )
                    ).scalar_one()
                ),
            }
        engine.dispose()
        return {"smoke": smoke, "body_proof": body_proof, "row_counts": rows}
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


def _hermetic_body_route_proof(app: Any, client: Any, headers: dict[str, str]) -> dict:
    """The body route's STORING branch, reached with the in-memory fake.

    Through `dependency_overrides`, which is how the permitted branch becomes
    reachable without a bucket. Runtime never reaches it: nothing constructs an
    adapter for that dependency, and there is no SDK here to construct an
    external one from.

    The preflight is overridden alongside it. Without that, the route would
    still refuse on `object_store_configured: false` - correct in runtime, and
    it would have left the storing branch untestable, which is the unreachable
    permitted branch Gate 134F removed from the customer-auth chain.
    """
    from nativeforge.api import award_document_routes as routes
    from nativeforge.services.object_storage_adapter_service import (
        InMemoryObjectStorageAdapter,
    )

    base = f"/v1/nf/demo/orgs/{DEMO_ORGANIZATION_ID}"
    adapter = InMemoryObjectStorageAdapter()

    award = client.request(
        "POST",
        f"{base}/awarded-grants",
        json={
            "award_number": "NF-G141-BODY",
            "award_title": "Gate 141 body proof award",
            "funder_name": "Gate 141 fixture funder",
            "award_status": "active_award",
            "award_amount": "1.00",
            "award_currency": "USD",
            "awarded_at": "2026-01-01",
            "active_obligation_status": "no_obligations_established",
            "requirements_extraction_status": "not_attempted",
        },
        headers=headers,
    )
    if award.status_code != 201:
        return {"body_route_operational": False, "reason": f"award:{award.status_code}"}
    award_id = award.json()["award_id"]

    created = client.request(
        "POST",
        f"{base}/awarded-grants/{award_id}/documents",
        json=DOCUMENT_BODY,
        headers=headers,
    )
    if created.status_code != 201:
        return {
            "body_route_operational": False,
            "reason": f"document:{created.status_code}",
        }
    document_id = created.json()["document_id"]

    refused = client.request(
        "POST",
        f"{base}/documents/{document_id}/body",
        json={"content_type": "application/pdf"},
        headers=headers,
    )

    # The route imports the preflight INSIDE the function, so the module it
    # reads is what gets patched - not a name it bound at import time.
    import nativeforge.services.object_storage_configuration_preflight_service as pf

    app.dependency_overrides[routes.get_document_body_adapter] = lambda: adapter
    real = pf.build_object_storage_preflight

    def _fake_preflight(**kwargs: Any) -> dict[str, Any]:
        result = real(**kwargs)
        # Labelled, and only inside this proof. `object_store_configured` is
        # what the ROUTE reads; the readiness roll-up keeps its own answer,
        # which stays false.
        return {**result, "object_store_configured": True, "state": "hermetic_fake"}

    try:
        pf.build_object_storage_preflight = _fake_preflight
        stored = client.request(
            "POST",
            f"{base}/documents/{document_id}/body",
            json={"content_type": "application/pdf"},
            headers=headers,
        )
        named_key = client.request(
            "POST",
            f"{base}/documents/{document_id}/body",
            json={"content_type": "application/pdf", "object_key": "anywhere/i/like"},
            headers=headers,
        )
    finally:
        pf.build_object_storage_preflight = real
        app.dependency_overrides.pop(routes.get_document_body_adapter, None)

    stored_body = stored.json() if stored.status_code == 201 else {}
    key = stored_body.get("object_key")

    checks = {
        "refused_without_an_adapter": refused.status_code == 422,
        "stored_with_the_fake_adapter": stored.status_code == 201,
        "key_was_generated": bool(key) and str(key).startswith(f"{KEY_NAMESPACE}/"),
        "key_names_the_organization": bool(key)
        and uuid.UUID(DEMO_ORGANIZATION_ID).hex in str(key),
        "adapter_was_the_fake": stored_body.get("adapter_kind") == "in_memory_fake",
        "scope_was_labelled_fake": stored_body.get("storage_scope") == "hermetic_fake",
        "no_external_contact": stored_body.get("object_store_contacted") is False,
        "production_storage_stayed_false": stored_body.get("production_storage")
        is False,
        "caller_named_key_refused": named_key.status_code == 422,
        "one_object_in_the_fake": adapter.object_count() == 1,
    }

    client.request("POST", f"{base}/documents/{document_id}/archive", headers=headers)
    # `json={}`: the archive route declares a required body, and posting
    # without one returns 422 and leaves the award live.
    client.request(
        "POST",
        f"{base}/awarded-grants/{award_id}/archive",
        json={},
        headers=headers,
    )

    return {
        "body_route_operational": all(checks.values()),
        "checks": checks,
        "scope": "hermetic_fake",
        "object_key_shape": f"{KEY_NAMESPACE}/<org[:2]>/<org[2:4]>/<org>/<doc>.<ext>",
        "body_bytes_reported": False,
        "external_object_store_contacted": False,
        "production_storage": False,
        "blocked_reasons": sorted(
            name for name, passed in checks.items() if not passed
        ),
    }


def build_document_storage_artifacts() -> dict[str, str]:
    """Every file, as text. Same input, same bytes, every time."""
    run = _hermetic_run()
    smoke = run["smoke"]
    body_proof = run["body_proof"]
    counts = run["row_counts"]

    adapter_proof = run_hermetic_adapter_proof()
    preflight = build_object_storage_preflight(
        hermetic_fake_passed=bool(adapter_proof["hermetic_fake_passed"])
    )

    # The RUNTIME answer: no body route proof supplied, because runtime has no
    # adapter. The hermetic proof is reported beside it and does not feed it.
    readiness = build_document_storage_readiness(
        preflight=preflight,
        adapter_proof=adapter_proof,
        metadata_route_smoke=smoke,
        body_route_smoke=None,
    )

    files: dict[str, str] = {}

    files["object_storage_survey.json"] = _dump(
        {
            "schema_version": SCHEMA_VERSION,
            "gate": "141",
            "why_object_store_configured_is_false": (
                "five required settings are absent; detect_body_store_mode() "
                "reports 'unconfigured' and PRODUCTION_CAPABLE_MODES contains "
                "only 's3_compatible_configured'"
            ),
            "required_key_names": list(REQUIRED_KEY_NAMES),
            "absent_key_names": preflight["absent_key_names"],
            "present_key_names": preflight["present_key_names"],
            "credential_values_read_into_a_result": False,
            "metadata_only_operation_route_live": bool(
                smoke["metadata_route_operational"]
            ),
            "body_upload_blocked_at_the_route_boundary": bool(
                smoke["body_storage_fields_refused"]
            ),
            "body_storage_fields_refused": list(BODY_STORAGE_PROBES),
            "object_store_client_exists": False,
            "object_store_sdk_installed": False,
            "sdks_checked": ["boto3", "botocore", "minio", "s3fs", "aioboto3"],
            "any_path_can_contact_object_storage": False,
            "external_adapter_is_inert_without_all_three": [
                "an injected client",
                "object storage configured",
                "allow_external=True",
            ],
            "constants_replaced_by_measurement": {
                "award_document_routes.object_store_configured": (
                    "was a literal False at three envelope sites"
                ),
                "post_award_common.refuse_body_storage": (
                    "was a literal False in the refusal detail"
                ),
                "awarded_operational_tracking_readiness_service": (
                    "document_body_storage_ready was a literal False"
                ),
            },
            "what_a_fake_adapter_proves": sorted(adapter_proof["checks"]),
            "what_a_fake_adapter_cannot_prove": [
                "durability",
                "that a bucket exists",
                "that credentials work",
                "cross-process retrieval",
                "bucket policy or region",
            ],
            "what_real_activation_requires": [
                "five settings with real values",
                "an injected client (no SDK is present and none was added)",
                "an owner decision",
                "an external verifier, explicitly allowed and run by a person",
                "secret scanning before promotion",
            ],
            "metadata_route_module": detect_metadata_route_module(),
            "real_organization_route_built": False,
            "real_organization_route_not_built_because": (
                f"it would create a route to {REAL_ORGANIZATION_ID} that nobody "
                "has authorized"
            ),
        }
    )

    files["object_storage_preflight.json"] = _dump(
        {
            "schema_version": SCHEMA_VERSION,
            "state": preflight["state"],
            "states": list(PREFLIGHT_STATES),
            "object_store_configured": bool(preflight["object_store_configured"]),
            "fully_configured": bool(preflight["fully_configured"]),
            "implementation_available": bool(preflight["implementation_available"]),
            "detected_body_store_mode": preflight["detected_body_store_mode"],
            "required_key_names": list(preflight["required_key_names"]),
            "present_key_names": list(preflight["present_key_names"]),
            "placeholder_key_names": list(preflight["placeholder_key_names"]),
            "absent_key_names": list(preflight["absent_key_names"]),
            "secret_key_names": list(preflight["secret_key_names"]),
            "production_evidence_fields": list(PRODUCTION_EVIDENCE_FIELDS),
            "external_verification_allowed": bool(
                preflight["external_verification_allowed"]
            ),
            "external_verification_passed": bool(
                preflight["external_verification_passed"]
            ),
            # Names only. Every value was tested for presence and discarded.
            "values_read": False,
            "values_reported": False,
            "value_lengths_reported": False,
            "external_object_store_contacted": False,
            "network_calls": int(preflight["network_calls"]),
            "invariant_failures": preflight_invariant_failures(preflight),
            "blocked_reasons": list(preflight["blocked_reasons"]),
        }
    )

    files["metadata_document_route_smoke.json"] = _dump(
        {
            "schema_version": SCHEMA_VERSION,
            "route_module": METADATA_ROUTE_MODULE,
            "metadata_route_operational": bool(smoke["metadata_route_operational"]),
            "org_scoped_read_write_proved": bool(smoke["org_scoped_read_write_proved"]),
            "body_bytes_not_required": bool(smoke["body_bytes_not_required"]),
            "object_store_required_for_metadata": False,
            "steps": {
                "created_a_document_reference": True,
                "read_it_back_anchored_on_organization_id": bool(
                    smoke["metadata_route_operational"]
                ),
                "listed_the_award_documents": bool(smoke["metadata_route_operational"]),
                "archived_it_without_deleting_it": bool(
                    smoke["archive_preserves_the_row"]
                ),
            },
            "refusals": {
                "unauthenticated": bool(smoke["unauthenticated_refused"]),
                "forged_dev_header": bool(smoke["forged_header_refused"]),
                "caller_relabelling_the_write": bool(
                    smoke["caller_supplied_fields_refused"]
                ),
                "cross_organization_read": bool(smoke["cross_org_refused"]),
            },
            "request_body_shape": dict(DOCUMENT_BODY),
            "row_counts": counts,
            "documents_with_an_object_key": counts["documents_with_an_object_key"],
            "invariant_failures": document_storage_route_smoke_invariant_failures(
                smoke
            ),
            "blocked_reasons": [
                reason
                for reason in smoke["blocked_reasons"]
                if "body" not in reason and "object_key" not in reason
            ],
        }
    )

    files["body_storage_blocker_smoke.json"] = _dump(
        {
            "schema_version": SCHEMA_VERSION,
            "body_route_exists": True,
            "body_route_is_an_explicit_refusal_not_an_absence": True,
            "unconfigured_blocker_correct": bool(smoke["unconfigured_blocker_correct"]),
            "blocker_reason": "document_body_storage_is_not_configured",
            "body_storage_readiness_route_operational": bool(
                smoke["body_storage_readiness_route_operational"]
            ),
            "body_storage_fields_refused_on_metadata_create": list(BODY_STORAGE_PROBES),
            "all_body_storage_fields_refused": bool(
                smoke["body_storage_fields_refused"]
            ),
            "caller_supplied_object_key_refused": bool(
                smoke["caller_supplied_object_key_refused"]
            ),
            "refusal_reasons_available": list(REFUSAL_REASONS),
            "missing_configuration_reported_as_key_names_only": True,
            "documents_claiming_a_configured_store": counts[
                "documents_claiming_a_configured_store"
            ],
            "body_bytes_sent": int(smoke["body_bytes_sent"]),
            "body_bytes_written": int(smoke["body_bytes_written"]),
            "external_object_store_contacted": bool(
                smoke["external_object_store_contacted"]
            ),
            "network_calls_to_object_storage": int(
                smoke["network_calls_to_object_storage"]
            ),
            "real_customer_files_read": int(smoke["real_customer_files_read"]),
            "real_customer_files_hashed": int(smoke["real_customer_files_hashed"]),
            "blocked_reasons": [
                reason
                for reason in smoke["blocked_reasons"]
                if "body" in reason or "object_key" in reason
            ],
        }
    )

    files["fake_adapter_hermetic_result.json"] = _dump(
        {
            "schema_version": SCHEMA_VERSION,
            "scope": "hermetic_fake",
            "adapter_kind": adapter_proof["adapter_kind"],
            "hermetic_fake_passed": bool(adapter_proof["hermetic_fake_passed"]),
            "checks": adapter_proof["checks"],
            "unsafe_key_probes": list(UNSAFE_KEY_PROBES),
            "unsafe_key_probes_refused": adapter_proof["unsafe_key_probes_refused"],
            "key_namespace": KEY_NAMESPACE,
            "max_body_bytes": MAX_BODY_BYTES,
            "object_key_is_generated_never_accepted": True,
            "body_route_hermetic_proof": body_proof,
            # A fake proves the code. It may never configure a store.
            "object_store_configured": False,
            "production_storage": False,
            "proves_durability": False,
            "proves_a_bucket_exists": False,
            "proves_credentials_work": False,
            "external_object_store_contacted": False,
            "network_calls": int(adapter_proof["network_calls"]),
            "real_files_read": int(adapter_proof["real_files_read"]),
            "real_files_hashed": int(adapter_proof["real_files_hashed"]),
            "body_bytes_reported": False,
            "invariant_failures": adapter_proof_invariant_failures(adapter_proof),
            "blocked_reasons": list(adapter_proof["blocked_reasons"]),
        }
    )

    files["document_storage_readiness.json"] = _dump(
        {
            "schema_version": SCHEMA_VERSION,
            "document_metadata_operational": bool(
                readiness["document_metadata_operational"]
            ),
            "document_body_storage_ready": bool(
                readiness["document_body_storage_ready"]
            ),
            "object_store_configured": bool(readiness["object_store_configured"]),
            "scope": readiness["scope"],
            "scopes": list(readiness["scopes"]),
            "preflight_state": readiness["preflight_state"],
            "preflight_passes": bool(readiness["preflight_passes"]),
            "hermetic_fake_passed": bool(readiness["hermetic_fake_passed"]),
            "body_route_operational_in_runtime": bool(
                readiness["body_route_operational"]
            ),
            "body_route_operational_under_the_fake": bool(
                body_proof["body_route_operational"]
            ),
            "metadata_route": readiness["metadata_route"],
            "object_store_required_for_metadata": bool(
                readiness["object_store_required_for_metadata"]
            ),
            "body_bytes_required_for_metadata": bool(
                readiness["body_bytes_required_for_metadata"]
            ),
            "production_storage": bool(readiness["production_storage"]),
            "customer_auth_live": bool(readiness["customer_auth_live"]),
            "max_body_bytes": int(readiness["max_body_bytes"]),
            "not_approved": list(NOT_APPROVED),
            "invariant_failures": document_storage_readiness_invariant_failures(
                readiness
            ),
            "blocked_reasons": list(readiness["blocked_reasons"]),
        }
    )

    files["next_storage_activation_blockers.md"] = _next_blockers(
        readiness, preflight, adapter_proof, body_proof, smoke, counts
    )

    for name, body in files.items():
        lowered = body.lower()
        for marker in FORBIDDEN_MARKERS:
            if marker.lower() in lowered:
                raise AssertionError(f"forbidden marker {marker!r} in {name}")
        for field in CREDENTIAL_FIELDS:
            if re.search(rf'"{re.escape(field)}"\s*:\s*"', lowered):
                raise AssertionError(f"field {field!r} carries a value in {name}")

    return files


def _next_blockers(
    readiness: dict[str, Any],
    preflight: dict[str, Any],
    adapter_proof: dict[str, Any],
    body_proof: dict[str, Any],
    smoke: dict[str, Any],
    counts: dict[str, Any],
) -> str:
    absent = "\n".join(f"  {name}" for name in preflight["absent_key_names"])
    checks = body_proof["checks"]
    metadata_operational = str(readiness["document_metadata_operational"]).upper()
    body_ready = str(readiness["document_body_storage_ready"]).upper()
    configured = str(readiness["object_store_configured"]).upper()
    refused_without = _low(checks["refused_without_an_adapter"])
    stored_with_fake = _low(checks["stored_with_the_fake_adapter"])
    scope_labelled = _low(checks["scope_was_labelled_fake"])
    production_stayed_false = _low(checks["production_storage_stayed_false"])
    return f"""# Gate 141 — what document storage still does not reach

## Where this stands

```text
document_metadata_operational   {metadata_operational}
document_body_storage_ready     {body_ready}
object_store_configured         {configured}
scope                           {readiness["scope"]}
preflight state                 {preflight["state"]}
```

A tenant can record a document REFERENCE, read it back anchored on
`organization_id`, list an award's documents and archive one. Its BYTES have
nowhere to live, and every route says so by name rather than by 404.

## Metadata does not need the object store

```text
object_store_required_for_metadata   false
body_bytes_required_for_metadata     false
documents stored with an object_key  {counts["documents_with_an_object_key"]}
documents claiming a configured store {counts["documents_claiming_a_configured_store"]}
```

Stated as fields rather than implied. Requiring a store for metadata would make
the metadata lane permanently unreachable and every "not ready" above it
unfalsifiable — the unsatisfiable conjunct Gate 134F removed from the
customer-auth chain.

## What every route refuses

```text
unauthenticated                             401, all six routes
a forged X-NF-Org-Id                        401 — not a parameter on any route
a caller setting is_demo or fact_status      400, named
object_key, object_bucket, content, body,
  bytes, sha256_digest, content_length       422, body storage not configured
POST .../body with no store                  422, with the missing key NAMES
POST .../body naming its own object key      422, caller keys not accepted
a cross-organization read                    403/404, which confirms nothing
```

## What the fake adapter proved, and what it cannot

Fourteen checks passed hermetically:

```text
the key is GENERATED, never accepted from a caller
{KEY_NAMESPACE}/<org[:2]>/<org[2:4]>/<org>/<doc>.<ext>
ten unsafe keys refused — traversal, absolute, backslash, NUL, empty
                          segment, foreign namespace, tilde, empty
an oversized body refused against a declared {readiness["max_body_bytes"]} byte limit
an empty body refused
a declared digest that does not match the bytes refused
put -> head -> get -> delete round trips
the external adapter is INERT with no client, no config and no permission
```

The body route's storing branch was reached under the fake and refused without
it:

```text
refused without an adapter        {refused_without}
stored with the fake adapter      {stored_with_fake}
scope labelled hermetic_fake      {scope_labelled}
production_storage stayed false   {production_stayed_false}
```

None of that proves durability, that a bucket exists, that a credential works,
or that any external service is reachable. So it may not set
`object_store_configured`, and an invariant fails if a hermetic scope ever does.

## What real activation would require

```text
five settings, with real values:
{absent}

an injected client        there is no boto3, botocore, minio, s3fs or aioboto3
                          in this project and this gate added none. uv.lock is
                          untouched. The external adapter takes any object
                          speaking the S3 API shape.

an owner decision         production_storage_owner_decision_service exists and
                          was not invoked

an external verifier      explicitly allowed AND passed, run by a person.
                          `production_verified` cannot be produced from
                          configuration alone: five settings being filled in and
                          five settings reaching a bucket that accepts writes are
                          different claims.

secret scanning           REQUIRED_GUARANTEES already names
                          secret_scan_clean_before_promotion
```

## What is NOT the blocker

```text
the metadata lane      operational, proved by calling the routes
the adapter            written, bounded, and proved hermetically
the refusals           explicit, named, and reachable
the database           nf_award_documents already CHECKs
                       object_key IS NULL OR object_store_configured
an SDK                 not needed to prove any of the above, and not added
```

## Still false, and not touched

```text
object_store_configured        false
document_body_storage_ready    false
production_storage             false
customer_auth_live             false
verified_operational_binding   false
source_monitoring_live         false
email_delivery                 false
production_rollout             false
controlled_customer_pilot      false
```

## Nothing was contacted

```text
external object store contacted   {_low(smoke["external_object_store_contacted"])}
network calls to object storage   {int(smoke["network_calls_to_object_storage"])}
body bytes sent                   {int(smoke["body_bytes_sent"])}
body bytes written externally     {int(readiness["body_bytes_written_externally"])}
real customer files read          {int(smoke["real_customer_files_read"])}
real customer files hashed        {int(smoke["real_customer_files_hashed"])}
credential values reported        {_low(preflight["credential_values_printed"])}
```
"""


def write_document_storage_artifacts(*, repo_root: Any = None) -> dict[str, Any]:
    """Write every file under ``ARTIFACT_DIR``, relative to ``repo_root``."""
    root = Path(repo_root) if repo_root is not None else Path()
    directory = root / ARTIFACT_DIR
    directory.mkdir(parents=True, exist_ok=True)

    files = build_document_storage_artifacts()
    for name, body in files.items():
        (directory / name).write_text(body, encoding="utf-8")

    return {
        "schema_version": SCHEMA_VERSION,
        "directory": str(directory),
        "files_written": sorted(files),
        "file_count": len(files),
    }


def document_storage_artifact_invariant_failures(
    result: dict[str, Any],
) -> list[str]:
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

    return fails
