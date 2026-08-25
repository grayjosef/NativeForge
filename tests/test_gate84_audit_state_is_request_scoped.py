"""Gate 84 — audit state is request-scoped, not module-level.

Thirty services used to keep a module-level ``_AUDIT`` list that lived for the
life of the process. Output depended on call history, the lists grew without
bound, and demo determinism needed a workaround to clear them.
"""

from __future__ import annotations

import re
import warnings
from pathlib import Path

import pytest

from nativeforge.services.audit_event_collector_service import (
    SCHEMA_VERSION,
    AuditEventCollector,
    NoopAuditCollector,
    collector_invariant_failures,
    new_collector,
)

warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parents[1]
SERVICES = ROOT / "src" / "nativeforge" / "services"

# One representative call per patched service, chosen so the call emits at least
# one audit event where the service emits at all.
CALLS: list[tuple[str, str]] = [
    ("gate31_live_authority_service", "resolve_live_authority"),
    ("gate31_live_source_coverage_service", "resolve_live_source_coverage"),
    ("gate31_pilot_onboarding_service", "resolve_invite_readiness"),
    ("gate31_support_triage_service", "resolve_support_triage"),
    ("gate32_backup_restore_service", "resolve_backup_restore"),
    ("gate32_launch_packet_service", "build_launch_packet"),
    ("gate32_observability_service", "resolve_observability"),
    ("gate32_source_freshness_service", "run_source_freshness_bundle"),
    ("gate33_healthcheck_service", "resolve_healthchecks"),
    ("gate33_restore_rehearsal_service", "run_restore_rehearsal"),
    ("gate33_runbook_service", "resolve_runbooks_and_checklist"),
    ("gate33_source_probe_service", "run_source_probe_bundle"),
    ("gate34_owner_wait_service", "resolve_owner_wait_state"),
    ("session_tenant_enforcement_service", "run_session_tenant_enforcement_suite"),
]

AUDIT_REF_CALLS = [
    ("gate31_live_authority_service", "resolve_live_authority"),
    ("gate31_live_source_coverage_service", "resolve_live_source_coverage"),
    ("gate31_support_triage_service", "resolve_support_triage"),
    ("gate32_backup_restore_service", "resolve_backup_restore"),
    ("gate32_source_freshness_service", "run_source_freshness_bundle"),
    ("gate33_restore_rehearsal_service", "run_restore_rehearsal"),
    ("gate33_source_probe_service", "run_source_probe_bundle"),
]


def _call(module_name: str, fn_name: str, **kwargs):
    import importlib

    mod = importlib.import_module(f"nativeforge.services.{module_name}")
    return getattr(mod, fn_name)(**kwargs)


# --------------------------------------------------------------------------
# No module-level audit state anywhere
# --------------------------------------------------------------------------


def test_no_service_declares_a_module_level_audit_list() -> None:
    offenders = [
        p.name
        for p in SERVICES.glob("*.py")
        if re.search(r"^_AUDIT\s*:?[^=]*=\s*\[\]", p.read_text(encoding="utf-8"), re.M)
    ]
    assert offenders == [], offenders


def test_no_service_appends_to_a_module_level_audit_list() -> None:
    offenders = [
        p.name
        for p in SERVICES.glob("*.py")
        if re.search(r"\b_AUDIT\.(append|extend)\(", p.read_text(encoding="utf-8"))
    ]
    assert offenders == [], offenders


def test_no_service_reads_a_module_level_audit_list() -> None:
    offenders = []
    for p in SERVICES.glob("*.py"):
        text = p.read_text(encoding="utf-8")
        if re.search(r"\blist\(_AUDIT\)|\blen\(_AUDIT\)|\b_AUDIT\[", text):
            offenders.append(p.name)
    assert offenders == [], offenders


def test_the_deleted_reset_helpers_are_gone() -> None:
    """They existed only to undo the accumulation."""
    offenders = []
    for p in SERVICES.glob("*.py"):
        text = p.read_text(encoding="utf-8")
        if re.search(r"def clear_[a-z0-9_]*audit[a-z0-9_]*_for_tests", text):
            offenders.append(p.name)
    assert offenders == [], offenders


def test_collector_module_holds_no_mutable_global() -> None:
    import nativeforge.services.audit_event_collector_service as mod

    mutable = {
        name: type(getattr(mod, name)).__name__
        for name in dir(mod)
        if not name.startswith("__")
        and isinstance(getattr(mod, name), (list, dict, set))
    }
    assert mutable == {}, mutable


# --------------------------------------------------------------------------
# The collector itself
# --------------------------------------------------------------------------


def test_two_collectors_are_isolated() -> None:
    a, b = AuditEventCollector(), AuditEventCollector()
    a.record("only_a")
    assert a.event_names() == ["only_a"]
    assert b.event_names() == []


def test_record_returns_the_stored_event() -> None:
    c = AuditEventCollector()
    entry = c.record("deploy", {"target": "prod"})
    assert entry["event"] == "deploy"
    assert entry["target"] == "prod"
    assert c.snapshot()[0] == entry


def test_snapshot_is_a_copy_and_does_not_mutate() -> None:
    c = AuditEventCollector()
    c.record("x")
    snap = c.snapshot()
    assert isinstance(snap, tuple)
    snap[0]["event"] = "tampered"
    assert c.event_names() == ["x"]
    assert len(c) == 1


def test_tail_does_not_mutate_and_respects_count() -> None:
    c = AuditEventCollector()
    for i in range(5):
        c.record(f"e{i}")
    assert [e["event"] for e in c.tail(2)] == ["e3", "e4"]
    assert len(c) == 5
    assert c.tail(0) == []
    assert c.tail(-1) == []


def test_event_names_and_has_event() -> None:
    c = AuditEventCollector()
    c.record("alpha")
    c.record("beta")
    assert c.event_names() == ["alpha", "beta"]
    assert c.event_names(1) == ["beta"]
    assert c.has_event("beta") is True
    assert c.has_event("missing") is False


def test_clear_affects_only_that_instance() -> None:
    a, b = AuditEventCollector(), AuditEventCollector()
    a.record("x")
    b.record("y")
    a.clear()
    assert a.event_names() == []
    assert b.event_names() == ["y"]


def test_deterministic_event_ids_when_a_factory_is_supplied() -> None:
    def factory(index: int, event: str) -> str:
        return f"{event}-{index}"

    a = AuditEventCollector(event_id_factory=factory)
    b = AuditEventCollector(event_id_factory=factory)
    a.record("x")
    b.record("x")
    assert a.snapshot()[0]["event_id"] == b.snapshot()[0]["event_id"] == "x-0"


def test_no_event_id_without_a_factory() -> None:
    c = AuditEventCollector()
    assert "event_id" not in c.record("x")


def test_noop_collector_keeps_nothing_but_honours_the_interface() -> None:
    n = NoopAuditCollector()
    entry = n.record("ignored", {"k": 1})
    assert entry["event"] == "ignored"
    assert len(n) == 0
    assert n.snapshot() == ()
    assert n.has_event("ignored") is False


def test_new_collector_returns_the_callers_instance_or_a_fresh_one() -> None:
    mine = AuditEventCollector()
    assert new_collector(mine) is mine
    fresh = new_collector(None)
    assert isinstance(fresh, AuditEventCollector)
    assert fresh is not mine
    assert len(fresh) == 0


def test_collector_describe_and_invariants() -> None:
    c = AuditEventCollector()
    c.record("x")
    described = c.describe()
    assert described["schema_version"] == SCHEMA_VERSION
    assert described["request_scoped"] is True
    assert described["module_level_state"] is False
    assert collector_invariant_failures(described) == []


def test_invariants_reject_a_module_level_claim() -> None:
    c = AuditEventCollector()
    forged = dict(c.describe())
    forged["module_level_state"] = True
    assert "forbidden_claim:module_level_state" in collector_invariant_failures(forged)


# --------------------------------------------------------------------------
# Services no longer accumulate across calls
# --------------------------------------------------------------------------


@pytest.mark.parametrize("module_name,fn_name", AUDIT_REF_CALLS)
def test_repeated_calls_do_not_grow_audit_refs(module_name: str, fn_name: str) -> None:
    first = _call(module_name, fn_name)
    second = _call(module_name, fn_name)
    third = _call(module_name, fn_name)
    assert len(first["audit_refs"]) == len(second["audit_refs"])
    assert len(second["audit_refs"]) == len(third["audit_refs"])


@pytest.mark.parametrize("module_name,fn_name", AUDIT_REF_CALLS)
def test_repeated_calls_return_identical_audit_refs(
    module_name: str, fn_name: str
) -> None:
    assert _call(module_name, fn_name)["audit_refs"] == _call(
        module_name, fn_name
    )["audit_refs"]


@pytest.mark.parametrize("module_name,fn_name", AUDIT_REF_CALLS)
def test_audit_refs_are_not_empty_where_the_service_emits(
    module_name: str, fn_name: str
) -> None:
    """Scoping must not silently drop the trail."""
    assert _call(module_name, fn_name)["audit_refs"]


@pytest.mark.parametrize("module_name,fn_name", CALLS)
def test_one_call_cannot_see_another_calls_audit_events(
    module_name: str, fn_name: str
) -> None:
    a, b = AuditEventCollector(), AuditEventCollector()
    _call(module_name, fn_name, collector=a)
    _call(module_name, fn_name, collector=b)
    assert a.event_names() == b.event_names()
    # Same events, separate instances - neither accumulated the other's.
    assert len(a) == len(b)
    combined = AuditEventCollector()
    _call(module_name, fn_name, collector=combined)
    _call(module_name, fn_name, collector=combined)
    assert len(combined) == 2 * len(a), "a shared collector should accumulate"


def test_a_caller_owns_the_request_boundary() -> None:
    """Two calls share a trail only when the caller says so."""
    from nativeforge.services.gate32_backup_restore_service import (
        resolve_backup_restore,
    )

    isolated_one = resolve_backup_restore()
    isolated_two = resolve_backup_restore()
    assert isolated_one["audit_refs"] == isolated_two["audit_refs"]

    shared = AuditEventCollector()
    resolve_backup_restore(collector=shared)
    second = resolve_backup_restore(collector=shared)
    assert len(second["audit_refs"]) > len(isolated_one["audit_refs"])


# --------------------------------------------------------------------------
# Audit content preserved
# --------------------------------------------------------------------------


def test_backup_restore_event_content_is_preserved() -> None:
    from nativeforge.services.gate32_backup_restore_service import (
        resolve_backup_restore,
    )

    collector = AuditEventCollector()
    resolve_backup_restore(collector=collector, non_prod_rehearsed=True)
    event = collector.snapshot()[0]
    assert event["event"] == "restore_rehearsal"
    assert event["non_prod"] is True


def test_services_that_stamped_a_time_still_do() -> None:
    """Two services recorded an `at` timestamp; the refactor must keep it."""
    from nativeforge.services.session_tenant_enforcement_service import (
        build_session_context,
    )

    collector = AuditEventCollector()
    build_session_context(collector=collector, status="expired")
    events = collector.snapshot()
    assert events
    assert all("at" in e for e in events), events


def test_session_suite_still_detects_its_own_denial_events() -> None:
    """The suite reads its own trail; scoping must not blind it."""
    from nativeforge.services.session_tenant_enforcement_service import (
        run_session_tenant_enforcement_suite,
    )

    result = run_session_tenant_enforcement_suite()
    assert result["denial_audit_events_present"] is True


def test_object_storage_status_counts_only_its_own_request() -> None:
    from nativeforge.services.object_storage_signed_url_service import (
        build_object_storage_adapter_status,
        generate_signed_upload_url,
    )

    collector = AuditEventCollector()
    generate_signed_upload_url(
        collector=collector,
        organization_profile_id="org_a",
        package_workspace_id="ws1",
        evidence_id="ev1",
        content_hash="deadbeef",
    )
    status = build_object_storage_adapter_status(collector=collector)
    assert status["audit_events_emitted"] == len(collector)
    assert build_object_storage_adapter_status()["audit_events_emitted"] == 0


# --------------------------------------------------------------------------
# Determinism no longer depends on the workaround
# --------------------------------------------------------------------------


def test_demo_generation_no_longer_resets_any_accumulator() -> None:
    from nativeforge.services.demo_payload_determinism_service import (
        ACCUMULATOR_ATTRS,
    )

    assert ACCUMULATOR_ATTRS == ()


def test_demo_payload_is_still_deterministic(tmp_path: Path) -> None:
    from nativeforge.services.sc_monday_demo_bridge_service import (
        write_sc_customer_demo_bridge_json,
    )

    first = tmp_path / "a.json"
    second = tmp_path / "b.json"
    write_sc_customer_demo_bridge_json(path=first)
    write_sc_customer_demo_bridge_json(path=second)
    assert first.read_bytes() == second.read_bytes()


def test_readiness_doc_still_claims_no_coverage() -> None:
    doc = ROOT / "docs" / "operations" / "471_GATE84_PRODUCTION_READINESS_DELTA.md"
    body = doc.read_text(encoding="utf-8")
    assert "Live SC source coverage:   NONE" in body
    assert "65% improvement:           NOT CLAIMED" in body
    assert "Controlled customer pilot: NO_GO" in body
