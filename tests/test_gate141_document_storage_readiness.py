"""Gate 141: document storage readiness, made exact.

Gate 139 made document metadata route-live and correctly refused body storage.
Gate 140 made the digest operational without an object store. This gate asks the
question both left declared rather than measured:

```text
award_document_routes.py            object_store_configured=False, three times
post_award_common.refuse_body_storage  "object_store_configured": False
awarded_operational_tracking_readiness "document_body_storage_ready": False
```

Every one was correct and none was measured. Configure a bucket tomorrow and
the routes would still tell callers there was none.

The claims the gate is forbidden from making get their own tests and their own
reachable branches:

```text
no object store is contacted, and there is no SDK to contact one with
metadata does not need the object store, and does not ask for it
body storage is refused BY NAME, not by a 404
a fake adapter proves the code and may never configure a store
an object key is generated, never accepted from a caller
```
"""

from __future__ import annotations

import ast
import json
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from nativeforge.api import award_document_routes as routes
from nativeforge.api.post_award_common import (
    BODY_STORAGE_FIELDS,
    BODY_STORAGE_UNAVAILABLE,
    CALLER_MAY_NOT_SET,
    object_store_configured,
)
from nativeforge.main import create_app
from nativeforge.services import document_storage_artifact_gate141_service as art
from nativeforge.services.document_storage_readiness_service import (
    CREDENTIAL_SHAPED_MARKERS,
    METADATA_ROUTE_MODULE,
    NOT_APPROVED,
    SCOPE_HERMETIC_FAKE,
    SCOPE_NONE,
    SCOPE_PRODUCTION,
    build_document_storage_readiness,
    detect_metadata_route_module,
    document_storage_readiness_invariant_failures,
)
from nativeforge.services.document_storage_route_smoke_service import (
    AWARD_BODY,
    BODY_STORAGE_PROBES,
    DOCUMENT_BODY,
    document_storage_route_smoke_invariant_failures,
    run_document_storage_route_smoke,
)
from nativeforge.services.object_storage_adapter_service import (
    KEY_NAMESPACE,
    MAX_BODY_BYTES,
    UNSAFE_KEY_PROBES,
    ExternalObjectStorageAdapter,
    InMemoryObjectStorageAdapter,
    ObjectStorageError,
    adapter_proof_invariant_failures,
    assert_safe_key,
    body_digest,
    generate_object_key,
    key_is_safe,
    run_hermetic_adapter_proof,
)
from nativeforge.services.object_storage_configuration_preflight_service import (
    CONFIGURED_BUT_UNVERIFIED,
    HERMETIC_FAKE_VERIFIED,
    NO_CONFIG,
    PARTIAL_CONFIG,
    PREFLIGHT_STATES,
    PRODUCTION_VERIFIED,
    REQUIRED_KEY_NAMES,
    build_object_storage_preflight,
    inspect_required_keys,
    preflight_invariant_failures,
)
from tests import session_org_helper as soh

DEMO = "bbbbbbbb-cccc-dddd-eeee-ffffffffffff"
OTHER = "cccccccc-dddd-eeee-ffff-00000000d141"
REAL = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"

REPO_ROOT = Path(__file__).resolve().parents[1]

#: Modules that must import no object storage SDK and no network client.
STORAGE_MODULES: tuple[str, ...] = (
    "src/nativeforge/services/object_storage_adapter_service.py",
    "src/nativeforge/services/object_storage_configuration_preflight_service.py",
    "src/nativeforge/services/document_storage_readiness_service.py",
)


class _Settings:
    """Settings with exactly the object storage values a test wants.

    A real `Settings` cannot be constructed with a bucket in a test without
    reaching for the environment, and the point of these tests is that no value
    is ever read into a result.
    """

    def __init__(self, **values: object) -> None:
        for name in REQUIRED_KEY_NAMES:
            setattr(self, name, values.get(name, ""))


def _base(organization_id: str = DEMO) -> str:
    return f"/v1/nf/demo/orgs/{organization_id}"


@pytest.fixture
def client():
    return TestClient(create_app(), raise_server_exceptions=False)


@pytest.fixture
def demo_session():
    soh.ensure_signing_key()
    soh.ensure_org(DEMO, "demo")
    soh.ensure_org(OTHER, "demo")
    soh.ensure_member(DEMO)
    return soh.session_headers(uuid.UUID(DEMO))


def _create_award(client, headers) -> str:
    body = {**AWARD_BODY, "award_number": f"NF-G141T-{uuid.uuid4().hex[:8].upper()}"}
    response = client.post(f"{_base()}/awarded-grants", json=body, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()["award_id"]


def _create_document(client, headers, award_id: str, **overrides) -> str:
    body = {**DOCUMENT_BODY, **overrides}
    response = client.post(
        f"{_base()}/awarded-grants/{award_id}/documents", json=body, headers=headers
    )
    assert response.status_code == 201, response.text
    return response.json()["document_id"]


# ---------------------------------------------------------------------------
# nothing can contact an object store
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("sdk", ["boto3", "botocore", "minio", "s3fs", "aioboto3"])
def test_no_object_storage_sdk_is_installed(sdk):
    """ "No object store was contacted" is worth more as a property of the deps."""
    import importlib.util

    assert importlib.util.find_spec(sdk) is None, sdk


@pytest.mark.parametrize("name", ["pyproject.toml", "uv.lock"])
def test_no_object_storage_sdk_in_the_dependency_set(name):
    text = (REPO_ROOT / name).read_text(encoding="utf-8").lower()
    for sdk in ("boto3", "botocore", "minio", "s3fs", "aioboto3"):
        assert sdk not in text, f"{name} references {sdk}"


@pytest.mark.parametrize("relative", STORAGE_MODULES)
def test_the_storage_modules_import_no_network_client(relative):
    """Parsed, not searched: a docstring mention is not an import."""
    tree = ast.parse((REPO_ROOT / relative).read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            imported.add(node.module.split(".")[0])
    forbidden = {
        "boto3",
        "botocore",
        "minio",
        "s3fs",
        "aioboto3",
        "httpx",
        "requests",
        "aiohttp",
        "socket",
        "urllib3",
        "urllib",
    }
    assert not (imported & forbidden), sorted(imported & forbidden)


def test_the_adapter_logs_nothing():
    """A log line is a copy. No logger, no print, no exception carrying a body."""
    path = REPO_ROOT / "src/nativeforge/services/object_storage_adapter_service.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    called: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                called.add(node.func.id)
            elif isinstance(node.func, ast.Attribute):
                called.add(node.func.attr)
    for forbidden in ("print", "info", "debug", "warning", "error", "exception"):
        assert forbidden not in called, forbidden


def test_the_external_adapter_is_inert_by_default():
    """Default construction can reach nothing."""
    adapter = ExternalObjectStorageAdapter()
    result = adapter.put(organization_id=DEMO, document_id=str(uuid.uuid4()), body=b"x")
    assert result["stored"] is False
    assert result["blocked_reasons"] == ["object_storage_not_configured"]
    assert result["external_object_store_contacted"] is False


def test_the_external_adapter_needs_configuration_permission_and_a_client():
    """Three things, and each missing one is a different refusal by name."""

    class _Boom:
        def put_object(self, **kwargs):  # pragma: no cover - must never run
            raise AssertionError("the client was called")

        def get_object(self, **kwargs):  # pragma: no cover
            raise AssertionError("the client was called")

        def head_object(self, **kwargs):  # pragma: no cover
            raise AssertionError("the client was called")

        def delete_object(self, **kwargs):  # pragma: no cover
            raise AssertionError("the client was called")

    for kwargs, reason in (
        ({}, "object_storage_not_configured"),
        (
            {"object_store_configured": True},
            "external_object_storage_not_allowed",
        ),
        (
            {"object_store_configured": True, "allow_external": True},
            "no_object_store_client_injected",
        ),
        (
            {
                "object_store_configured": True,
                "allow_external": True,
                "client": _Boom(),
            },
            "no_object_store_client_injected",
        ),
    ):
        adapter = ExternalObjectStorageAdapter(**kwargs)
        result = adapter.put(
            organization_id=DEMO, document_id=str(uuid.uuid4()), body=b"x"
        )
        assert result["blocked_reasons"] == [reason], kwargs
        assert result["external_object_store_contacted"] is False


# ---------------------------------------------------------------------------
# the object key is generated, never accepted
# ---------------------------------------------------------------------------


def test_the_object_key_is_derived_from_ids_this_system_already_has():
    document_id = "00000000-0000-0000-0000-000000000141"
    key = generate_object_key(
        organization_id=DEMO, document_id=document_id, content_type="application/pdf"
    )
    assert key.startswith(f"{KEY_NAMESPACE}/")
    assert uuid.UUID(DEMO).hex in key
    assert uuid.UUID(document_id).hex in key
    assert key.endswith(".pdf")
    assert key_is_safe(key)


def test_an_unknown_content_type_gets_an_extension_that_claims_nothing():
    key = generate_object_key(
        organization_id=DEMO,
        document_id=str(uuid.uuid4()),
        content_type="application/made-up",
    )
    assert key.endswith(".bin")


def test_a_key_cannot_be_generated_from_a_non_uuid_anchor():
    with pytest.raises(ObjectStorageError):
        generate_object_key(organization_id="not-a-uuid", document_id=str(uuid.uuid4()))


@pytest.mark.parametrize("probe", UNSAFE_KEY_PROBES)
def test_every_unsafe_key_is_refused(probe):
    """Ten different ways of leaving the namespace, not ten spellings of one."""
    assert key_is_safe(probe) is False
    with pytest.raises(ObjectStorageError):
        assert_safe_key(probe)


def test_a_refused_key_is_not_echoed_back():
    """A refused key can be attacker-shaped; a message repeating it carries it."""
    probe = "award_documents/../../etc/passwd"
    with pytest.raises(ObjectStorageError) as caught:
        assert_safe_key(probe)
    assert probe not in str(caught.value)


def test_the_adapter_refuses_a_caller_supplied_key():
    adapter = InMemoryObjectStorageAdapter()
    result = adapter.put(
        organization_id=DEMO,
        document_id=str(uuid.uuid4()),
        body=b"x",
        object_key=f"{KEY_NAMESPACE}/anywhere/i/like.bin",
    )
    assert result["stored"] is False
    assert result["blocked_reasons"] == ["caller_supplied_object_keys_are_not_accepted"]


# ---------------------------------------------------------------------------
# the fake adapter, and its bounds
# ---------------------------------------------------------------------------


def test_the_fake_adapter_round_trips():
    adapter = InMemoryObjectStorageAdapter()
    document_id = str(uuid.uuid4())
    payload = b"gate141 synthetic bytes"

    stored = adapter.put(organization_id=DEMO, document_id=document_id, body=payload)
    assert stored["stored"] is True
    key = stored["object_key"]

    assert adapter.head(object_key=key)["exists"] is True
    assert adapter.get(object_key=key) == payload
    assert adapter.delete(object_key=key)["deleted"] is True
    assert adapter.head(object_key=key)["exists"] is False


def test_the_fake_adapter_refuses_an_oversized_body():
    adapter = InMemoryObjectStorageAdapter()
    result = adapter.put(
        organization_id=DEMO,
        document_id=str(uuid.uuid4()),
        body=b"x" * (MAX_BODY_BYTES + 1),
    )
    assert result["blocked_reasons"] == ["body_exceeds_the_maximum"]
    assert result["max_body_bytes"] == MAX_BODY_BYTES


def test_the_fake_adapter_refuses_an_empty_body():
    adapter = InMemoryObjectStorageAdapter()
    result = adapter.put(organization_id=DEMO, document_id=str(uuid.uuid4()), body=b"")
    assert result["blocked_reasons"] == ["body_is_empty"]


def test_a_declared_digest_is_verified_not_trusted():
    """Content addressing means nothing if the address is taken on trust."""
    adapter = InMemoryObjectStorageAdapter()
    payload = b"gate141 synthetic bytes"
    refused = adapter.put(
        organization_id=DEMO,
        document_id=str(uuid.uuid4()),
        body=payload,
        declared_digest="0" * 64,
    )
    assert refused["blocked_reasons"] == ["declared_digest_does_not_match_the_bytes"]

    accepted = adapter.put(
        organization_id=DEMO,
        document_id=str(uuid.uuid4()),
        body=payload,
        declared_digest=body_digest(payload),
    )
    assert accepted["stored"] is True


def test_no_adapter_result_carries_the_bytes():
    adapter = InMemoryObjectStorageAdapter()
    payload = b"gate141 secret-looking synthetic bytes"
    stored = adapter.put(
        organization_id=DEMO, document_id=str(uuid.uuid4()), body=payload
    )
    headed = adapter.head(object_key=stored["object_key"])
    for result in (stored, headed):
        assert payload.decode() not in json.dumps(result)
        assert result["body_bytes_returned"] is False


def test_the_hermetic_proof_passes_and_configures_nothing():
    result = run_hermetic_adapter_proof()
    assert result["hermetic_fake_passed"] is True
    assert result["blocked_reasons"] == []
    assert adapter_proof_invariant_failures(result) == []
    # The load-bearing separation.
    assert result["object_store_configured"] is False
    assert result["production_storage"] is False
    assert result["proves_durability"] is False
    assert result["proves_a_bucket_exists"] is False
    assert result["proves_credentials_work"] is False


def test_the_hermetic_proof_reads_and_hashes_no_real_file():
    result = run_hermetic_adapter_proof()
    assert result["real_files_read"] == 0
    assert result["real_files_hashed"] == 0
    assert result["network_calls"] == 0


def test_the_proof_invariants_catch_a_fake_that_configured_a_store():
    forged = {
        **run_hermetic_adapter_proof(),
        "object_store_configured": True,
    }
    assert "claimed:object_store_configured" in adapter_proof_invariant_failures(forged)


# ---------------------------------------------------------------------------
# the preflight reports names, never values
# ---------------------------------------------------------------------------


def test_the_preflight_reports_key_names_and_no_values():
    keys = inspect_required_keys(
        settings=_Settings(
            raw_payload_object_store_endpoint="https://storage.invalid",
            raw_payload_object_store_bucket="a-real-looking-bucket",
        )
    )
    rendered = json.dumps(keys)
    assert "storage.invalid" not in rendered
    assert "a-real-looking-bucket" not in rendered
    assert keys["values_reported"] is False
    assert keys["value_lengths_reported"] is False
    assert set(keys["present_key_names"]) == {
        "raw_payload_object_store_endpoint",
        "raw_payload_object_store_bucket",
    }


def test_the_runtime_preflight_is_not_configured():
    result = build_object_storage_preflight(settings=_Settings())
    assert result["object_store_configured"] is False
    assert result["state"] == NO_CONFIG
    assert result["blocked_reasons"]
    assert preflight_invariant_failures(result) == []


def test_a_partial_configuration_is_named_as_partial():
    """The dangerous state: it looks configured and can store nothing."""
    result = build_object_storage_preflight(
        settings=_Settings(raw_payload_object_store_bucket="something")
    )
    assert result["state"] == PARTIAL_CONFIG
    assert result["object_store_configured"] is False
    assert result["fully_configured"] is False


def test_a_full_configuration_is_still_unverified():
    result = build_object_storage_preflight(
        settings=_Settings(**dict.fromkeys(REQUIRED_KEY_NAMES, "set"))
    )
    assert result["state"] == CONFIGURED_BUT_UNVERIFIED
    assert result["fully_configured"] is True
    # Five settings filled in and five settings reaching a bucket that accepts
    # writes are different claims.
    assert result["object_store_configured"] is False


def test_production_verified_needs_both_pieces_of_evidence():
    """The permitted branch, kept reachable so the refusals are falsifiable."""
    configured = dict.fromkeys(REQUIRED_KEY_NAMES, "set")
    verified = build_object_storage_preflight(
        settings=_Settings(**configured),
        external_verification_allowed=True,
        external_verification_passed=True,
    )
    assert verified["state"] == PRODUCTION_VERIFIED
    assert verified["object_store_configured"] is True
    assert preflight_invariant_failures(verified) == []

    allowed_only = build_object_storage_preflight(
        settings=_Settings(**configured), external_verification_allowed=True
    )
    assert allowed_only["state"] == CONFIGURED_BUT_UNVERIFIED
    assert allowed_only["object_store_configured"] is False


def test_a_verification_nobody_allowed_is_refused():
    result = build_object_storage_preflight(
        settings=_Settings(**dict.fromkeys(REQUIRED_KEY_NAMES, "set")),
        external_verification_passed=True,
    )
    assert result["external_verification_passed"] is False
    assert (
        "external_verification_passed_without_being_allowed"
        in result["blocked_reasons"]
    )
    assert result["object_store_configured"] is False


def test_a_hermetic_fake_never_configures_the_store():
    result = build_object_storage_preflight(
        settings=_Settings(), hermetic_fake_passed=True
    )
    assert result["state"] == HERMETIC_FAKE_VERIFIED
    assert result["object_store_configured"] is False
    assert preflight_invariant_failures(result) == []


def test_the_preflight_invariants_catch_a_fake_that_configured_a_store():
    forged = {
        **build_object_storage_preflight(
            settings=_Settings(), hermetic_fake_passed=True
        ),
        "object_store_configured": True,
    }
    failures = preflight_invariant_failures(forged)
    assert "a_fake_adapter_configured_the_object_store" in failures


@pytest.mark.parametrize("state", PREFLIGHT_STATES)
def test_every_declared_state_is_recognised(state):
    assert state in PREFLIGHT_STATES


# ---------------------------------------------------------------------------
# metadata, which needs no object store
# ---------------------------------------------------------------------------


def test_the_metadata_route_module_is_session_wired_and_derives_the_flag():
    detected = detect_metadata_route_module()
    assert detected["route_module_available"] is True
    assert detected["session_wired"] is True
    assert detected["refuses_body_storage"] is True
    # The literal this gate removed. Its return would mean the routes stopped
    # measuring and started asserting again.
    assert detected["derives_object_store_configured"] is True
    assert detected["blocked_reasons"] == []


def test_the_metadata_route_detector_can_report_absent(tmp_path):
    detected = detect_metadata_route_module(repo_root=tmp_path)
    assert detected["route_module_available"] is False
    assert "route_module_does_not_exist" in detected["blocked_reasons"]


def test_no_real_organization_route_was_built():
    source = (REPO_ROOT / METADATA_ROUTE_MODULE).read_text(encoding="utf-8")
    assert "require_real_org_session" not in source
    assert "/v1/nf/real/orgs" not in source
    assert REAL not in source


def test_metadata_write_and_read_work_under_an_authenticated_org(client, demo_session):
    award_id = _create_award(client, demo_session)
    document_id = _create_document(client, demo_session, award_id)

    read = client.get(f"{_base()}/documents/{document_id}", headers=demo_session)
    assert read.status_code == 200
    assert read.json()["metadata_only"] is True

    listed = client.get(
        f"{_base()}/awarded-grants/{award_id}/documents", headers=demo_session
    )
    assert listed.status_code == 200
    assert listed.json()["rows_read"] >= 1


@pytest.mark.parametrize(
    "method,path",
    [
        ("GET", f"{_base()}/awarded-grants/{uuid.uuid4()}/documents"),
        ("POST", f"{_base()}/awarded-grants/{uuid.uuid4()}/documents"),
        ("GET", f"{_base()}/documents/{uuid.uuid4()}"),
        ("POST", f"{_base()}/documents/{uuid.uuid4()}/archive"),
        ("GET", f"{_base()}/documents/{uuid.uuid4()}/body-storage"),
        ("POST", f"{_base()}/documents/{uuid.uuid4()}/body"),
    ],
)
def test_every_document_route_refuses_an_unauthenticated_caller(client, method, path):
    assert client.request(method, path, json={}).status_code == 401


def test_a_forged_dev_header_cannot_override_the_org(client, demo_session):
    document_id = _create_document(
        client, demo_session, _create_award(client, demo_session)
    )
    forged = client.get(
        f"{_base()}/documents/{document_id}/body-storage",
        headers=soh.forged_header_only(uuid.UUID(DEMO)),
    )
    assert forged.status_code == 401


def test_the_dev_header_is_not_a_parameter_on_any_document_route():
    source = (REPO_ROOT / METADATA_ROUTE_MODULE).read_text(encoding="utf-8")
    assert "X-NF-Org-Id" not in source


def test_another_organization_cannot_read_this_document(client, demo_session):
    document_id = _create_document(
        client, demo_session, _create_award(client, demo_session)
    )
    soh.ensure_member(OTHER)
    other = soh.session_headers(uuid.UUID(OTHER))
    refused = client.get(f"{_base(OTHER)}/documents/{document_id}", headers=other)
    assert refused.status_code in {403, 404}


# ---------------------------------------------------------------------------
# body storage is refused, by name
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("field", sorted(BODY_STORAGE_FIELDS))
def test_a_caller_offering_a_body_field_is_refused_by_name(client, demo_session, field):
    award_id = _create_award(client, demo_session)
    refused = client.post(
        f"{_base()}/awarded-grants/{award_id}/documents",
        # A NAME, never content. Nothing here is read from a file.
        json={**DOCUMENT_BODY, field: "gate141-probe"},
        headers=demo_session,
    )
    assert refused.status_code == 422
    detail = refused.json()["detail"]
    assert detail["error"] == BODY_STORAGE_UNAVAILABLE
    assert field in detail["fields"]
    assert detail["object_store_configured"] is False


@pytest.mark.parametrize("field", sorted(CALLER_MAY_NOT_SET))
def test_a_caller_may_not_relabel_a_document_write(client, demo_session, field):
    award_id = _create_award(client, demo_session)
    refused = client.post(
        f"{_base()}/awarded-grants/{award_id}/documents",
        json={**DOCUMENT_BODY, field: "verified"},
        headers=demo_session,
    )
    assert refused.status_code in {400, 422}
    assert field in json.dumps(refused.json())


def test_the_body_route_refuses_with_the_missing_key_names(client, demo_session):
    """An explicit refusal, not a 404 that reads as a wrong URL."""
    document_id = _create_document(
        client, demo_session, _create_award(client, demo_session)
    )
    refused = client.post(
        f"{_base()}/documents/{document_id}/body",
        json={"content_type": "application/pdf"},
        headers=demo_session,
    )
    assert refused.status_code == 422
    detail = refused.json()["detail"]
    assert detail["error"] == BODY_STORAGE_UNAVAILABLE
    assert detail["object_store_configured"] is False
    assert detail["adapter_available"] is False
    assert set(detail["missing_configuration"]) == set(REQUIRED_KEY_NAMES)


def test_the_body_route_refusal_carries_no_credential_value(client, demo_session):
    document_id = _create_document(
        client, demo_session, _create_award(client, demo_session)
    )
    refused = client.post(
        f"{_base()}/documents/{document_id}/body",
        json={"content_type": "application/pdf"},
        headers=demo_session,
    )
    rendered = json.dumps(refused.json())
    for marker in CREDENTIAL_SHAPED_MARKERS:
        assert marker not in rendered, marker


def test_the_body_route_refuses_a_caller_supplied_object_key(client, demo_session):
    document_id = _create_document(
        client, demo_session, _create_award(client, demo_session)
    )
    refused = client.post(
        f"{_base()}/documents/{document_id}/body",
        json={"content_type": "application/pdf", "object_key": "anywhere/i/like"},
        headers=demo_session,
    )
    assert refused.status_code == 422
    assert (
        refused.json()["detail"]["error"]
        == "caller_supplied_object_keys_are_not_accepted"
    )


def test_the_body_storage_readiness_route_reports_what_is_missing(client, demo_session):
    document_id = _create_document(
        client, demo_session, _create_award(client, demo_session)
    )
    response = client.get(
        f"{_base()}/documents/{document_id}/body-storage", headers=demo_session
    )
    assert response.status_code == 200
    body = response.json()
    assert body["body_storage_available"] is False
    assert body["adapter_available"] is False
    assert body["object_store_configured"] is False
    assert body["production_storage"] is False
    assert set(body["missing_configuration"]) == set(REQUIRED_KEY_NAMES)
    assert body["unavailable_reason"] == BODY_STORAGE_UNAVAILABLE


def test_the_body_storage_readiness_route_names_no_value(client, demo_session):
    document_id = _create_document(
        client, demo_session, _create_award(client, demo_session)
    )
    response = client.get(
        f"{_base()}/documents/{document_id}/body-storage", headers=demo_session
    )
    rendered = json.dumps(response.json())
    for marker in CREDENTIAL_SHAPED_MARKERS:
        assert marker not in rendered, marker


def test_object_store_configured_is_measured_not_asserted():
    """The helper the routes call. It reads settings; it opens no socket."""
    assert object_store_configured() is False


def test_the_route_module_no_longer_hardcodes_the_flag():
    source = (REPO_ROOT / METADATA_ROUTE_MODULE).read_text(encoding="utf-8")
    assert "object_store_configured=False" not in source
    assert "object_store_configured=object_store_configured()" in source


# ---------------------------------------------------------------------------
# the body route's storing branch is reachable
# ---------------------------------------------------------------------------


def test_the_body_route_stores_through_an_injected_fake_adapter(demo_session):
    """The permitted branch, reached without a bucket.

    An unreachable permitted branch makes every refusal above it
    unfalsifiable - Gate 134F removed exactly that from the customer-auth
    chain. Runtime cannot reach this branch: nothing constructs an adapter for
    that dependency and there is no SDK here to construct an external one from.
    """
    import nativeforge.services.object_storage_configuration_preflight_service as pf

    app = create_app()
    adapter = InMemoryObjectStorageAdapter()
    app.dependency_overrides[routes.get_document_body_adapter] = lambda: adapter
    local = TestClient(app, raise_server_exceptions=False)

    award_id = _create_award(local, demo_session)
    document_id = _create_document(local, demo_session, award_id)

    real = pf.build_object_storage_preflight

    def _configured(**kwargs):
        return {
            **real(**kwargs),
            "object_store_configured": True,
            "state": SCOPE_HERMETIC_FAKE,
        }

    try:
        pf.build_object_storage_preflight = _configured
        stored = local.post(
            f"{_base()}/documents/{document_id}/body",
            json={"content_type": "application/pdf"},
            headers=demo_session,
        )
    finally:
        pf.build_object_storage_preflight = real

    assert stored.status_code == 201, stored.text
    body = stored.json()
    assert body["object_key"].startswith(f"{KEY_NAMESPACE}/")
    assert uuid.UUID(DEMO).hex in body["object_key"]
    assert body["adapter_kind"] == "in_memory_fake"
    assert body["storage_scope"] == SCOPE_HERMETIC_FAKE
    assert body["object_store_contacted"] is False
    assert body["production_storage"] is False
    assert body["body_bytes_returned"] is False
    assert adapter.object_count() == 1


def test_the_body_route_default_adapter_is_nothing():
    """Runtime's answer, and it is the answer rather than a placeholder."""
    assert routes.get_document_body_adapter() is None


# ---------------------------------------------------------------------------
# readiness
# ---------------------------------------------------------------------------


def _metadata_smoke(**overrides):
    return {
        "metadata_route_operational": True,
        "org_scoped_read_write_proved": True,
        "body_bytes_not_required": True,
        "blocked_reasons": [],
        **overrides,
    }


def test_metadata_is_operational_and_the_body_is_not():
    readiness = build_document_storage_readiness(metadata_route_smoke=_metadata_smoke())
    assert readiness["document_metadata_operational"] is True
    assert readiness["document_body_storage_ready"] is False
    assert readiness["object_store_configured"] is False
    assert readiness["scope"] == SCOPE_NONE
    assert readiness["blocked_reasons"]
    assert document_storage_readiness_invariant_failures(readiness) == []


def test_metadata_does_not_require_the_object_store():
    """Requiring one would make the metadata lane permanently unreachable."""
    readiness = build_document_storage_readiness(metadata_route_smoke=_metadata_smoke())
    assert readiness["object_store_required_for_metadata"] is False
    assert readiness["body_bytes_required_for_metadata"] is False


def test_metadata_is_not_operational_without_a_smoke():
    readiness = build_document_storage_readiness()
    assert readiness["document_metadata_operational"] is False
    assert "no_metadata_route_smoke_was_supplied" in readiness["blocked_reasons"]


def test_metadata_is_not_operational_when_the_module_is_absent(tmp_path):
    readiness = build_document_storage_readiness(
        metadata_route_smoke=_metadata_smoke(), repo_root=tmp_path
    )
    assert readiness["document_metadata_operational"] is False
    assert any(
        "route_module_does_not_exist" in reason
        for reason in readiness["blocked_reasons"]
    )


def test_body_storage_is_ready_only_in_a_labelled_scope():
    """The permitted branch, kept reachable, and kept out of production."""
    ready = build_document_storage_readiness(
        preflight=build_object_storage_preflight(
            settings=_Settings(), hermetic_fake_passed=True
        ),
        adapter_proof=run_hermetic_adapter_proof(),
        metadata_route_smoke=_metadata_smoke(),
        body_route_smoke={"body_route_operational": True},
    )
    assert ready["document_body_storage_ready"] is True
    assert ready["scope"] == SCOPE_HERMETIC_FAKE
    # And still not configured. A fake is not a bucket.
    assert ready["object_store_configured"] is False
    assert ready["production_storage"] is False
    assert document_storage_readiness_invariant_failures(ready) == []


def test_body_storage_is_not_ready_without_a_body_route_proof():
    readiness = build_document_storage_readiness(
        preflight=build_object_storage_preflight(
            settings=_Settings(), hermetic_fake_passed=True
        ),
        adapter_proof=run_hermetic_adapter_proof(),
        metadata_route_smoke=_metadata_smoke(),
    )
    assert readiness["document_body_storage_ready"] is False
    assert "no_body_route_proof_was_supplied" in readiness["blocked_reasons"]


def test_body_storage_is_not_ready_when_a_secret_was_exposed():
    readiness = build_document_storage_readiness(
        preflight=build_object_storage_preflight(
            settings=_Settings(), hermetic_fake_passed=True
        ),
        adapter_proof=run_hermetic_adapter_proof(),
        metadata_route_smoke=_metadata_smoke(),
        body_route_smoke={"body_route_operational": True, "secrets_exposed": True},
    )
    assert readiness["document_body_storage_ready"] is False
    assert "credential_values_were_exposed" in readiness["blocked_reasons"]


def test_object_store_configured_needs_production_scope():
    readiness = build_document_storage_readiness(
        preflight=build_object_storage_preflight(
            settings=_Settings(**dict.fromkeys(REQUIRED_KEY_NAMES, "set")),
            external_verification_allowed=True,
            external_verification_passed=True,
        ),
        adapter_proof=run_hermetic_adapter_proof(),
        metadata_route_smoke=_metadata_smoke(),
        body_route_smoke={"body_route_operational": True},
    )
    assert readiness["scope"] == SCOPE_PRODUCTION
    assert readiness["object_store_configured"] is True
    # Production STORAGE is a different claim, and it stays false.
    assert readiness["production_storage"] is False
    assert document_storage_readiness_invariant_failures(readiness) == []


@pytest.mark.parametrize(
    "field",
    [
        "production_storage",
        "external_object_store_contacted",
        "credential_values_reported",
        "customer_auth_live",
        "real_organization_touched",
    ],
)
def test_readiness_never_claims(field):
    readiness = build_document_storage_readiness(metadata_route_smoke=_metadata_smoke())
    assert readiness[field] is False


def test_readiness_writes_no_body_bytes_and_reads_no_real_file():
    readiness = build_document_storage_readiness(metadata_route_smoke=_metadata_smoke())
    assert readiness["body_bytes_written_externally"] == 0
    assert readiness["real_customer_files_read"] == 0
    assert readiness["real_customer_files_hashed"] == 0
    assert readiness["network_calls"] == 0


def test_readiness_names_what_it_does_not_approve():
    readiness = build_document_storage_readiness()
    assert set(NOT_APPROVED) <= set(readiness["not_approved"])


def test_the_readiness_invariants_catch_a_fake_that_configured_a_store():
    forged = {
        **build_document_storage_readiness(metadata_route_smoke=_metadata_smoke()),
        "scope": SCOPE_HERMETIC_FAKE,
        "object_store_configured": True,
    }
    failures = document_storage_readiness_invariant_failures(forged)
    assert "a_fake_adapter_configured_the_object_store" in failures


def test_the_readiness_invariants_catch_a_hardcoded_route_flag():
    readiness = build_document_storage_readiness(metadata_route_smoke=_metadata_smoke())
    forged = {
        **readiness,
        "metadata_route": {
            **readiness["metadata_route"],
            "derives_object_store_configured": False,
        },
    }
    failures = document_storage_readiness_invariant_failures(forged)
    assert "metadata_route_hardcodes_object_store_configured" in failures


def test_customer_auth_live_is_not_silently_made_true():
    readiness = build_document_storage_readiness(
        preflight=build_object_storage_preflight(
            settings=_Settings(), hermetic_fake_passed=True
        ),
        adapter_proof=run_hermetic_adapter_proof(),
        metadata_route_smoke=_metadata_smoke(),
        body_route_smoke={"body_route_operational": True},
    )
    assert readiness["document_body_storage_ready"] is True
    assert readiness["customer_auth_live"] is False


# ---------------------------------------------------------------------------
# the route smoke
# ---------------------------------------------------------------------------


def test_the_route_smoke_proves_every_lane(client, demo_session):
    soh.ensure_member(OTHER)
    smoke = run_document_storage_route_smoke(
        client=client,
        organization_id=DEMO,
        other_organization_id=OTHER,
        session_headers=demo_session,
    )
    assert smoke["blocked_reasons"] == [], smoke["blocked_reasons"]
    assert smoke["end_to_end_completed"] is True
    assert document_storage_route_smoke_invariant_failures(smoke) == []
    assert smoke["external_object_store_contacted"] is False
    assert smoke["body_bytes_sent"] == 0
    assert smoke["real_customer_files_read"] == 0


def test_the_route_smoke_refuses_everything_without_a_session(client):
    smoke = run_document_storage_route_smoke(
        client=client, organization_id=DEMO, other_organization_id=OTHER
    )
    assert smoke["unauthenticated_refused"] is True
    assert smoke["forged_header_refused"] is True
    assert smoke["authenticated_run"] is False


@pytest.mark.parametrize("probe", BODY_STORAGE_PROBES)
def test_every_body_storage_probe_is_a_field_the_guard_knows(probe):
    """Otherwise a probe could pass because nothing was watching for it."""
    assert probe in BODY_STORAGE_FIELDS


# ---------------------------------------------------------------------------
# the artifacts
# ---------------------------------------------------------------------------


def test_the_artifact_writes_every_declared_file(tmp_path):
    result = art.write_document_storage_artifacts(repo_root=tmp_path)
    assert art.document_storage_artifact_invariant_failures(result) == []
    for name in art.ARTIFACT_FILES:
        assert (tmp_path / art.ARTIFACT_DIR / name).is_file(), name


def test_the_artifact_is_deterministic():
    first = art.build_document_storage_artifacts()
    second = art.build_document_storage_artifacts()
    assert first == second


def test_the_artifact_reports_metadata_operational_and_the_body_blocked():
    files = art.build_document_storage_artifacts()
    readiness = json.loads(files["document_storage_readiness.json"])
    blocker = json.loads(files["body_storage_blocker_smoke.json"])
    assert readiness["document_metadata_operational"] is True
    assert readiness["document_body_storage_ready"] is False
    assert readiness["object_store_configured"] is False
    assert readiness["invariant_failures"] == []
    assert blocker["unconfigured_blocker_correct"] is True
    assert blocker["all_body_storage_fields_refused"] is True
    assert blocker["body_bytes_written"] == 0


def test_the_artifact_records_a_reachable_hermetic_body_route():
    files = art.build_document_storage_artifacts()
    fake = json.loads(files["fake_adapter_hermetic_result.json"])
    assert fake["hermetic_fake_passed"] is True
    assert fake["body_route_hermetic_proof"]["body_route_operational"] is True
    assert fake["object_store_configured"] is False
    assert fake["production_storage"] is False
    assert fake["invariant_failures"] == []


def test_no_artifact_carries_a_credential_or_a_body():
    for name, body in art.build_document_storage_artifacts().items():
        lowered = body.lower()
        for marker in art.FORBIDDEN_MARKERS:
            assert marker.lower() not in lowered, (name, marker)


def test_the_artifacts_report_key_names_and_no_values():
    files = art.build_document_storage_artifacts()
    preflight = json.loads(files["object_storage_preflight.json"])
    assert set(preflight["absent_key_names"]) == set(REQUIRED_KEY_NAMES)
    assert preflight["values_reported"] is False
    assert preflight["value_lengths_reported"] is False
    assert preflight["external_object_store_contacted"] is False


def test_the_committed_artifacts_match_what_the_service_builds():
    directory = REPO_ROOT / art.ARTIFACT_DIR
    for name, body in art.build_document_storage_artifacts().items():
        committed = directory / name
        assert committed.is_file(), name
        assert committed.read_text(encoding="utf-8") == body, name
