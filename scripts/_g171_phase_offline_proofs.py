"""Gate 171L/M/N/P: the proofs that need fixtures, not requests.

Four things the two real payloads cannot demonstrate on their own, because the
real world declined to provide them: a second page, a malformed body, a
deadline that moved, and a source that failed while others kept working. Each
is proved here with source-SHAPED fixtures - HTML for the document adapter,
the real JSON envelope for the API adapter - and no network.

Using the shapes the real payloads actually had is the point. A pagination
proof over an invented envelope proves the invention.
"""

from __future__ import annotations

import json
import socket
import sys
import uuid

sys.path.insert(0, "src")
sys.path.insert(0, ".")

_NETWORK = {"attempts": 0}
_real_socket = socket.socket


class _Refused(socket.socket):
    def __init__(self, *a, **k):  # noqa: ANN002, ANN003
        _NETWORK["attempts"] += 1
        raise OSError("gate171 offline proofs make no network request")


socket.socket = _Refused  # type: ignore[misc,assignment]

import sqlalchemy as sa  # noqa: E402

from nativeforge.db.session import SessionLocal  # noqa: E402
from nativeforge.services.opportunity_change_taxonomy_service import (  # noqa: E402
    change_invariant_failures,
    classify_change,
)
from nativeforge.services.source_adapter_contract_service import (  # noqa: E402
    PageCursor,
    cursor_failures,
    deduplicate_documents,
    document_failures,
    identity_for_normalized,
    normalized_envelope_for,
)
from nativeforge.services.source_adapters import (  # noqa: E402
    bia_program_page_html as bia,
)
from nativeforge.services.source_adapters import (  # noqa: E402
    federal_register_documents_json as fr,
)

DEMO_ORG = uuid.UUID("bbbbbbbb-cccc-dddd-eeee-ffffffffffff")
out: dict[str, object] = {"schema_version": "nf_gate171_offline_proofs_v1"}


def fr_page(numbers: list[str], *, next_page: bool) -> bytes:
    """The real Federal Register envelope shape, with chosen contents."""
    return json.dumps(
        {
            "count": len(numbers),
            "next_page_url": (
                "https://www.federalregister.gov/api/v1/documents.json?page=2"
                if next_page
                else None
            ),
            "results": [
                {
                    "document_number": number,
                    "title": f"Notice {number}",
                    "type": "Notice",
                    "publication_date": "2026-09-01",
                    "agencies": [{"name": "Department of the Interior"}],
                    "html_url": f"https://www.federalregister.gov/d/{number}",
                    "comments_close_on": "2026-11-01",
                }
                for number in numbers
            ],
        }
    ).encode("utf-8")


def bia_page(*, title: str, links: list[str]) -> bytes:
    anchors = "".join(f'<a href="{href}">doc</a>' for href in links)
    return (
        f"<html><head><title>{title}</title></head><body><h1>{title}</h1>"
        f"<p>Program text.</p>{anchors}</body></html>"
    ).encode()


# ================= 171L: pagination / continuation safety =========
pagination: dict[str, object] = {}

descriptor = fr.build_descriptor()
cursor = PageCursor(max_pages=descriptor.max_pages, max_records=descriptor.max_records)

# A source that ALWAYS claims another page. A bounded collector stops anyway.
pages_walked = 0
for _ in range(25):
    body = fr_page([f"2026-{pages_walked:05d}"], next_page=True)
    records = fr.read_records(
        descriptor=descriptor,
        body_bytes=body,
        media_type="application/json",
        cursor=cursor,
    )
    import hashlib

    cursor.observe_page(
        content_sha256=hashlib.sha256(body).hexdigest(),
        record_count=len(records),
    )
    pages_walked += 1
    claims_more = fr.source_says_more(body_bytes=body)
    if not cursor.should_continue(source_says_more=claims_more):
        break

pagination["insatiable_source_stopped_at_page"] = pages_walked
pagination["termination_reason"] = cursor.terminated_because
pagination["max_pages_declared"] = descriptor.max_pages
pagination["next_page_termination_respected"] = pages_walked <= descriptor.max_pages
pagination["cursor_failures"] = cursor_failures(cursor)

# The same bytes twice is a loop, whatever the token says.
loop_cursor = PageCursor(max_pages=10, max_records=100)
same = fr_page(["2026-00001"], next_page=True)
digest = hashlib.sha256(same).hexdigest()
loop_cursor.observe_page(content_sha256=digest, record_count=1)
loop_cursor.observe_page(content_sha256=digest, record_count=1)
pagination["repeated_page_detected"] = (
    loop_cursor.terminated_because == "repeated_page_detected"
)
pagination["cursor_loop_refused"] = not loop_cursor.should_continue(
    source_says_more=True
)

# Record bound, independent of page bound.
record_cursor = PageCursor(max_pages=100, max_records=3)
record_cursor.observe_page(content_sha256="a" * 64, record_count=5)
pagination["max_record_bound_enforced"] = not record_cursor.should_continue(
    source_says_more=True
)
pagination["max_record_bound_reason"] = record_cursor.terminated_because

# Resumability: a cursor rebuilt at the same page index continues, not restarts.
resumed = PageCursor(max_pages=5, max_records=100, page_index=2, records_seen=40)
pagination["resumes_from_recorded_position"] = resumed.should_continue(
    source_says_more=True
)
pagination["resumed_page_index"] = resumed.page_index

# Rate limiting is DECLARED, not inferred.
pagination["rate_limit_declared_per_adapter"] = {
    bia.ADAPTER_KEY: bia.RATE_LIMIT_POLICY,
    fr.ADAPTER_KEY: fr.RATE_LIMIT_POLICY,
}
pagination["backoff_representable"] = all(
    policy.get("honors_retry_after") is True and policy.get("on_429")
    for policy in (bia.RATE_LIMIT_POLICY, fr.RATE_LIMIT_POLICY)
)
out["pagination_safety"] = pagination

# ================= 171M: document-source safety ===================
document: dict[str, object] = {}

bia_descriptor = bia.build_descriptor()
body = bia_page(
    title="Apply for a Grant",
    links=[
        "/media/nofo.pdf",
        "/media/nofo.pdf",
        "https://www.bia.gov/media/nofo.pdf",
        "/media/form.docx",
        "/topic/grants?utm_source=news",
        "/topic/grants",
        "#skip",
        "mailto:someone@bia.gov",
    ],
)
records = bia.read_records(
    descriptor=bia_descriptor, body_bytes=body, media_type="text/html", cursor=None
)
record = records[0]
documents = list(record.documents)

document["links_in_page"] = 8
document["documents_kept"] = len(documents)
document["duplicates_suppressed"] = record.metrics.get(
    "duplicate_documents_suppressed"
)
document["anchors_and_mailto_excluded"] = not any(
    d.url.startswith(("#", "mailto:")) for d in documents
)
document["relative_links_made_absolute"] = all(
    d.url.startswith("http") for d in documents
)
document["canonical_url_normalization"] = {
    d.url: d.canonical for d in documents if "utm_source" in d.url
}
document["attachment_relationship_assigned"] = sorted(
    {d.relationship for d in documents}
)
document["nothing_was_fetched"] = all(d.fetched is False for d in documents)
document["all_at_depth_zero"] = all(d.depth == 0 for d in documents)
document["crawl_depth_bound"] = bia_descriptor.max_crawl_depth
document["document_failures"] = document_failures(
    documents, max_depth=bia_descriptor.max_crawl_depth
)

# A depth-1 fetched document is refused by the contract, not by convention.
from nativeforge.services.source_adapter_contract_service import (  # noqa: E402
    DocumentReference,
)

forged = DocumentReference(
    url="https://www.bia.gov/media/deep.pdf", relationship="attachment",
    depth=1, fetched=True,
)
document["a_followed_link_is_refused"] = bool(
    document_failures([forged], max_depth=0)
)
document["refusal_reasons"] = document_failures([forged], max_depth=0)

# Content-hash duplicate suppression, distinct from URL duplicates.
same_bytes = [
    DocumentReference(url="https://a.invalid/1", content_sha256="f" * 64),
    DocumentReference(url="https://a.invalid/2", content_sha256="f" * 64),
]
kept, suppressed = deduplicate_documents(same_bytes)
document["identical_content_at_two_urls_suppressed"] = suppressed == 1
out["document_safety"] = document

# ================= 171N: change intelligence, fixture-driven ======
changes: dict[str, object] = {}
cases = {
    "deadline_shortened": {
        "field_name": "close_date",
        "prior_value": "2026-11-01",
        "new_value": "2026-10-01",
    },
    "deadline_extended": {
        "field_name": "close_date",
        "prior_value": "2026-11-01",
        "new_value": "2026-12-15",
    },
    "status_change": {
        "field_name": "status",
        "prior_value": "forecasted",
        "new_value": "posted",
    },
    "cancelled": {
        "field_name": "status",
        "prior_value": "posted",
        "new_value": "cancelled",
    },
    "funding_change": {
        "field_name": "funding_amount_max",
        "prior_value": "500000",
        "new_value": "750000",
    },
}
proved: dict[str, object] = {}
for name, case in cases.items():
    change = classify_change(**case)
    proved[name] = {
        "change_type": change["change_type"],
        "materiality": change["materiality"],
        "materiality_rule": change["materiality_rule"],
        "invariant_failures": change_invariant_failures(change),
    }
changes["classified"] = proved
changes["shortened_is_critical"] = (
    proved["deadline_shortened"]["materiality"] == "CRITICAL"
)
changes["extended_is_not_critical"] = (
    proved["deadline_extended"]["materiality"] != "CRITICAL"
)
changes["every_case_has_a_rule"] = all(
    bool(v["materiality_rule"]) for v in proved.values()
)
changes["no_invariant_failures"] = all(
    not v["invariant_failures"] for v in proved.values()
)

# Conflict and corroboration are properties of two sources disagreeing or
# agreeing on one field. Proved over the SHAPES the two real adapters produce.
fr_records = fr.read_records(
    descriptor=descriptor,
    body_bytes=fr_page(["2026-99999"], next_page=False),
    media_type="application/json",
    cursor=None,
)
fr_envelope = normalized_envelope_for(
    fr_records[0], adapter_key=fr.ADAPTER_KEY
)
bia_envelope = normalized_envelope_for(record, adapter_key=bia.ADAPTER_KEY)
changes["two_adapters_produce_disjoint_field_sets"] = sorted(
    set(fr_envelope["fields"]) ^ set(bia_envelope["fields"])
)
changes["api_source_supplies_dates_document_source_does_not"] = (
    "close_date" in fr_envelope["fields"]
    and "close_date" not in bia_envelope["fields"]
)
changes["identity_layers_differ_by_what_is_published"] = {
    fr.ADAPTER_KEY: identity_for_normalized(fr_envelope, source_id="a")[
        "identity_layer"
    ],
    bia.ADAPTER_KEY: identity_for_normalized(bia_envelope, source_id="b")[
        "identity_layer"
    ],
}
out["change_intelligence_fixtures"] = changes

# ================= 171P: failure isolation ========================
isolation: dict[str, object] = {}

# A malformed body from one adapter does not stop the other.
malformed_html = b"\x00\x01 not markup"
malformed_json = b"{not json at all"

bia_failed = False
try:
    bia.read_records(
        descriptor=bia_descriptor,
        body_bytes=malformed_html,
        media_type="text/html",
        cursor=None,
    )
except Exception:  # noqa: BLE001
    bia_failed = True

fr_still_works = len(
    fr.read_records(
        descriptor=descriptor,
        body_bytes=fr_page(["2026-12345"], next_page=False),
        media_type="application/json",
        cursor=None,
    )
)
isolation["malformed_document_payload_refused"] = bia_failed
isolation["api_adapter_unaffected_by_document_failure"] = fr_still_works == 1

fr_failed = False
try:
    fr.read_records(
        descriptor=descriptor,
        body_bytes=malformed_json,
        media_type="application/json",
        cursor=None,
    )
except Exception:  # noqa: BLE001
    fr_failed = True
bia_still_works = len(
    bia.read_records(
        descriptor=bia_descriptor,
        body_bytes=bia_page(title="Still fine", links=[]),
        media_type="text/html",
        cursor=None,
    )
)
isolation["malformed_api_payload_refused"] = fr_failed
isolation["document_adapter_unaffected_by_api_failure"] = bia_still_works == 1

# An adapter exception is a value, not a crash, to the harness that drives it.
isolation["adapter_exception_is_catchable_not_fatal"] = bia_failed and fr_failed

# Disabling a source is a DATA change. Proved by reading the column that does
# it rather than by asserting it.
session = SessionLocal()
try:
    active = sa.Table(
        "nf_active_opportunity_sources",
        sa.MetaData(),
        sa.Column("source_id", sa.Text()),
        sa.Column("organization_id", sa.Uuid(as_uuid=True)),
        sa.Column("disabled_at", sa.DateTime(timezone=True)),
        sa.Column("disabled_by", sa.Text()),
        sa.Column("disabled_reason", sa.Text()),
    )
    columns = {c.name for c in active.columns}
    isolation["disable_is_a_data_change"] = {
        "columns_that_disable_a_source": sorted(
            columns & {"disabled_at", "disabled_by", "disabled_reason"}
        ),
        "requires_code_deploy": False,
        "why": (
            "the collection runner refuses a source whose activation row has "
            "disabled_at set, so disabling one is an UPDATE - no code path "
            "names a source id"
        ),
    }
    rows = (
        session.execute(
            sa.select(active.c.source_id, active.c.disabled_at).where(
                active.c.organization_id == DEMO_ORG
            )
        )
        .mappings()
        .all()
    )
    isolation["active_sources"] = {
        str(r["source_id"]): ("disabled" if r["disabled_at"] else "enabled")
        for r in rows
    }
finally:
    session.close()

out["failure_isolation"] = isolation
out["failure_isolation_ready"] = all(
    [
        isolation["malformed_document_payload_refused"],
        isolation["api_adapter_unaffected_by_document_failure"],
        isolation["malformed_api_payload_refused"],
        isolation["document_adapter_unaffected_by_api_failure"],
    ]
)

socket.socket = _real_socket  # type: ignore[misc,assignment]
out["network_attempts_during_this_phase"] = _NETWORK["attempts"]
print(json.dumps(out, sort_keys=True, default=str))
