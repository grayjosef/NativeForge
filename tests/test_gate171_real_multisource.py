"""Gate 171: heterogeneous real multi-source ingestion.

Hermetic. Every test here runs on bytes supplied in-process or on rows already
in the database; nothing opens a socket, and the gate's approved live budget
is spent.

The centre of gravity is the L4 defect. Gate 167's unique index permitted
exactly one provisional opportunity in the whole graph, and only a second
source family that publishes no opportunity number could ever have shown it.
Those tests exist so it can never come back quietly.
"""

from __future__ import annotations

import json
import pathlib

import pytest

from nativeforge.services.canonical_opportunity_normalizer_service import (
    CANONICAL_FIELDS,
    lifecycle_for_status,
)
from nativeforge.services.cross_source_identity_service import (
    MACHINE_SETTLEABLE,
    PROVISIONAL_MATCH,
)
from nativeforge.services.source_adapter_contract_service import (
    DocumentReference,
    PageCursor,
    SourceDescriptor,
    adapter_contract_failures,
    canonical_url,
    deduplicate_documents,
    descriptor_failures,
    document_failures,
    identity_for_normalized,
    normalized_envelope_for,
    record_failures,
)
from nativeforge.services.source_adapters import bia_program_page_html as bia
from nativeforge.services.source_adapters import (
    federal_register_documents_json as fr,
)
from nativeforge.services.source_attribution_contract_service import (
    ATTRIBUTION_CONTRACTS,
    verify_recorded_notice,
)

REPO = pathlib.Path(__file__).resolve().parents[1]
MIGRATION = REPO / "alembic" / "versions" / "0056_provisional_identity_uniqueness.py"
LOOKUP_MIGRATION = REPO / "alembic" / "versions" / "0057_identity_lookup_index.py"
SEMANTICS_PHASE = REPO / "scripts" / "_g167_phase_graph_semantics.py"
ISOLATION_PHASE = REPO / "scripts" / "_g171_phase_sequential_isolation.py"
APPROVAL = (
    REPO / "fixtures" / "source_authorization" / "gate171_operator_approval.json"
)

BIA_HTML = (
    b"<html><head><title>Apply for a TTGP Grant</title></head><body>"
    b"<h1>Apply</h1><p>Program text.</p>"
    b'<a href="/media/nofo.pdf">NOFO</a><a href="/media/nofo.pdf">again</a>'
    b'<a href="/topic/grants?utm_source=news">More</a>'
    b'<a href="#skip">skip</a><a href="mailto:a@b.gov">mail</a>'
    b"</body></html>"
)


def fr_json(numbers: list[str], *, next_page: bool = False) -> bytes:
    return json.dumps(
        {
            "count": len(numbers),
            "next_page_url": "https://example.invalid/p2" if next_page else None,
            "results": [
                {
                    "document_number": n,
                    "title": f"Notice {n}",
                    "type": "Notice",
                    "publication_date": "2026-09-01",
                    "agencies": [{"name": "Department of the Interior"}],
                    "html_url": f"https://www.federalregister.gov/d/{n}",
                    "comments_close_on": "2026-11-01",
                }
                for n in numbers
            ],
        }
    ).encode("utf-8")


def bia_record():
    return bia.read_records(
        descriptor=bia.build_descriptor(),
        body_bytes=BIA_HTML,
        media_type="text/html",
        cursor=None,
    )[0]


def fr_record(number: str = "2026-11111"):
    return fr.read_records(
        descriptor=fr.build_descriptor(),
        body_bytes=fr_json([number]),
        media_type="application/json",
        cursor=None,
    )[0]


# ------------------------------------------------- the L4 defect


def test_the_migration_makes_the_identity_index_partial():
    """The one line that stopped the graph holding two provisional records."""
    text = MIGRATION.read_text(encoding="utf-8")
    assert "normalized_opportunity_number <> ''" in text
    assert "sqlite_where" in text
    assert "postgresql_where" in text


def test_the_migration_keeps_the_index_unique_and_on_the_same_columns():
    text = MIGRATION.read_text(encoding="utf-8")
    assert "unique=True" in text
    assert '"normalized_opportunity_number", "doc_type"' in text


def test_a_document_source_gets_a_provisional_identity_not_an_empty_l1():
    """An L1 with an empty key is what the write path refuses by name."""
    envelope = normalized_envelope_for(
        bia_record(), adapter_key=bia.ADAPTER_KEY
    )
    identity = identity_for_normalized(envelope, source_id="s")
    assert identity["identity_layer"] == "L4"
    assert identity["is_provisional"] is True
    assert len(str(identity["fuzzy_key"])) == 64


def test_an_api_source_with_a_published_number_gets_l1():
    envelope = normalized_envelope_for(fr_record(), adapter_key=fr.ADAPTER_KEY)
    identity = identity_for_normalized(envelope, source_id="s")
    assert identity["identity_layer"] == "L1"
    assert identity["is_provisional"] is False
    assert identity["normalized_opportunity_number"]


def test_two_document_records_produce_different_provisional_keys():
    """If these ever collide, one provisional record per graph returns."""
    first = bia.read_records(
        descriptor=bia.build_descriptor(source_url="https://www.bia.gov/a"),
        body_bytes=b"<html><head><title>Program A</title></head><body>x</body></html>",
        media_type="text/html",
        cursor=None,
    )[0]
    second = bia.read_records(
        descriptor=bia.build_descriptor(source_url="https://www.bia.gov/b"),
        body_bytes=b"<html><head><title>Program B</title></head><body>x</body></html>",
        media_type="text/html",
        cursor=None,
    )[0]
    a = identity_for_normalized(
        normalized_envelope_for(first, adapter_key=bia.ADAPTER_KEY), source_id="s"
    )
    b = identity_for_normalized(
        normalized_envelope_for(second, adapter_key=bia.ADAPTER_KEY), source_id="s"
    )
    assert a["fuzzy_key"] != b["fuzzy_key"]
    assert first.source_record_id != second.source_record_id


def test_a_provisional_match_can_never_machine_settle():
    assert PROVISIONAL_MATCH not in MACHINE_SETTLEABLE


# ------------------------------------------------- the access path


def test_0057_adds_a_second_non_unique_index_rather_than_widening_0056():
    """0056 fixed a collision and removed the lookup path in one stroke.

    A partial index only serves a query whose predicate implies its own, and
    the write path's lookup does not carry `<> ''`. 0.09ms became 9.85ms at
    50k and the full suite stayed green, because a scan is correct.
    """
    text = LOOKUP_MIGRATION.read_text(encoding="utf-8")
    assert "create_index" in text
    assert '"normalized_opportunity_number", "doc_type"' in text
    # Not unique: it imposes nothing, it only gives the planner something.
    assert "unique=True" not in text
    # And it must not have re-created the total unique index 0056 replaced.
    assert "sqlite_where" not in text


def test_the_constraint_and_the_access_path_are_different_indexes():
    constraint = MIGRATION.read_text(encoding="utf-8")
    lookup = LOOKUP_MIGRATION.read_text(encoding="utf-8")
    assert "uq_" in constraint
    assert "ix_" in lookup and "identity_lookup" in lookup


def test_the_identity_lookup_query_carries_no_index_predicate():
    """A caller must not have to know an index exists.

    Adding `AND normalized_opportunity_number <> ''` to the query would
    restore the plan and return nothing for exactly the provisional rows 0056
    exists to support.
    """
    from nativeforge.repositories import canonical_opportunity_batch_repository

    text = pathlib.Path(
        canonical_opportunity_batch_repository.__file__
    ).read_text(encoding="utf-8")
    assert "normalized_opportunity_number <> ''" not in text


# ------------------------------------------------- sequential isolation


def test_the_lineage_phase_reports_what_state_it_started_from():
    """A stale fixture and a regression must not look alike.

    Gate 171's battery produced a lineage failure that passed standalone and
    would not reproduce. Nothing recorded the starting state, so it could not
    be told apart from leftovers after the fact.
    """
    text = SEMANTICS_PHASE.read_text(encoding="utf-8")
    assert "g_started_from_a_clean_fixture" in text
    assert "g_versions_present_before_this_run" in text


def test_the_lineage_sort_is_unambiguous():
    """`versions[-1]` must mean the newest, not whatever the plan returned."""
    text = SEMANTICS_PHASE.read_text(encoding="utf-8")
    assert "ORDER BY created_at, version_id" in text


def test_the_supersession_chain_is_checked_against_the_timestamp_order():
    text = SEMANTICS_PHASE.read_text(encoding="utf-8")
    assert "g_timestamp_order_matches_supersession_order" in text
    assert "g_exactly_one_chain_root" in text


def test_the_sequential_isolation_phase_runs_each_step_in_its_own_process():
    """In-process reuse would share the very state it exists to detect."""
    text = ISOLATION_PHASE.read_text(encoding="utf-8")
    assert "subprocess.run" in text
    assert "sequential_lineage_isolation" in text


# ------------------------------------------------- the adapter bridge


def test_the_bridge_emits_only_canonical_fields():
    envelope = normalized_envelope_for(
        bia_record(), adapter_key=bia.ADAPTER_KEY
    )
    assert set(envelope["fields"]) <= set(CANONICAL_FIELDS)


def test_adapter_metrics_stay_out_of_the_canonical_fields():
    """Link counts are facts about a READ, not about an opportunity."""
    record = bia_record()
    assert record.metrics["document_count"] >= 1
    assert "document_count" not in record.fields
    envelope = normalized_envelope_for(record, adapter_key=bia.ADAPTER_KEY)
    assert "document_count" not in envelope["fields"]
    assert envelope["adapter_metrics"]["document_count"] >= 1


def test_a_field_the_source_does_not_publish_is_unsupported_not_absent():
    """The distinction that stops a missing value becoming a conflict."""
    envelope = normalized_envelope_for(
        bia_record(), adapter_key=bia.ADAPTER_KEY
    )
    assert "close_date" in envelope["fields_not_supported"]
    assert "close_date" not in envelope["fields_absent"]


def test_both_adapters_conform_to_the_contract():
    for module in (bia, fr):
        assert adapter_contract_failures(module) == []


def test_no_adapter_may_import_a_repository():
    for module in (bia, fr):
        text = pathlib.Path(module.__file__).read_text(encoding="utf-8")
        assert "from nativeforge.repositories" not in text
        assert "import nativeforge.repositories" not in text


def test_an_adapter_refuses_to_build_a_request_without_an_authorization():
    for module in (bia, fr):
        with pytest.raises(Exception):  # noqa: B017 - any refusal is the point
            module.build_request(
                descriptor=module.build_descriptor(),
                authorization=None,
                cursor=None,
            )


def test_an_adapter_refuses_the_wrong_media_type():
    with pytest.raises(ValueError):
        bia.read_records(
            descriptor=bia.build_descriptor(),
            body_bytes=BIA_HTML,
            media_type="application/json",
            cursor=None,
        )
    with pytest.raises(ValueError):
        fr.read_records(
            descriptor=fr.build_descriptor(),
            body_bytes=fr_json(["2026-1"]),
            media_type="text/html",
            cursor=None,
        )


def test_records_bind_to_the_evidence_that_produced_them():
    for record in (bia_record(), fr_record()):
        assert record_failures(record) == []
        assert len(record.evidence_sha256) == 64


# ------------------------------------------------- lifecycle vocabulary


@pytest.mark.parametrize("status", ["posted", "forecasted", "closed", "archived"])
def test_lifecycle_values_come_from_the_normalizer(status):
    """A hand-written fixture said "open" and rolled back 500 valid records."""
    assert lifecycle_for_status(status) in (
        "forecasted",
        "posted",
        "amended",
        "closed",
        "awarded",
        "archived",
        "unknown",
    )


def test_open_is_not_a_lifecycle_value():
    assert lifecycle_for_status("posted") != "open"


# ------------------------------------------------- bounded collection


def test_a_cursor_stops_even_when_the_source_always_claims_more():
    cursor = PageCursor(max_pages=2, max_records=100)
    for _ in range(10):
        cursor.observe_page(content_sha256=f"{cursor.page_index:064d}", record_count=1)
        if not cursor.should_continue(source_says_more=True):
            break
    assert cursor.terminated_because == "max_pages_reached"
    assert cursor.page_index <= 2


def test_the_same_bytes_twice_is_a_loop():
    cursor = PageCursor(max_pages=10, max_records=100)
    cursor.observe_page(content_sha256="a" * 64, record_count=1)
    cursor.observe_page(content_sha256="a" * 64, record_count=1)
    assert cursor.terminated_because == "repeated_page_detected"
    assert cursor.should_continue(source_says_more=True) is False


def test_a_single_document_descriptor_cannot_declare_more_than_one_page():
    descriptor = SourceDescriptor(
        source_id="s",
        adapter_key="a",
        display_name="n",
        publisher="p",
        base_url="https://example.invalid/x",
        pagination_model="single_document",
        max_pages=5,
    )
    assert any(
        "single_document_source_declaring_more_than_one_page" in f
        for f in descriptor_failures(descriptor)
    )


def test_an_unbounded_descriptor_is_refused():
    descriptor = SourceDescriptor(
        source_id="s",
        adapter_key="a",
        display_name="n",
        publisher="p",
        base_url="https://example.invalid/x",
        max_pages=0,
        max_records=0,
    )
    failures = descriptor_failures(descriptor)
    assert "max_pages_below_one" in failures
    assert "max_records_below_one" in failures


# ------------------------------------------------- document safety


def test_extracted_links_are_never_fetched():
    record = bia_record()
    assert record.documents
    assert all(document.fetched is False for document in record.documents)
    assert all(document.depth == 0 for document in record.documents)


def test_following_a_link_beyond_depth_zero_is_refused():
    followed = DocumentReference(
        url="https://www.bia.gov/deep.pdf", depth=1, fetched=True
    )
    assert any(
        "adapter_followed_a_link_beyond_depth_zero" in f
        for f in document_failures([followed], max_depth=0)
    )


def test_tracking_parameters_do_not_create_a_second_document():
    assert canonical_url("https://a.invalid/x?utm_source=n&id=2") == (
        "https://a.invalid/x?id=2"
    )


def test_identical_content_at_two_urls_is_suppressed():
    _, suppressed = deduplicate_documents(
        [
            DocumentReference(url="https://a.invalid/1", content_sha256="f" * 64),
            DocumentReference(url="https://a.invalid/2", content_sha256="f" * 64),
        ]
    )
    assert suppressed == 1


def test_anchors_and_mailto_links_are_not_documents():
    record = bia_record()
    assert not any(
        d.url.startswith(("#", "mailto:")) for d in record.documents
    )


# ------------------------------------------------- failure isolation


def test_a_malformed_payload_from_one_adapter_does_not_stop_the_other():
    with pytest.raises(Exception):  # noqa: B017
        bia.read_records(
            descriptor=bia.build_descriptor(),
            body_bytes=b"\x00 not markup",
            media_type="text/html",
            cursor=None,
        )
    assert len(fr.read_records(
        descriptor=fr.build_descriptor(),
        body_bytes=fr_json(["2026-2"]),
        media_type="application/json",
        cursor=None,
    )) == 1


def test_a_malformed_api_payload_does_not_stop_the_document_adapter():
    with pytest.raises(Exception):  # noqa: B017
        fr.read_records(
            descriptor=fr.build_descriptor(),
            body_bytes=b"{not json",
            media_type="application/json",
            cursor=None,
        )
    assert len(bia.read_records(
        descriptor=bia.build_descriptor(),
        body_bytes=BIA_HTML,
        media_type="text/html",
        cursor=None,
    )) == 1


def test_an_empty_body_is_no_records_rather_than_an_error():
    assert bia.read_records(
        descriptor=bia.build_descriptor(),
        body_bytes=b"",
        media_type="text/html",
        cursor=None,
    ) == []
    assert fr.read_records(
        descriptor=fr.build_descriptor(),
        body_bytes=b"",
        media_type="application/json",
        cursor=None,
    ) == []


def test_a_record_without_a_document_number_is_skipped_not_invented():
    body = json.dumps(
        {"count": 1, "next_page_url": None, "results": [{"title": "No number"}]}
    ).encode("utf-8")
    assert fr.read_records(
        descriptor=fr.build_descriptor(),
        body_bytes=body,
        media_type="application/json",
        cursor=None,
    ) == []


# ------------------------------------------------- authorization data


def test_activating_a_source_is_a_data_change():
    """The approval is a file, not a constant in a script."""
    approval = json.loads(APPROVAL.read_text(encoding="utf-8"))
    ids = {str(e["source_id"]) for e in approval["approved_sources"]}
    assert ids == {
        "nf-seed-2026-fed-007",
        "nf-seed-2026-api-federal-register-documents",
    }
    assert approval["approved_operator"] == "MAYHEM"


def test_the_approval_records_the_replacement_request():
    """The request my defect spent, and the one that replaced it."""
    approval = json.loads(APPROVAL.read_text(encoding="utf-8"))
    amendments = approval.get("amendments") or []
    assert amendments
    assert amendments[0]["spent_without_evidence"] == 1
    assert amendments[0]["replacement_requests_authorized"] == 1
    assert approval["maximum_total_requests"] == 5


def test_each_approved_source_declares_an_attribution_contract():
    approval = json.loads(APPROVAL.read_text(encoding="utf-8"))
    for entry in approval["approved_sources"]:
        assert entry["adapter_key"] in ATTRIBUTION_CONTRACTS


def test_an_attribution_notice_is_verified_verbatim():
    verdict = verify_recorded_notice(
        adapter_key=bia.ADAPTER_KEY,
        notice="Source: Bureau of Indian Affairs, U.S. Department of the Interior",
    )
    assert verdict["attribution_status"] == "present_and_verbatim"
    assert verdict["attribution_is_customer_visible"] is True


def test_one_edited_character_breaks_the_attribution():
    verdict = verify_recorded_notice(
        adapter_key=bia.ADAPTER_KEY,
        notice="Source: Bureau of Indian Affairs, US Department of the Interior",
    )
    assert verdict["attribution_status"] == "missing"


def test_an_adapter_with_no_contract_does_not_pass_by_default():
    verdict = verify_recorded_notice(adapter_key="nobody", notice="anything")
    assert verdict["result"] == "no_contract_declared"
    assert verdict["attribution_is_customer_visible"] is False
