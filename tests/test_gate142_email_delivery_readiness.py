"""Gate 142: digest delivery, rehearsed without sending any email.

Doc 741 found the constraint that shapes this gate: Gate 104's digest builder
owns the word `queued` and lists it under `DELIVERED_STATUSES` — "statuses that
assert something left the building". So a dry-run queue may not borrow it, and
the digest keeps `delivery_status: preview_only`.

The claims the gate is forbidden from making get their own tests and their own
reachable branches:

```text
readiness is not delivery, and a rehearsal may never activate sending
no address is stored, returned, or committed - a fingerprint and a domain
no provider is contacted, and no delivery module imports a mail library
an intent is not a queue position, and the DATABASE enforces it
an unverified recipient is refused; a shape is not a fact
```
"""

from __future__ import annotations

import ast
import json
import re
import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient

from nativeforge.api.post_award_common import CALLER_MAY_NOT_SET
from nativeforge.domain.enums import SECURITY_AUDIT_ACTIONS, AuditAction
from nativeforge.main import create_app
from nativeforge.services import digest_delivery_dry_run_queue_service as queue
from nativeforge.services import email_delivery_artifact_gate142_service as art
from nativeforge.services.digest_delivery_renderer_service import (
    FORBIDDEN_CLAIMS,
    MAX_RENDERED_ITEMS,
    MAX_SUBJECT_LENGTH,
    RENDER_FIELDS,
    body_render_hash,
    digest_period_key,
    render_digest_for_delivery,
    render_invariant_failures,
)
from nativeforge.services.digest_delivery_route_smoke_service import (
    delivery_route_smoke_invariant_failures,
    run_digest_delivery_route_smoke,
)
from nativeforge.services.digest_recipient_validation_service import (
    FIXTURE_DOMAIN,
    recipient_invariant_failures,
    recipient_set_invariant_failures,
    resolve_org_recipients,
    validate_recipient,
)
from nativeforge.services.email_delivery_readiness_service import (
    DELIVERY_MODULES,
    NOT_APPROVED,
    SCOPE_CONTROLLED,
    SCOPE_NONE,
    build_email_delivery_readiness,
    delivery_readiness_invariant_failures,
    detect_delivery_route_module,
    detect_mail_library_imports,
)
from nativeforge.services.email_provider_configuration_preflight_service import (
    CONFIGURED_BUT_UNVERIFIED,
    DRY_RUN_VERIFIED,
    NO_CONFIG,
    PARTIAL_CONFIG,
    REQUIRED_SETTING_NAMES,
    SEND_ACTIVATED,
    SEND_ACTIVATION_SETTING,
    build_email_provider_preflight,
    email_preflight_invariant_failures,
    inspect_required_settings,
)
from nativeforge.services.tenant_nofo_digest_service import build_org_digest_preview
from tests import session_org_helper as soh

DEMO = "bbbbbbbb-cccc-dddd-eeee-ffffffffffff"
OTHER = "cccccccc-dddd-eeee-ffff-00000000d142"
REAL = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"

REPO_ROOT = Path(__file__).resolve().parents[1]

#: A fixture mailbox at a domain RFC 2606 reserves so nothing can deliver to it.
FIXTURE_ADDRESS = f"gate142-test@fixture.{FIXTURE_DOMAIN}"

#: A mailbox: local part, @, domain with a real TLD. Not a bare `@` - a bare
#: one appears in the migration's own CHECK, which is the guarantee.
ADDRESS_SHAPE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")

FIXED_NOW = datetime(2026, 9, 4, tzinfo=UTC)


class _Settings:
    """Settings carrying exactly the email values a test wants."""

    def __init__(self, **values: object) -> None:
        for name in (*REQUIRED_SETTING_NAMES, SEND_ACTIVATION_SETTING):
            setattr(self, name, values.get(name, ""))


def _base(organization_id: str = DEMO) -> str:
    return f"/v1/nf/demo/orgs/{organization_id}"


def _seed(organization_id: str, *, with_recipient: bool = True) -> str | None:
    """A profile, a watchlist entry and a verified fixture member."""
    from nativeforge.db.session import SessionLocal
    from nativeforge.services import tenant_source_watchlist_service as watchlist
    from nativeforge.services.dev_org_membership_bootstrap_service import (
        insert_membership,
        upsert_identity,
    )
    from nativeforge.services.tenant_profile_repository_service import (
        upsert_tenant_profile,
    )

    identity_id = None
    with SessionLocal() as session:
        connection = session.connection()
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
        assert result["rows_written"] == 1, result["blocked_reasons"]
        watchlist.add_watchlist_entry(
            connection=connection,
            entry_id=uuid.uuid4(),
            now=FIXED_NOW,
            organization_id=organization_id,
            source_id="nf-seed-2026-fed-001",
            watchlist_source="registry_entry",
            source_name="Aid to Tribal Government Services",
            jurisdiction="federal",
            fact_status="demo_fixture",
        )
        if with_recipient:
            identity = upsert_identity(
                connection=connection,
                issuer="https://accounts.google.com",
                subject=f"gate142-member-of-{organization_id}",
                email_verified=True,
                verification_source="oidc_token_signature",
                email=f"gate142-{organization_id[:8]}@fixture.{FIXTURE_DOMAIN}",
            )
            identity_id = identity["identity_id"]
            already = session.execute(
                sa.text(
                    "SELECT COUNT(*) FROM nf_org_memberships "
                    "WHERE organization_id = :o AND identity_id = :i"
                ),
                {
                    "o": uuid.UUID(organization_id).hex,
                    "i": uuid.UUID(identity_id).hex,
                },
            ).scalar_one()
            if not already:
                insert_membership(
                    connection=connection,
                    organization_id=organization_id,
                    identity_id=identity_id,
                    state="active",
                    role="org_owner",
                    membership_source="verified_directory",
                )
        session.commit()
    return identity_id


def _clear(organization_id: str) -> None:
    from nativeforge.db.session import SessionLocal

    with SessionLocal() as session:
        for table in (
            "nf_digest_delivery_intents",
            "nf_source_watchlist_entries",
            "nf_tenant_pursuit_suppressions",
            "nf_tenant_beta_profiles",
        ):
            session.execute(
                sa.text(f"DELETE FROM {table} WHERE organization_id = :o"),
                {"o": uuid.UUID(organization_id).hex},
            )
        session.commit()


@pytest.fixture
def client():
    return TestClient(create_app(), raise_server_exceptions=False)


@pytest.fixture
def demo_session():
    soh.ensure_signing_key()
    soh.ensure_org(DEMO, "demo")
    soh.ensure_org(OTHER, "demo")
    soh.ensure_member(DEMO)
    _clear(DEMO)
    _clear(OTHER)
    _seed(DEMO)
    yield soh.session_headers(uuid.UUID(DEMO))
    _clear(DEMO)
    _clear(OTHER)


# ---------------------------------------------------------------------------
# nothing can send
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("relative", DELIVERY_MODULES)
def test_no_delivery_module_imports_a_mail_library(relative):
    """Parsed, not searched. `smtplib` is stdlib, so absence is the guarantee."""
    tree = ast.parse((REPO_ROOT / relative).read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            imported.add(node.module.split(".")[0])
    forbidden = {
        "smtplib",
        "email",
        "aiosmtplib",
        "sendgrid",
        "mailgun",
        "postmarker",
        "socket",
        "httpx",
        "requests",
        "aiohttp",
        "urllib",
        "urllib3",
        "http",
    }
    assert not (imported & forbidden), sorted(imported & forbidden)


def test_the_detector_finds_no_mail_library_anywhere():
    found = detect_mail_library_imports()
    assert found["any_mail_library_imported"] is False
    assert found["mail_library_imports"] == {}
    assert found["modules_missing"] == []


def test_the_route_module_does_not_look_like_it_sends():
    detected = detect_delivery_route_module()
    assert detected["route_module_available"] is True
    assert detected["session_wired"] is True
    assert detected["sends_no_email"] is True
    assert detected["blocked_reasons"] == []


def test_the_route_module_detector_can_report_absent(tmp_path):
    detected = detect_delivery_route_module(repo_root=tmp_path)
    assert detected["route_module_available"] is False
    assert "route_module_does_not_exist" in detected["blocked_reasons"]


def test_no_real_organization_delivery_route_was_built():
    source = (REPO_ROOT / "src/nativeforge/api/digest_delivery_routes.py").read_text(
        encoding="utf-8"
    )
    assert "require_real_org_session" not in source
    assert "/v1/nf/real/orgs" not in source
    assert REAL not in source


def test_the_delivery_audit_verbs_are_not_security_events():
    """A tenant digest in the security stream teaches readers to ignore it."""
    assert AuditAction.digest_delivery_intent_recorded not in SECURITY_AUDIT_ACTIONS
    assert AuditAction.digest_delivery_refused not in SECURITY_AUDIT_ACTIONS


def test_no_audit_verb_asserts_a_send():
    """`digest_delivery_sent` does not exist, because nothing can produce it."""
    assert not any(a.value.endswith("_sent") for a in AuditAction)


# ---------------------------------------------------------------------------
# the provider preflight: names, never values
# ---------------------------------------------------------------------------


def test_the_preflight_reports_setting_names_and_no_values():
    names = inspect_required_settings(
        settings=_Settings(
            nf_email_provider="a-real-looking-vendor",
            nf_email_sender_address="someone@a-real-domain.test",
        )
    )
    rendered = json.dumps(names)
    assert "a-real-looking-vendor" not in rendered
    assert "a-real-domain.test" not in rendered
    assert not ADDRESS_SHAPE.search(rendered)
    assert names["values_reported"] is False


def test_the_runtime_preflight_has_no_configuration():
    result = build_email_provider_preflight(settings=_Settings())
    assert result["state"] == NO_CONFIG
    assert result["email_delivery"] is False
    assert result["provider_configured"] is False
    assert "no_email_provider_configured" in result["blocked_reasons"]
    assert "send_activation_absent" in result["blocked_reasons"]
    assert email_preflight_invariant_failures(result) == []


def test_a_partial_configuration_is_named_as_partial():
    result = build_email_provider_preflight(
        settings=_Settings(nf_email_provider="vendor")
    )
    assert result["state"] == PARTIAL_CONFIG
    assert result["provider_configured"] is False
    assert result["email_delivery"] is False


def test_a_placeholder_is_not_a_configuration():
    result = build_email_provider_preflight(
        settings=_Settings(**dict.fromkeys(REQUIRED_SETTING_NAMES, "changeme"))
    )
    assert result["provider_configured"] is False
    assert result["placeholder_setting_names"]


def test_a_full_configuration_is_still_not_delivering():
    result = build_email_provider_preflight(
        settings=_Settings(**dict.fromkeys(REQUIRED_SETTING_NAMES, "set"))
    )
    assert result["state"] == CONFIGURED_BUT_UNVERIFIED
    assert result["provider_configured"] is True
    assert result["email_delivery"] is False


def test_send_activation_needs_three_pieces_of_evidence():
    """The permitted branch, kept reachable so the refusals are falsifiable."""
    configured = dict.fromkeys(REQUIRED_SETTING_NAMES, "set")
    activated = build_email_provider_preflight(
        settings=_Settings(**configured),
        provider_verification_allowed=True,
        provider_verification_passed=True,
        send_activation_approved=True,
    )
    assert activated["state"] == SEND_ACTIVATED
    assert activated["email_delivery"] is True
    assert email_preflight_invariant_failures(activated) == []

    for missing in (
        {"provider_verification_allowed": True, "provider_verification_passed": True},
        {"provider_verification_allowed": True, "send_activation_approved": True},
        {"send_activation_approved": True},
    ):
        partial = build_email_provider_preflight(
            settings=_Settings(**configured), **missing
        )
        assert partial["email_delivery"] is False, missing


def test_a_setting_is_not_an_approval():
    """Somebody flipping an env var is not the decision this gate requires."""
    result = build_email_provider_preflight(
        settings=_Settings(
            **dict.fromkeys(REQUIRED_SETTING_NAMES, "set"),
            **{SEND_ACTIVATION_SETTING: "true"},
        )
    )
    assert result["email_delivery"] is False
    assert (
        "send_activation_setting_present_without_an_approval"
        in result["blocked_reasons"]
    )


def test_a_dry_run_never_activates_delivery():
    result = build_email_provider_preflight(settings=_Settings(), dry_run_passed=True)
    assert result["state"] == DRY_RUN_VERIFIED
    assert result["email_delivery"] is False
    assert email_preflight_invariant_failures(result) == []


def test_the_preflight_invariants_catch_a_dry_run_that_activated_delivery():
    forged = {
        **build_email_provider_preflight(settings=_Settings(), dry_run_passed=True),
        "email_delivery": True,
    }
    assert "a_dry_run_activated_email_delivery" in (
        email_preflight_invariant_failures(forged)
    )


# ---------------------------------------------------------------------------
# the render
# ---------------------------------------------------------------------------


def _digest(client=None, headers=None):
    from nativeforge.db.session import SessionLocal

    with SessionLocal() as session:
        return build_org_digest_preview(
            connection=session.connection(), organization_id=DEMO
        )


def test_a_digest_renders_into_a_deliverable_shape(demo_session):
    render = render_digest_for_delivery(digest=_digest())
    assert render["deliverable"] is True
    assert render["subject_line"]
    assert render["body_byte_length"] > 0
    assert render_invariant_failures(render) == []
    missing = [f for f in RENDER_FIELDS if f not in render]
    assert not missing


def test_the_render_carries_no_recipient(demo_session):
    render = render_digest_for_delivery(digest=_digest())
    assert render["recipient_in_render"] is False
    assert not ADDRESS_SHAPE.search(render["body_text"])
    assert not ADDRESS_SHAPE.search(render["subject_line"])


def test_the_render_makes_no_claim_it_may_not(demo_session):
    render = render_digest_for_delivery(digest=_digest())
    lowered = render["body_text"].lower()
    for claim in FORBIDDEN_CLAIMS:
        assert claim not in lowered, claim


def test_an_unverified_deadline_is_written_as_unverified(demo_session):
    render = render_digest_for_delivery(digest=_digest())
    assert render["items_with_unverified_deadlines"] >= 1
    assert "(not verified)" in render["body_text"]


def test_the_render_tells_the_reader_it_is_not_a_live_check(demo_session):
    render = render_digest_for_delivery(digest=_digest())
    lowered = render["body_text"].lower()
    assert "not from live checks" in lowered
    assert "verify every deadline" in lowered


def test_the_render_is_plain_text(demo_session):
    render = render_digest_for_delivery(digest=_digest())
    assert render["html_rendered"] is False
    assert render["tracking_pixels"] == 0
    assert render["links_rewritten"] == 0


def test_the_render_hash_matches_the_body(demo_session):
    render = render_digest_for_delivery(digest=_digest())
    assert render["body_render_hash"] == body_render_hash(render["body_text"])


def test_two_renders_of_one_digest_agree(demo_session):
    digest = _digest()
    assert render_digest_for_delivery(digest=digest) == render_digest_for_delivery(
        digest=digest
    )


def test_a_refused_digest_does_not_render():
    render = render_digest_for_delivery(
        digest={"blocked_reasons": ["daily_digest_requested_but_not_enabled"]}
    )
    assert render["deliverable"] is False
    assert "digest_was_not_produced" in render["blocked_reasons"]
    assert render_invariant_failures(render) == []


def test_an_empty_digest_does_not_render():
    render = render_digest_for_delivery(digest={"items": [], "items_total": 0})
    assert render["deliverable"] is False
    assert "digest_has_no_items_to_render" in render["blocked_reasons"]


def test_a_long_digest_is_bounded():
    items = [
        {
            "opportunity_id": f"nf-fixture-{n}",
            "title": f"Opportunity {n}",
            "source": "fixture",
            "eligibility_status": "unknown",
            "recommended_action": "review_eligibility_with_a_human",
        }
        for n in range(MAX_RENDERED_ITEMS + 10)
    ]
    render = render_digest_for_delivery(
        digest={"items": items, "items_total": len(items), "items_visible": len(items)}
    )
    assert render["items_rendered"] == MAX_RENDERED_ITEMS
    assert "further matched notices are not listed" in render["body_text"]
    assert len(render["subject_line"]) <= MAX_SUBJECT_LENGTH


def test_the_period_key_is_stable_for_one_period():
    key = digest_period_key(
        cadence="weekly", period_start="2026-01-01", period_end="2026-01-08"
    )
    assert key == digest_period_key(
        cadence="weekly", period_start="2026-01-01", period_end="2026-01-08"
    )
    assert key != digest_period_key(
        cadence="weekly", period_start="2026-01-08", period_end="2026-01-15"
    )


def test_the_digest_now_carries_a_real_period(demo_session):
    """Gate 140's assembler passed no period, so every digest_id was identical."""
    digest = _digest()
    assert digest["period_start"]
    assert digest["period_end"]
    assert digest["period_start"] != digest["period_end"]


# ---------------------------------------------------------------------------
# recipient validation
# ---------------------------------------------------------------------------


def test_a_verified_recipient_validates_to_a_fingerprint():
    result = validate_recipient(
        address=FIXTURE_ADDRESS, verified=True, recipient_source="org_membership"
    )
    assert result["deliverable"] is True
    assert len(result["recipient_fingerprint"]) == 32
    assert result["recipient_domain"] == f"fixture.{FIXTURE_DOMAIN}"
    assert recipient_invariant_failures(result) == []


def test_no_address_appears_in_a_validation_result():
    result = validate_recipient(
        address=FIXTURE_ADDRESS, verified=True, recipient_source="org_membership"
    )
    rendered = json.dumps(result)
    assert FIXTURE_ADDRESS not in rendered
    assert not ADDRESS_SHAPE.search(rendered)
    assert result["address_reported"] is False
    assert result["address_stored"] is False


def test_an_unverified_recipient_is_refused():
    """A shape is not a fact. `email_verified` comes from a token signature."""
    result = validate_recipient(
        address=FIXTURE_ADDRESS, verified=False, recipient_source="org_membership"
    )
    assert result["deliverable"] is False
    assert result["blocked_reasons"] == ["recipient_not_verified"]


@pytest.mark.parametrize(
    "address,reason",
    [
        ("not-an-address", "recipient_shape_invalid"),
        ("", "no_recipient_supplied"),
        ("a" * 400 + f"@fixture.{FIXTURE_DOMAIN}", "recipient_address_too_long"),
    ],
)
def test_a_malformed_recipient_is_refused(address, reason):
    result = validate_recipient(
        address=address, verified=True, recipient_source="org_membership"
    )
    assert result["deliverable"] is False
    assert reason in result["blocked_reasons"]


def test_a_domain_outside_the_allowed_list_is_refused():
    result = validate_recipient(
        address=FIXTURE_ADDRESS,
        verified=True,
        recipient_source="org_membership",
        allowed_domains=["somewhere-else.invalid"],
    )
    assert result["deliverable"] is False
    assert "recipient_domain_not_allowed" in result["blocked_reasons"]


def test_an_unrecognised_source_is_refused():
    result = validate_recipient(
        address=FIXTURE_ADDRESS, verified=True, recipient_source="somebody_asked"
    )
    assert result["deliverable"] is False
    assert "recipient_source_not_recognised" in result["blocked_reasons"]


def test_a_tenant_requested_recipient_needs_human_review():
    result = validate_recipient(
        address=FIXTURE_ADDRESS, verified=True, recipient_source="tenant_requested"
    )
    assert result["human_review_required"] is True


def test_nothing_is_looked_up_over_a_network():
    result = validate_recipient(
        address=FIXTURE_ADDRESS, verified=True, recipient_source="org_membership"
    )
    assert result["dns_checked"] is False
    assert result["mx_checked"] is False
    assert result["provider_validation_called"] is False
    assert result["network_calls"] == 0


def test_org_recipients_resolve_to_fingerprints(demo_session):
    from nativeforge.db.session import SessionLocal

    with SessionLocal() as session:
        resolved = resolve_org_recipients(
            connection=session.connection(), organization_id=DEMO
        )
    assert resolved["rows_read"] >= 1
    assert resolved["deliverable_count"] >= 1
    assert recipient_set_invariant_failures(resolved) == []
    assert not ADDRESS_SHAPE.search(json.dumps(resolved))


def test_a_member_with_no_address_is_refused_not_assumed_away(demo_session):
    """`nf_identities.email` is nullable, so this member really can exist."""
    from nativeforge.db.session import SessionLocal
    from nativeforge.services.dev_org_membership_bootstrap_service import (
        insert_membership,
        upsert_identity,
    )

    with SessionLocal() as session:
        connection = session.connection()
        identity = upsert_identity(
            connection=connection,
            issuer="https://accounts.google.com",
            subject="gate142-member-with-no-address",
            email_verified=False,
            verification_source="oidc_token_signature",
        )["identity_id"]
        insert_membership(
            connection=connection,
            organization_id=DEMO,
            identity_id=identity,
            state="active",
            role="org_member",
            membership_source="verified_directory",
        )
        session.commit()
        resolved = resolve_org_recipients(
            connection=session.connection(), organization_id=DEMO
        )

    refused = [r for r in resolved["recipients"] if not r["deliverable"]]
    assert refused, "the member with no address should have been refused"
    for recipient in refused:
        assert recipient["blocked_reasons"]
        assert (
            recipient["recipient_fingerprint"] is None
            or len(recipient["recipient_fingerprint"]) == 32
        )
    # And the organization is still deliverable to, through the members who can.
    assert resolved["deliverable_count"] >= 1
    assert recipient_set_invariant_failures(resolved) == []


def test_an_organization_with_no_members_says_so():
    from nativeforge.db.session import SessionLocal

    soh.ensure_org(OTHER, "demo")
    _clear(OTHER)
    with SessionLocal() as session:
        resolved = resolve_org_recipients(
            connection=session.connection(), organization_id=OTHER
        )
    assert resolved["deliverable_count"] == 0
    assert resolved["blocked_reasons"]


# ---------------------------------------------------------------------------
# the queue: an intent is not a delivery
# ---------------------------------------------------------------------------


def test_the_queue_vocabulary_excludes_the_words_gate_104_reserved():
    from nativeforge.services.tenant_nofo_digest_builder_service import (
        DELIVERED_STATUSES,
    )

    assert not (queue.DELIVERY_INTENT_STATES & DELIVERED_STATUSES)
    assert "queued" not in queue.DELIVERY_INTENT_STATES
    assert "sent" not in queue.DELIVERY_INTENT_STATES


def test_an_intent_is_recorded_with_the_send_disabled_reason(demo_session):
    from nativeforge.db.session import SessionLocal

    with SessionLocal() as session:
        result = queue.record_delivery_intent(
            connection=session.connection(),
            organization_id=DEMO,
            digest_period_key="weekly|2026-01-01|2026-01-08",
            cadence="weekly",
            recipient_fingerprint="a" * 32,
            recipient_domain=f"fixture.{FIXTURE_DOMAIN}",
            recipient_source="org_membership",
            recipient_verified=True,
            digest_deliverable=True,
            send_activated=False,
            provider_configured=False,
        )
        session.commit()
    assert result["rows_written"] == 1
    assert result["delivery_status"] == "send_disabled"
    assert result["blocked_reason"] == "no_email_provider_configured"
    assert result["emails_sent"] == 0
    assert queue_invariant_failures_ok(result)


def queue_invariant_failures_ok(result) -> bool:
    return queue.queue_invariant_failures(result) == []


def test_an_address_offered_as_a_fingerprint_is_refused(demo_session):
    from nativeforge.db.session import SessionLocal

    with SessionLocal() as session:
        result = queue.record_delivery_intent(
            connection=session.connection(),
            organization_id=DEMO,
            digest_period_key="weekly|2026-01-01|2026-01-08",
            cadence="weekly",
            recipient_fingerprint=FIXTURE_ADDRESS,
            recipient_source="org_membership",
            recipient_verified=True,
            digest_deliverable=True,
        )
    assert result["rows_written"] == 0
    assert "recipient_fingerprint_is_an_address" in result["blocked_reasons"]


def test_an_unverified_recipient_is_recorded_as_refused(demo_session):
    from nativeforge.db.session import SessionLocal

    with SessionLocal() as session:
        result = queue.record_delivery_intent(
            connection=session.connection(),
            organization_id=DEMO,
            digest_period_key="weekly|2026-01-01|2026-01-08",
            cadence="weekly",
            recipient_fingerprint="b" * 32,
            recipient_source="org_membership",
            recipient_verified=False,
            digest_deliverable=True,
        )
        session.commit()
    assert result["delivery_status"] == "recipient_refused"
    assert result["blocked_reason"] == "recipient_not_verified"


@pytest.mark.parametrize("field", sorted(queue.CALLER_MAY_NOT_SET))
def test_a_caller_may_not_set_a_send_field(demo_session, field):
    result = queue.prepare_delivery_intent(
        organization_id=DEMO,
        digest_period_key="weekly|x|y",
        cadence="weekly",
        recipient_fingerprint="c" * 32,
        recipient_source="org_membership",
        recipient_verified=True,
        digest_deliverable=True,
        **{field: True},
    )
    assert result["storage_allowed"] is False
    assert f"caller_may_not_set:{field}" in result["blocked_reasons"]


def test_a_substitute_anchor_is_refused():
    for key in ("tenant_id", "customer_org_id", "organization_profile_id"):
        result = queue.prepare_delivery_intent(
            organization_id=DEMO,
            digest_period_key="weekly|x|y",
            cadence="weekly",
            recipient_fingerprint="d" * 32,
            recipient_source="org_membership",
            recipient_verified=True,
            digest_deliverable=True,
            **{key: "something"},
        )
        assert f"not_an_anchor_for_a_delivery_intent:{key}" in result["blocked_reasons"]


def test_the_same_recipient_is_not_recorded_twice_for_one_period(demo_session):
    from nativeforge.db.session import SessionLocal

    kwargs = {
        "organization_id": DEMO,
        "digest_period_key": "weekly|2026-01-01|2026-01-08",
        "cadence": "weekly",
        "recipient_fingerprint": "e" * 32,
        "recipient_source": "org_membership",
        "recipient_verified": True,
        "digest_deliverable": True,
    }
    with SessionLocal() as session:
        first = queue.record_delivery_intent(connection=session.connection(), **kwargs)
        second = queue.record_delivery_intent(connection=session.connection(), **kwargs)
        session.commit()
    assert first["rows_written"] == 1
    assert second["rows_written"] == 0
    assert (
        "this_recipient_is_already_recorded_for_this_period"
        in second["blocked_reasons"]
    )


def test_a_different_period_may_be_recorded(demo_session):
    """Otherwise a tenant is recorded once and refused every week after."""
    from nativeforge.db.session import SessionLocal

    with SessionLocal() as session:
        for period in ("weekly|2026-01-01|2026-01-08", "weekly|2026-01-08|2026-01-15"):
            result = queue.record_delivery_intent(
                connection=session.connection(),
                organization_id=DEMO,
                digest_period_key=period,
                cadence="weekly",
                recipient_fingerprint="f" * 32,
                recipient_source="org_membership",
                recipient_verified=True,
                digest_deliverable=True,
            )
            assert result["rows_written"] == 1, period
        session.commit()


def test_cancelling_keeps_the_row(demo_session):
    from nativeforge.db.session import SessionLocal

    with SessionLocal() as session:
        written = queue.record_delivery_intent(
            connection=session.connection(),
            organization_id=DEMO,
            digest_period_key="weekly|2026-01-01|2026-01-08",
            cadence="weekly",
            recipient_fingerprint="1" * 32,
            recipient_source="org_membership",
            recipient_verified=True,
            digest_deliverable=True,
        )
        cancelled = queue.cancel_delivery_intent(
            connection=session.connection(),
            organization_id=DEMO,
            intent_id=written["intent_id"],
        )
        session.commit()
        active = queue.list_delivery_intents(
            connection=session.connection(), organization_id=DEMO
        )
        everything = queue.list_delivery_intents(
            connection=session.connection(),
            organization_id=DEMO,
            include_cancelled=True,
        )
    assert cancelled["rows_written"] == 1
    assert cancelled["rows_deleted"] == 0
    assert active["rows_read"] == 0
    assert everything["rows_read"] == 1


def test_intents_are_org_scoped(demo_session):
    from nativeforge.db.session import SessionLocal

    with SessionLocal() as session:
        queue.record_delivery_intent(
            connection=session.connection(),
            organization_id=DEMO,
            digest_period_key="weekly|2026-01-01|2026-01-08",
            cadence="weekly",
            recipient_fingerprint="2" * 32,
            recipient_source="org_membership",
            recipient_verified=True,
            digest_deliverable=True,
        )
        session.commit()
        mine = queue.list_delivery_intents(
            connection=session.connection(), organization_id=DEMO
        )
        theirs = queue.list_delivery_intents(
            connection=session.connection(), organization_id=OTHER
        )
    assert mine["rows_read"] == 1
    assert theirs["rows_read"] == 0


def test_the_database_refuses_a_row_that_claims_a_send(demo_session):
    """A CHECK, so a service cannot store one by forgetting."""
    from nativeforge.db.session import SessionLocal

    with SessionLocal() as session:
        with pytest.raises(Exception):  # noqa: B017 - dialect-specific error type
            session.execute(
                sa.text(
                    "INSERT INTO nf_digest_delivery_intents "
                    "(id, organization_id, is_demo, digest_period_key, cadence, "
                    "recipient_fingerprint, recipient_source, recipient_verified, "
                    "items_total, items_visible, delivery_status, blocked_reason, "
                    "send_attempted, provider_contacted, emails_sent, fact_status, "
                    "created_at, recorded_at) VALUES "
                    "(:i, :o, 1, 'p', 'weekly', :f, 'org_membership', 1, 0, 0, "
                    "'dry_run_recorded', 'send_activation_absent', 1, 0, 0, "
                    "'demo_fixture', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
                ),
                {
                    "i": uuid.uuid4().hex,
                    "o": uuid.UUID(DEMO).hex,
                    "f": "3" * 32,
                },
            )
        session.rollback()


def test_the_database_refuses_a_status_gate_104_reserved(demo_session):
    from nativeforge.db.session import SessionLocal

    with SessionLocal() as session:
        with pytest.raises(Exception):  # noqa: B017
            session.execute(
                sa.text(
                    "INSERT INTO nf_digest_delivery_intents "
                    "(id, organization_id, is_demo, digest_period_key, cadence, "
                    "recipient_fingerprint, recipient_source, recipient_verified, "
                    "items_total, items_visible, delivery_status, blocked_reason, "
                    "send_attempted, provider_contacted, emails_sent, fact_status, "
                    "created_at, recorded_at) VALUES "
                    "(:i, :o, 1, 'p', 'weekly', :f, 'org_membership', 1, 0, 0, "
                    "'sent', 'unknown', 0, 0, 0, 'demo_fixture', "
                    "CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
                ),
                {
                    "i": uuid.uuid4().hex,
                    "o": uuid.UUID(DEMO).hex,
                    "f": "4" * 32,
                },
            )
        session.rollback()


def test_the_database_refuses_an_address_in_the_fingerprint_column(demo_session):
    from nativeforge.db.session import SessionLocal

    with SessionLocal() as session:
        with pytest.raises(Exception):  # noqa: B017
            session.execute(
                sa.text(
                    "INSERT INTO nf_digest_delivery_intents "
                    "(id, organization_id, is_demo, digest_period_key, cadence, "
                    "recipient_fingerprint, recipient_source, recipient_verified, "
                    "items_total, items_visible, delivery_status, blocked_reason, "
                    "send_attempted, provider_contacted, emails_sent, fact_status, "
                    "created_at, recorded_at) VALUES "
                    "(:i, :o, 1, 'p', 'weekly', :f, 'org_membership', 1, 0, 0, "
                    "'dry_run_recorded', 'send_activation_absent', 0, 0, 0, "
                    "'demo_fixture', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
                ),
                {
                    "i": uuid.uuid4().hex,
                    "o": uuid.UUID(DEMO).hex,
                    "f": FIXTURE_ADDRESS,
                },
            )
        session.rollback()


# ---------------------------------------------------------------------------
# the routes
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "method,path",
    [
        ("GET", f"{_base()}/digest/delivery/preview"),
        ("GET", f"{_base()}/digest/delivery/recipients"),
        ("POST", f"{_base()}/digest/delivery/dry-run"),
        ("GET", f"{_base()}/digest/delivery/intents"),
        ("POST", f"{_base()}/digest/delivery/cancel"),
        ("GET", f"{_base()}/digest/delivery/readiness"),
    ],
)
def test_every_delivery_route_refuses_an_unauthenticated_caller(client, method, path):
    assert client.request(method, path, json={}).status_code == 401


def test_a_forged_dev_header_authorizes_nothing(client):
    response = client.get(
        f"{_base()}/digest/delivery/readiness",
        headers=soh.forged_header_only(uuid.UUID(DEMO)),
    )
    assert response.status_code == 401


def test_the_preview_route_sends_nothing(client, demo_session):
    response = client.get(f"{_base()}/digest/delivery/preview", headers=demo_session)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["delivery_status"] == "preview_only"
    assert body["email_delivery"] is False
    assert body["emails_sent"] == 0
    assert body["send_attempted"] is False
    assert body["provider_contacted"] is False
    assert not ADDRESS_SHAPE.search(json.dumps(body))


def test_the_recipients_route_returns_no_address(client, demo_session):
    response = client.get(f"{_base()}/digest/delivery/recipients", headers=demo_session)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["deliverable_count"] >= 1
    assert body["addresses_reported"] is False
    assert not ADDRESS_SHAPE.search(json.dumps(body))
    for recipient in body["recipients"]:
        if recipient["deliverable"]:
            assert len(recipient["recipient_fingerprint"]) == 32
        else:
            # A member with no address on file is refused by name, not dropped.
            assert recipient["blocked_reasons"]


def test_the_dry_run_records_an_intent_with_an_audit_event(client, demo_session):
    from nativeforge.db.session import SessionLocal

    response = client.post(
        f"{_base()}/digest/delivery/dry-run",
        json={"cadence": "weekly"},
        headers=demo_session,
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["rows_written"] >= 1
    assert body["emails_sent"] == 0
    assert body["send_attempted"] is False
    assert body["provider_contacted"] is False
    assert body["send_disabled_reason"] == "no_email_provider_configured"

    audit_id = uuid.UUID(body["audit_event_id"])
    with SessionLocal() as session:
        found = session.execute(
            sa.text("SELECT action FROM nf_audit_events WHERE id = :i"),
            {"i": audit_id.hex},
        ).scalar_one()
    assert found == "digest_delivery_intent_recorded"


def test_the_dry_run_stores_no_address(client, demo_session):
    from nativeforge.db.session import SessionLocal

    client.post(
        f"{_base()}/digest/delivery/dry-run",
        json={"cadence": "weekly"},
        headers=demo_session,
    )
    with SessionLocal() as session:
        rows = session.execute(
            sa.text(
                "SELECT recipient_fingerprint, recipient_domain "
                "FROM nf_digest_delivery_intents"
            )
        ).all()
    assert rows
    for fingerprint, domain in rows:
        assert len(fingerprint) == 32
        assert "@" not in fingerprint
        assert "@" not in (domain or "")


def test_a_second_dry_run_for_the_same_period_is_refused(client, demo_session):
    first = client.post(
        f"{_base()}/digest/delivery/dry-run",
        json={"cadence": "weekly"},
        headers=demo_session,
    )
    assert first.status_code == 201
    second = client.post(
        f"{_base()}/digest/delivery/dry-run",
        json={"cadence": "weekly"},
        headers=demo_session,
    )
    assert second.status_code == 422
    assert "already_recorded_for_this_period" in json.dumps(second.json())


def test_a_refused_dry_run_leaves_no_audit_event(client, demo_session):
    """An audit event for something that did not happen is worse than none."""
    from nativeforge.db.session import SessionLocal

    client.post(
        f"{_base()}/digest/delivery/dry-run",
        json={"cadence": "weekly"},
        headers=demo_session,
    )
    with SessionLocal() as session:
        before = session.execute(
            sa.text(
                "SELECT COUNT(*) FROM nf_audit_events "
                "WHERE action = 'digest_delivery_intent_recorded'"
            )
        ).scalar_one()

    refused = client.post(
        f"{_base()}/digest/delivery/dry-run",
        json={"cadence": "weekly"},
        headers=demo_session,
    )
    assert refused.status_code == 422

    with SessionLocal() as session:
        after = session.execute(
            sa.text(
                "SELECT COUNT(*) FROM nf_audit_events "
                "WHERE action = 'digest_delivery_intent_recorded'"
            )
        ).scalar_one()
    assert after == before


@pytest.mark.parametrize("field", sorted(CALLER_MAY_NOT_SET))
def test_a_caller_may_not_relabel_a_dry_run(client, demo_session, field):
    refused = client.post(
        f"{_base()}/digest/delivery/dry-run",
        json={"cadence": "weekly", field: "verified"},
        headers=demo_session,
    )
    assert refused.status_code in {400, 422}
    assert field in json.dumps(refused.json())


def test_an_unrecognised_cadence_is_refused(client, demo_session):
    refused = client.get(
        f"{_base()}/digest/delivery/preview?cadence=hourly", headers=demo_session
    )
    assert refused.status_code == 422
    assert "cadence_not_recognised" in json.dumps(refused.json())


def test_another_organization_cannot_read_this_ones_intents(client, demo_session):
    soh.ensure_member(OTHER)
    other = soh.session_headers(uuid.UUID(OTHER))
    for path in ("intents", "preview", "recipients", "readiness"):
        response = client.get(f"{_base(OTHER)}/digest/delivery/{path}", headers=other)
        assert response.status_code in {200, 403, 404, 422}, path
        if response.status_code == 200:
            assert not ADDRESS_SHAPE.search(json.dumps(response.json())), path


def test_the_readiness_route_names_what_is_missing(client, demo_session):
    response = client.get(f"{_base()}/digest/delivery/readiness", headers=demo_session)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["email_delivery"] is False
    assert body["provider_configured"] is False
    assert body["send_activated"] is False
    assert body["production_email_delivery"] is False
    assert set(body["missing_configuration"]) == set(REQUIRED_SETTING_NAMES)
    assert not ADDRESS_SHAPE.search(json.dumps(body))


def test_the_route_smoke_proves_every_lane(client, demo_session):
    soh.ensure_member(OTHER)
    smoke = run_digest_delivery_route_smoke(
        client=client,
        organization_id=DEMO,
        other_organization_id=OTHER,
        session_headers=demo_session,
    )
    assert smoke["blocked_reasons"] == [], smoke["blocked_reasons"]
    assert smoke["end_to_end_completed"] is True
    assert delivery_route_smoke_invariant_failures(smoke) == []
    assert smoke["emails_sent"] == 0
    assert smoke["provider_contacted"] is False
    assert smoke["no_address_in_any_response"] is True


# ---------------------------------------------------------------------------
# readiness
# ---------------------------------------------------------------------------


def _proofs(**overrides):
    base = {
        "render_proof": {"deliverable": True},
        "recipient_proof": {"deliverable_count": 1},
        "queue_proof": {
            "rows_written": 1,
            "blocked_reason": "no_email_provider_configured",
        },
        "audit_proof": {"audit_event_recorded": True},
        "tenant_digest_operational": True,
        "customer_persistence_live": True,
    }
    base.update(overrides)
    return base


def test_readiness_is_true_and_delivery_is_false():
    readiness = build_email_delivery_readiness(**_proofs())
    assert readiness["email_delivery_readiness"] is True
    assert readiness["email_delivery"] is False
    assert readiness["scope"] == SCOPE_CONTROLLED
    assert readiness["blocked_reasons"] == []
    assert delivery_readiness_invariant_failures(readiness) == []


def test_readiness_does_not_require_a_provider_or_activation():
    readiness = build_email_delivery_readiness(**_proofs())
    assert readiness["provider_required_for_readiness"] is False
    assert readiness["send_activation_required_for_readiness"] is False
    assert readiness["real_recipient_required_for_readiness"] is False


@pytest.mark.parametrize(
    "override,reason",
    [
        ({"render_proof": {"deliverable": False}}, "did_not_render"),
        ({"recipient_proof": {"deliverable_count": 0}}, "no_recipient_validated"),
        ({"queue_proof": {"rows_written": 0}}, "was_not_written"),
        ({"audit_proof": {"audit_event_recorded": False}}, "no_audit_event"),
        ({"tenant_digest_operational": False}, "tenant_digest_is_not_operational"),
        ({"customer_persistence_live": False}, "customer_persistence_is_not_live"),
    ],
)
def test_readiness_is_false_without_each_piece(override, reason):
    readiness = build_email_delivery_readiness(**_proofs(**override))
    assert readiness["email_delivery_readiness"] is False
    assert readiness["scope"] == SCOPE_NONE
    assert any(reason in r for r in readiness["blocked_reasons"]), readiness[
        "blocked_reasons"
    ]


def test_readiness_is_false_when_the_route_module_is_absent(tmp_path):
    readiness = build_email_delivery_readiness(**_proofs(), repo_root=tmp_path)
    assert readiness["email_delivery_readiness"] is False
    assert any("route_module_does_not_exist" in r for r in readiness["blocked_reasons"])


def test_readiness_is_false_if_anything_sent_email():
    readiness = build_email_delivery_readiness(
        **_proofs(
            queue_proof={
                "rows_written": 1,
                "blocked_reason": "no_email_provider_configured",
                "emails_sent": 3,
            }
        )
    )
    assert readiness["email_delivery_readiness"] is False
    assert "email_was_sent:3" in readiness["blocked_reasons"]


def test_readiness_is_false_if_an_address_was_stored():
    readiness = build_email_delivery_readiness(
        **_proofs(
            queue_proof={
                "rows_written": 1,
                "blocked_reason": "no_email_provider_configured",
                "addresses_stored": True,
            }
        )
    )
    assert readiness["email_delivery_readiness"] is False
    assert "a_recipient_address_was_stored" in readiness["blocked_reasons"]


@pytest.mark.parametrize(
    "field",
    [
        "provider_contacted",
        "send_attempted",
        "recipient_addresses_stored",
        "recipient_addresses_reported",
        "production_email_delivery",
        "customer_auth_live",
        "real_organization_touched",
    ],
)
def test_readiness_never_claims(field):
    readiness = build_email_delivery_readiness(**_proofs())
    assert readiness[field] is False


def test_readiness_names_what_it_does_not_approve():
    readiness = build_email_delivery_readiness()
    assert set(NOT_APPROVED) <= set(readiness["not_approved"])


def test_the_readiness_invariants_catch_a_rehearsal_that_activated_delivery():
    forged = {
        **build_email_delivery_readiness(**_proofs()),
        "email_delivery": True,
    }
    failures = delivery_readiness_invariant_failures(forged)
    assert "a_rehearsal_activated_email_delivery" in failures
    assert "email_delivery_without_send_activation" in failures


def test_customer_auth_live_is_not_silently_made_true():
    readiness = build_email_delivery_readiness(**_proofs())
    assert readiness["email_delivery_readiness"] is True
    assert readiness["customer_auth_live"] is False


# ---------------------------------------------------------------------------
# the artifacts
# ---------------------------------------------------------------------------


def test_the_artifact_writes_every_declared_file(tmp_path):
    result = art.write_email_delivery_artifacts(repo_root=tmp_path)
    assert art.email_delivery_artifact_invariant_failures(result) == []
    for name in art.ARTIFACT_FILES:
        assert (tmp_path / art.ARTIFACT_DIR / name).is_file(), name


def test_the_artifact_is_deterministic():
    first = art.build_email_delivery_artifacts()
    second = art.build_email_delivery_artifacts()
    assert first == second


def test_the_artifact_reports_readiness_and_no_delivery():
    files = art.build_email_delivery_artifacts()
    readiness = json.loads(files["email_delivery_readiness.json"])
    assert readiness["email_delivery_readiness"] is True
    assert readiness["email_delivery"] is False
    assert readiness["scope"] == SCOPE_CONTROLLED
    assert readiness["invariant_failures"] == []


def test_no_artifact_carries_an_address():
    """The whole point of the gate: no mailbox in a committed file."""
    for name, body in art.build_email_delivery_artifacts().items():
        found = ADDRESS_SHAPE.search(body)
        assert not found, (name, found.group(0)[:3] if found else "")


def test_no_artifact_carries_the_digest_body():
    files = art.build_email_delivery_artifacts()
    render = json.loads(files["digest_delivery_render_smoke.json"])
    assert render["body_text_committed"] is False
    assert "body_text" not in render["render_shape"]


def test_the_artifact_records_the_database_guarantees():
    files = art.build_email_delivery_artifacts()
    queue_file = json.loads(files["dry_run_delivery_queue_smoke.json"])
    assert queue_file["intents_claiming_a_send"] == 0
    assert queue_file["intents_with_an_address_shaped_fingerprint"] == 0
    assert queue_file["intents_for_the_real_org"] == 0
    assert queue_file["non_fixture_intents"] == 0
    assert queue_file["an_intent_is_not_a_queue_position"] is True


def test_the_committed_artifacts_match_what_the_service_builds():
    directory = REPO_ROOT / art.ARTIFACT_DIR
    for name, body in art.build_email_delivery_artifacts().items():
        committed = directory / name
        assert committed.is_file(), name
        assert committed.read_text(encoding="utf-8") == body, name
