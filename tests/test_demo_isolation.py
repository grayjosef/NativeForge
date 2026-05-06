"""NF-001 demo isolation helpers (model-agnostic)."""

from __future__ import annotations

import uuid

import pytest

from nativeforge.lib.demo_isolation import (
    DemoIsolationError,
    assert_demo_route_org,
    assert_real_route_org,
    can_read_record,
    org_type_for,
    parse_demo_org_ids,
    require_explicit_demo_seed_context,
    row_matches_reader_org_type,
    validate_record_write,
)


def test_parse_demo_org_ids_roundtrip() -> None:
    a = uuid.uuid4()
    b = uuid.uuid4()
    s = f"{a}, {b}"
    got = parse_demo_org_ids(s)
    assert got == frozenset({a, b})
    assert parse_demo_org_ids("") == frozenset()


def test_org_type_for_allowlist() -> None:
    demo_id = uuid.uuid4()
    other = uuid.uuid4()
    demo_ids = frozenset({demo_id})
    assert org_type_for(demo_id, demo_ids) == "demo"
    assert org_type_for(other, demo_ids) == "real"


def test_row_matches_reader_org_type() -> None:
    assert row_matches_reader_org_type("demo", True) is True
    assert row_matches_reader_org_type("demo", False) is False
    assert row_matches_reader_org_type("real", False) is True
    assert row_matches_reader_org_type("real", True) is False


def test_can_read_record_same_org() -> None:
    oid = uuid.uuid4()
    assert (
        can_read_record(
            reader_org_id=oid,
            reader_org_type="demo",
            record_org_id=oid,
            record_is_demo=True,
        )
        is True
    )
    assert (
        can_read_record(
            reader_org_id=oid,
            reader_org_type="demo",
            record_org_id=oid,
            record_is_demo=False,
        )
        is False
    )


def test_can_read_record_cross_org_blocked() -> None:
    a = uuid.uuid4()
    b = uuid.uuid4()
    assert (
        can_read_record(
            reader_org_id=a,
            reader_org_type="real",
            record_org_id=b,
            record_is_demo=False,
        )
        is False
    )


def test_validate_record_write_mismatch_raises() -> None:
    real_org = uuid.uuid4()
    demo_ids = frozenset({uuid.uuid4()})
    with pytest.raises(DemoIsolationError):
        validate_record_write(
            org_id=real_org,
            record_is_demo=True,
            demo_org_ids=demo_ids,
        )


def test_validate_record_write_demo_org_requires_demo_flag() -> None:
    demo_org = uuid.uuid4()
    demo_ids = frozenset({demo_org})
    with pytest.raises(DemoIsolationError):
        validate_record_write(
            org_id=demo_org,
            record_is_demo=False,
            demo_org_ids=demo_ids,
        )


def test_route_assert_helpers() -> None:
    assert_demo_route_org("demo")
    with pytest.raises(DemoIsolationError):
        assert_demo_route_org("real")
    assert_real_route_org("real")
    with pytest.raises(DemoIsolationError):
        assert_real_route_org("demo")


def test_explicit_demo_seed_gate() -> None:
    require_explicit_demo_seed_context(
        is_demo_content=False,
        explicit_demo_context=False,
    )
    require_explicit_demo_seed_context(
        is_demo_content=True,
        explicit_demo_context=True,
    )
    with pytest.raises(DemoIsolationError):
        require_explicit_demo_seed_context(
            is_demo_content=True,
            explicit_demo_context=False,
        )
