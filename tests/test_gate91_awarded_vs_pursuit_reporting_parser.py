"""Gate 91I - awarded vs pursuit lanes, and the reporting parser seams.

Two things are being protected here.

**A pursuit is a possibility; an award is an obligation.** Moving between them
changes what a customer owes, so it needs a person behind it. Gate 91A confirmed
`GrantPipelineStage.awarded` is a plain enum member assignable by anything and
the only place the word appears in the codebase - so the load-bearing test is
the one proving a backend assignment cannot produce a portfolio record.

**No obligation without evidence.** "Federal grants generally require SF-425
quarterly" is background, not a finding about a notice. Every extracted
requirement must carry a quote that is actually in the source text, and an
invariant re-checks that rather than trusting the extractor.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from nativeforge.services.award_transition_service import (
    AWARDED_PAGE_LABEL,
    CONFIRMATION_TEXT,
    MARK_AS_AWARDED_LABEL,
    UNDO_TEXT,
    AwardTransitionError,
    build_award_transition_preview,
    mark_as_awarded,
    transition_invariant_failures,
    undo_mark_as_awarded,
)
from nativeforge.services.awarded_grant_portfolio_service import (
    AwardedGrantError,
    awarded_grant_invariant_failures,
    build_awarded_grant_record,
    build_portfolio,
)
from nativeforge.services.grant_document_attachment_inventory_service import (
    DOCUMENT_TYPES,
    build_document_inventory,
    build_document_inventory_entry,
    inventory_invariant_failures,
)
from nativeforge.services.grant_document_text_extraction_service import (
    extract_grant_document_text,
)
from nativeforge.services.grant_document_text_extraction_service import (
    extraction_invariant_failures as text_extraction_failures,
)
from nativeforge.services.grant_lane_separation_service import (
    AWARDED_LANES,
    GRANT_LANES,
    PURSUIT_LANES,
    classify_grant_lane,
    lane_invariant_failures,
    separate_grant_lanes,
)
from nativeforge.services.grant_reporting_requirement_extraction_service import (
    REQUIREMENT_CATEGORIES,
    extract_reporting_requirements,
)
from nativeforge.services.grant_reporting_requirement_extraction_service import (
    extraction_invariant_failures as requirement_failures,
)
from nativeforge.services.pursuit_reporting_burden_projection_service import (
    BURDEN_STATUSES,
    DETERMINATE_BURDEN_STATUSES,
    project_pursuit_reporting_burden,
    projection_invariant_failures,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
TERMS_FIXTURE = REPO_ROOT / "tests/fixtures/grant_documents/synthetic_award_terms.txt"
PDF_FIXTURE = REPO_ROOT / "tests/fixtures/nofo_artifacts/synthetic_notice.pdf"
HTML_FIXTURE = REPO_ROOT / "tests/fixtures/nofo_artifacts/synthetic_notice.html"


@pytest.fixture(scope="module")
def extracted_text() -> dict:
    return extract_grant_document_text(
        document_id="doc-terms", local_path=str(TERMS_FIXTURE)
    )


@pytest.fixture(scope="module")
def requirements(extracted_text: dict) -> dict:
    return extract_reporting_requirements(
        document_id="doc-terms",
        text=extracted_text["text"],
        owner_id="opp-1",
        is_post_award_document=True,
    )


def _award_details() -> dict:
    return {
        "award_number": "SYN-1",
        "award_start_date": "2026-10-01",
        "award_end_date": "2027-09-30",
        "award_amount": 250000,
    }


def _transition(**overrides) -> dict:
    kwargs = {
        "transition_id": "t1",
        "source_opportunity_id": "opp-1",
        "customer_org_id": "org-1",
        "from_lane": "submitted",
        "prior_state": {"lane": "submitted", "status": "under_review"},
        "award_details": _award_details(),
        "user_action": True,
        "actor": "user-1",
        "at": "2026-08-26T00:00:00Z",
    }
    kwargs.update(overrides)
    return mark_as_awarded(**kwargs)


# ---------------------------------------------------------------------------
# Lane separation
# ---------------------------------------------------------------------------


def test_awarded_and_pursuit_are_disjoint_lane_sets() -> None:
    assert AWARDED_LANES & PURSUIT_LANES == set()
    assert AWARDED_LANES <= GRANT_LANES
    assert PURSUIT_LANES <= GRANT_LANES


@pytest.mark.parametrize("lane", sorted(AWARDED_LANES))
def test_awarded_lanes_require_reporting_tracking(lane: str) -> None:
    result = classify_grant_lane(
        grant_record_id="g", lane=lane, customer_org_id="org-1"
    )
    assert result["is_awarded"] is True
    assert result["is_pursuit"] is False
    assert result["requires_reporting_tracking"] is True
    assert result["requires_application_tracking"] is False
    assert lane_invariant_failures(result) == []


@pytest.mark.parametrize("lane", sorted(PURSUIT_LANES))
def test_pursuit_lanes_do_not_carry_reporting_tracking(lane: str) -> None:
    result = classify_grant_lane(
        grant_record_id="g", lane=lane, customer_org_id="org-1"
    )
    assert result["is_pursuit"] is True
    assert result["is_awarded"] is False
    assert result["requires_reporting_tracking"] is False
    assert result["requires_application_tracking"] is True


@pytest.mark.parametrize("lane", [None, "", "something_new", "AWARDED"])
def test_unknown_lane_defaults_to_neither(lane) -> None:
    """Defaulting either way is wrong: one hides an award, the other invents one."""
    result = classify_grant_lane(
        grant_record_id="g", lane=lane, customer_org_id="org-1"
    )
    assert result["lane"] == "unknown"
    assert result["is_pursuit"] is False
    assert result["is_awarded"] is False
    assert result["requires_reporting_tracking"] is False
    assert result["human_review_required"] is True
    assert lane_invariant_failures(result) == []


@pytest.mark.parametrize("lane", ["not_pursued", "archived"])
def test_inactive_lanes_are_neither_pursuit_nor_awarded(lane: str) -> None:
    result = classify_grant_lane(
        grant_record_id="g", lane=lane, customer_org_id="org-1"
    )
    assert result["is_pursuit"] is False
    assert result["is_awarded"] is False


def test_separation_covers_every_record_and_hides_none() -> None:
    result = separate_grant_lanes(
        records=[
            {"grant_record_id": "g1", "lane": "submitted", "customer_org_id": "o"},
            {"grant_record_id": "g2", "lane": "awarded_active", "customer_org_id": "o"},
            {"grant_record_id": "g3", "lane": "archived", "customer_org_id": "o"},
            {"grant_record_id": "g4", "lane": None, "customer_org_id": "o"},
        ]
    )
    assert result["total_records"] == 4
    assert (
        result["pursuit_count"]
        + result["awarded_count"]
        + result["inactive_count"]
        + result["unresolved_count"]
    ) == 4
    assert result["records_removed"] == 0
    assert result["records_hidden"] == 0
    assert lane_invariant_failures(result) == []


def test_a_pipeline_stage_is_not_a_lane() -> None:
    """GrantPipelineStage.awarded exists and must not be read as a lane."""
    from nativeforge.domain.enums import GrantPipelineStage

    assert GrantPipelineStage.awarded.value == "awarded"
    # "awarded" alone is not a member of the lane vocabulary.
    assert "awarded" not in GRANT_LANES
    result = classify_grant_lane(
        grant_record_id="g", lane="awarded", customer_org_id="org-1"
    )
    assert result["lane"] == "unknown"
    assert result["is_awarded"] is False
    assert result["pipeline_stage_is_not_a_lane"] is True


# ---------------------------------------------------------------------------
# Awarded portfolio
# ---------------------------------------------------------------------------


def test_awarded_grant_requires_a_customer_org() -> None:
    with pytest.raises(AwardedGrantError, match="customer_org_id"):
        build_awarded_grant_record(awarded_grant_id="a1", customer_org_id="")


def test_awarded_grant_is_customer_specific_not_a_registry_row() -> None:
    record = build_awarded_grant_record(
        awarded_grant_id="a1", customer_org_id="org-1", **_award_details()
    )
    assert record["is_customer_specific"] is True
    assert record["is_source_registry_row"] is False
    assert record["is_generic_opportunity"] is False
    assert record["is_active_obligation"] is True
    assert awarded_grant_invariant_failures(record) == []


def test_missing_award_details_create_human_review(requirements: dict) -> None:
    record = build_awarded_grant_record(
        awarded_grant_id="a1", customer_org_id="org-1"
    )
    assert record["requires_human_review"] is True
    assert any(
        i.startswith("missing_award_detail:") for i in record["human_review_items"]
    )
    assert record["risk_summary"]["administrable_from_this_record"] is False


def test_requirement_without_evidence_is_flagged_not_dropped() -> None:
    record = build_awarded_grant_record(
        awarded_grant_id="a1",
        customer_org_id="org-1",
        reporting_requirements=[{"report_name": "mystery report"}],
        **_award_details(),
    )
    assert len(record["reporting_requirements"]) == 1
    item = record["reporting_requirements"][0]
    assert item["human_review_required"] is True
    assert "requirement_without_evidence_quote" in item["blocked_reasons"]
    assert awarded_grant_invariant_failures(record) == []


def test_calendar_never_infers_a_date() -> None:
    record = build_awarded_grant_record(
        awarded_grant_id="a1",
        customer_org_id="org-1",
        reporting_requirements=[
            {"report_name": "quarterly", "report_frequency": "quarterly",
             "evidence_quote": "must submit quarterly"},
        ],
        **_award_details(),
    )
    calendar = record["reporting_calendar"]
    assert calendar["dates_inferred"] == 0
    # A frequency with no stated date does not become four deadlines.
    assert calendar["dated_count"] == 0
    assert calendar["undated_count"] == 1
    assert calendar["undated_obligations"][0]["reason"] == "no_due_date_in_source"


def test_portfolio_never_claims_live_lifecycle_tracking() -> None:
    record = build_awarded_grant_record(
        awarded_grant_id="a1", customer_org_id="org-1", **_award_details()
    )
    portfolio = build_portfolio(awarded_grants=[record])
    assert portfolio["lifecycle_tracking_live"] is False
    assert awarded_grant_invariant_failures(portfolio) == []


# ---------------------------------------------------------------------------
# Projected burden
# ---------------------------------------------------------------------------


def test_projected_burden_is_never_an_active_obligation(requirements: dict) -> None:
    projection = project_pursuit_reporting_burden(
        opportunity_id="opp-1",
        **{f"{k.replace('_requirements', '')}_requirements": requirements[k]
           for k in REQUIREMENT_CATEGORIES},
        extraction_complete=True,
    )
    assert projection["is_projection"] is True
    assert projection["is_active_obligation"] is False
    assert projection["requires_award_before_obligations_begin"] is True
    assert projection_invariant_failures(projection) == []


def test_every_projected_field_is_named_projected(requirements: dict) -> None:
    projection = project_pursuit_reporting_burden(
        opportunity_id="opp-1",
        reporting_requirements=requirements["reporting_requirements"],
        extraction_complete=True,
    )
    for key in projection:
        if key.endswith("_requirements"):
            assert key.startswith("projected_"), key


def test_burden_never_affects_eligibility(requirements: dict) -> None:
    projection = project_pursuit_reporting_burden(
        opportunity_id="opp-1",
        reporting_requirements=requirements["reporting_requirements"],
        extraction_complete=True,
    )
    assert projection["affects_eligibility"] is False
    assert projection["is_legal_advice"] is False


def test_incomplete_extraction_cannot_yield_a_determinate_burden(
    requirements: dict,
) -> None:
    """Absence of evidence is not evidence of low burden."""
    projection = project_pursuit_reporting_burden(
        opportunity_id="opp-1",
        reporting_requirements=requirements["reporting_requirements"],
        extraction_complete=False,
    )
    assert projection["burden_fit"] == "unclear"
    assert projection["burden_fit"] not in DETERMINATE_BURDEN_STATUSES
    assert projection["human_review_required"] is True
    assert "source_extraction_incomplete" in projection["blocked_reasons"]


def test_no_requirements_found_is_unclear_not_manageable() -> None:
    projection = project_pursuit_reporting_burden(
        opportunity_id="opp-1", extraction_complete=True
    )
    assert projection["burden_fit"] == "unclear"
    assert projection["system_need"] == "unclear"
    assert "no_evidenced_requirements_found" in projection["blocked_reasons"]


def test_burden_statuses_are_closed(requirements: dict) -> None:
    projection = project_pursuit_reporting_burden(
        opportunity_id="opp-1",
        reporting_requirements=requirements["reporting_requirements"],
        extraction_complete=True,
    )
    assert projection["burden_fit"] in BURDEN_STATUSES


# ---------------------------------------------------------------------------
# Mark as Awarded - the load-bearing tests
# ---------------------------------------------------------------------------


def test_mark_as_awarded_requires_explicit_user_action() -> None:
    """The rule this whole gate exists to make enforceable."""
    with pytest.raises(AwardTransitionError, match="explicit user action"):
        mark_as_awarded(
            transition_id="t1",
            source_opportunity_id="opp-1",
            customer_org_id="org-1",
            from_lane="submitted",
            user_action=False,
        )


def test_backend_enum_assignment_alone_is_not_a_valid_transition() -> None:
    """Setting GrantPipelineStage.awarded produces no portfolio record.

    The enum can still be assigned - other code may depend on it - but it does
    not route through this service, so it creates nothing and records nobody.
    """
    from nativeforge.domain.enums import GrantPipelineStage

    stage = GrantPipelineStage.awarded
    assert stage.value == "awarded"

    # No portfolio record exists as a result of that assignment. The only route
    # is mark_as_awarded, and it refuses without a user action.
    with pytest.raises(AwardTransitionError):
        mark_as_awarded(
            transition_id="t1",
            source_opportunity_id="opp-1",
            customer_org_id="org-1",
            from_lane=stage.value,
            user_action=False,
        )
    # And even with a user action, the raw stage value is not a lane.
    with pytest.raises(AwardTransitionError, match="unrecognised from_lane"):
        mark_as_awarded(
            transition_id="t1",
            source_opportunity_id="opp-1",
            customer_org_id="org-1",
            from_lane=stage.value,
            user_action=True,
        )


def test_mark_as_awarded_requires_a_customer_org() -> None:
    with pytest.raises(AwardTransitionError, match="customer_org_id"):
        mark_as_awarded(
            transition_id="t1",
            source_opportunity_id="opp-1",
            customer_org_id=None,
            from_lane="submitted",
            user_action=True,
        )


def test_mark_as_awarded_moves_the_record_and_creates_a_portfolio_entry() -> None:
    result = _transition()
    assert result["from_lane"] == "submitted"
    assert result["to_lane"] == "awarded_active"
    assert result["to_lane"] in AWARDED_LANES
    assert result["created_awarded_grant_id"]
    assert result["awarded_grant_record"]["customer_org_id"] == "org-1"
    assert transition_invariant_failures(result) == []


def test_the_record_is_no_longer_an_active_pursuit() -> None:
    result = _transition()
    lane = classify_grant_lane(
        grant_record_id="g1", lane=result["to_lane"], customer_org_id="org-1"
    )
    assert lane["is_pursuit"] is False
    assert lane["is_awarded"] is True
    assert lane["requires_application_tracking"] is False


def test_transition_emits_an_audit_event() -> None:
    result = _transition()
    event = result["audit_event"]
    assert event["action"] == "mark_as_awarded"
    assert event["customer_org_id"] == "org-1"
    assert event["actor"] == "user-1"
    assert event["detail"]["user_action"] is True
    assert event["immutable"] is True


def test_missing_award_details_create_human_review_not_failure() -> None:
    result = _transition(award_details={})
    assert result["transition_status"] == "completed_with_human_review"
    assert result["requires_human_review"] is True
    assert result["missing_award_fields"]
    # And obligations are not dated without them.
    assert result["obligations_dated"] is False
    assert transition_invariant_failures(result) == []


@pytest.mark.parametrize("lane", ["archived", "not_pursued"])
def test_inactive_lanes_require_review_to_become_awarded(lane: str) -> None:
    result = _transition(from_lane=lane, prior_state={"lane": lane})
    assert result["requires_human_review"] is True
    assert any(
        r.startswith("transition_from_inactive_lane")
        for r in result["human_review_reasons"]
    )


def test_cannot_transition_from_an_already_awarded_lane() -> None:
    with pytest.raises(AwardTransitionError, match="already in an awarded lane"):
        mark_as_awarded(
            transition_id="t1",
            source_opportunity_id="opp-1",
            customer_org_id="org-1",
            from_lane="awarded_active",
            user_action=True,
        )


def test_preview_changes_nothing() -> None:
    preview = build_award_transition_preview(
        source_opportunity_id="opp-1",
        customer_org_id="org-1",
        from_lane="submitted",
        award_details=_award_details(),
    )
    assert preview["transition_performed"] is False
    assert preview.get("created_awarded_grant_id") is None
    assert preview["destination_label"] == AWARDED_PAGE_LABEL == "Awarded Grants"
    assert preview["action_label"] == MARK_AS_AWARDED_LABEL == "Mark as Awarded"
    assert preview["confirmation_text"] == CONFIRMATION_TEXT
    assert "reporting obligation tracking" in preview["what_begins"]
    assert transition_invariant_failures(preview) == []


def test_customer_copy_says_what_begins() -> None:
    assert "Awarded Grants workspace" in CONFIRMATION_TEXT
    assert "undo this if it was a mistake" in CONFIRMATION_TEXT
    assert UNDO_TEXT == "Moved to Awarded Grants. Undo?"
    assert AWARDED_PAGE_LABEL == "Awarded Grants"


# ---------------------------------------------------------------------------
# Undo
# ---------------------------------------------------------------------------


def test_undo_restores_the_prior_lane() -> None:
    result = _transition()
    undone = undo_mark_as_awarded(transition=result, actor="user-1")
    assert undone["undo_status"] == "undone"
    assert undone["restored_lane"] == "submitted"
    assert undone["restored_state"]["status"] == "under_review"
    assert undone["undo_available"] is False
    assert transition_invariant_failures(undone) == []


def test_undo_is_idempotent() -> None:
    result = _transition()
    once = undo_mark_as_awarded(transition=result)
    twice = undo_mark_as_awarded(transition=once)
    thrice = undo_mark_as_awarded(transition=twice)
    assert once["undo_status"] == "undone"
    assert twice["undo_status"] == "already_undone"
    assert thrice["undo_status"] == "already_undone"
    assert twice["restored_lane"] == once["restored_lane"]


def test_undo_deletes_no_evidence(requirements: dict) -> None:
    """A reversal removes standing, never evidence."""
    result = _transition(
        documents=[{"document_id": "doc-terms", "filename": "terms.txt"}],
        extracted_requirements={k: requirements[k] for k in REQUIREMENT_CATEGORIES},
    )
    undone = undo_mark_as_awarded(transition=result)

    assert undone["documents_deleted"] == 0
    assert undone["requirements_deleted"] == 0
    assert undone["award_details_deleted"] == 0
    assert undone["audit_events_deleted"] == 0

    preserved = undone["preserved_on_undo"]
    assert len(preserved["documents"]) == 1
    assert preserved["award_details"]["award_number"] == "SYN-1"
    assert preserved["extracted_requirements"]["reporting_requirements"]
    assert len(preserved["audit_events"]) >= 2
    assert undone["awarded_grant_record_status"] == "superseded"


def test_undo_without_a_snapshot_is_blocked_not_guessed() -> None:
    fabricated = {
        "schema_version": "nf_award_transition_v1",
        "transition_id": "t9",
        "customer_org_id": "org-1",
        "to_lane": "awarded_active",
        "prior_state_snapshot": {},
        "transition_status": "completed",
    }
    undone = undo_mark_as_awarded(transition=fabricated)
    assert undone["restored_lane"] is None
    assert "no_prior_lane_in_snapshot" in undone["blocked_reasons"]


# ---------------------------------------------------------------------------
# Document inventory
# ---------------------------------------------------------------------------


def test_inventory_preserves_owner_and_hash() -> None:
    entry = build_document_inventory_entry(
        document_id="doc-1",
        owner_type="opportunity",
        owner_id="opp-1",
        document_type="terms_and_conditions",
        local_path=str(TERMS_FIXTURE),
        terms_status="NO_REVIEW_REQUIRED",
    )
    assert entry["owner_type"] == "opportunity"
    assert entry["owner_id"] == "opp-1"
    assert entry["hash_sha256"]
    assert len(entry["hash_sha256"]) == 64
    assert entry["size_bytes"] > 0
    assert entry["retrieval_method"] == "local_fixture"
    assert inventory_invariant_failures(entry) == []


def test_inventory_does_not_imply_parsing_or_clearance() -> None:
    entry = build_document_inventory_entry(
        document_id="doc-1",
        owner_type="opportunity",
        owner_id="opp-1",
        document_type="NOFO",
        local_path=str(TERMS_FIXTURE),
        terms_status="TERMS_REVIEW_REQUIRED",
    )
    assert entry["parse_status"] == "not_attempted"
    assert entry["text_extraction_status"] == "not_attempted"
    assert "terms_status:TERMS_REVIEW_REQUIRED" in entry["blocked_reasons"]


def test_inventory_downloads_nothing() -> None:
    entry = build_document_inventory_entry(
        document_id="doc-remote",
        owner_type="opportunity",
        owner_id="opp-1",
        document_type="reporting_guidance",
        source_url="https://example.gov/guidance.pdf",
    )
    assert entry["downloaded"] is False
    assert entry["retrieval_method"] == "not_retrieved"
    assert entry["hash_sha256"] is None
    assert "not_retrieved_no_download_in_this_gate" in entry["blocked_reasons"]

    inventory = build_document_inventory(
        documents=[
            {
                "document_id": "d",
                "owner_type": "opportunity",
                "owner_id": "o",
                "source_url": "https://example.gov/x.pdf",
            }
        ]
    )
    assert inventory["downloads_performed"] == 0
    assert inventory["network_access_performed"] is False
    assert inventory_invariant_failures(inventory) == []


def test_post_award_and_application_documents_are_distinguished() -> None:
    terms = build_document_inventory_entry(
        document_id="d1", owner_type="opportunity", owner_id="o",
        document_type="terms_and_conditions",
    )
    app = build_document_inventory_entry(
        document_id="d2", owner_type="opportunity", owner_id="o",
        document_type="application_instructions",
    )
    assert terms["is_post_award_document"] is True
    assert terms["is_application_document"] is False
    assert app["is_post_award_document"] is False
    assert app["is_application_document"] is True
    assert terms["evidence_role"] == "post_award_terms"
    assert app["evidence_role"] == "application_instruction"


def test_document_types_are_closed() -> None:
    entry = build_document_inventory_entry(
        document_id="d", owner_type="opportunity", owner_id="o",
        document_type="not_a_real_type",
    )
    assert entry["document_type"] == "unknown"
    assert "unrecognised_document_type:not_a_real_type" in entry["blocked_reasons"]
    assert entry["document_type"] in DOCUMENT_TYPES


# ---------------------------------------------------------------------------
# Text extraction
# ---------------------------------------------------------------------------


def test_text_extraction_is_deterministic(extracted_text: dict) -> None:
    again = extract_grant_document_text(
        document_id="doc-terms", local_path=str(TERMS_FIXTURE)
    )
    assert json.dumps(extracted_text, sort_keys=True) == json.dumps(
        again, sort_keys=True
    )
    assert extracted_text["extraction_status"] == "extracted"
    assert extracted_text["text_hash_sha256"] == again["text_hash_sha256"]
    assert text_extraction_failures(extracted_text) == []


def test_html_extraction_reuses_the_gate82_adapter() -> None:
    result = extract_grant_document_text(
        document_id="doc-html", local_path=str(HTML_FIXTURE)
    )
    assert result["extraction_status"] == "extracted"
    assert result["text"]
    assert text_extraction_failures(result) == []


def test_unsupported_pdf_returns_parser_unavailable_not_empty_text() -> None:
    """A silent fallback would read a document with obligations as one with none."""
    result = extract_grant_document_text(
        document_id="doc-pdf", local_path=str(PDF_FIXTURE)
    )
    assert result["extraction_status"] == "parser_unavailable"
    assert result["text"] is None
    assert any("manual_review" in r for r in result["blocked_reasons"])
    assert text_extraction_failures(result) == []


BANNED_IMPORT_PREFIXES = (
    "requests", "httpx", "urllib", "socket", "http",
    "openai", "anthropic", "transformers", "torch", "sentence_transformers",
)


def _imported_module_names(path: Path) -> set[str]:
    """Modules a file actually imports.

    Parsed with `ast` rather than grepped, because a docstring explaining "no
    embedding, no model call" would trip a substring search — and the guard is
    supposed to check the code, not the prose describing it. Rewording accurate
    documentation to satisfy a naive matcher would make the module worse.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module.split(".")[0])
    return names


def test_extraction_uses_no_ai_and_no_network(extracted_text: dict) -> None:
    assert extracted_text["ai_used"] is False
    assert extracted_text["ocr_used"] is False
    assert extracted_text["network_access_performed"] is False
    assert extracted_text["deterministic"] is True

    imported = _imported_module_names(
        REPO_ROOT
        / "src/nativeforge/services/grant_document_text_extraction_service.py"
    )
    for banned in BANNED_IMPORT_PREFIXES:
        assert banned not in imported, f"{banned} imported"


def test_missing_document_is_blocked_not_fetched() -> None:
    result = extract_grant_document_text(document_id="doc-x", local_path=None)
    assert result["extraction_status"] == "blocked"
    assert "no_local_path_and_no_download_in_this_gate" in result["blocked_reasons"]


def test_extraction_spans_stay_inside_the_text(extracted_text: dict) -> None:
    length = len(extracted_text["text"])
    assert extracted_text["evidence_spans"]
    for span in extracted_text["evidence_spans"]:
        assert 0 <= span["start"] <= span["end"] <= length


# ---------------------------------------------------------------------------
# Requirement extraction
# ---------------------------------------------------------------------------


def test_requirements_are_extracted_with_evidence(
    requirements: dict, extracted_text: dict
) -> None:
    assert requirements["requirement_count"] > 0
    assert requirement_failures(requirements, source_text=extracted_text["text"]) == []
    for category in REQUIREMENT_CATEGORIES:
        for item in requirements[category]:
            assert item["evidence_quote"]
            assert item["evidence_quote"] in extracted_text["text"]
            assert item["source_document_id"] == "doc-terms"


def test_every_requirement_carries_a_span(requirements: dict) -> None:
    for category in REQUIREMENT_CATEGORIES:
        for item in requirements[category]:
            location = item["evidence_location"]
            assert location["start"] is not None
            assert location["end"] > location["start"]


def test_extraction_never_produces_a_due_date(requirements: dict) -> None:
    """A frequency is not a deadline."""
    assert requirements["dates_inferred"] == 0
    for category in REQUIREMENT_CATEGORIES:
        for item in requirements[category]:
            assert item["due_date"] is None
            assert item["first_due_date"] is None
    frequencies = [
        i["report_frequency"]
        for c in REQUIREMENT_CATEGORIES
        for i in requirements[c]
        if i["report_frequency"]
    ]
    assert frequencies, "the fixture states frequencies; they should be captured"


def test_application_requirements_are_separated_from_post_award(
    requirements: dict,
) -> None:
    assert requirements["application_requirement_count"] >= 1
    for item in requirements["application_requirements"]:
        assert item["timing"] == "application"
    # And none of them leaked into a burden category.
    for category in REQUIREMENT_CATEGORIES:
        for item in requirements[category]:
            assert item["timing"] != "application"


def test_subrecipient_duties_are_distinguished(requirements: dict) -> None:
    holders = {
        item["duty_holder"]
        for category in REQUIREMENT_CATEGORIES
        for item in requirements[category]
    }
    assert "subrecipient" in holders, "the fixture binds a subrecipient duty"
    assert "recipient" in holders


def test_optional_guidance_is_not_treated_as_required(requirements: dict) -> None:
    """'Grantees are encouraged to' is guidance, not an obligation."""
    forces = {
        item["requirement_force"]
        for category in REQUIREMENT_CATEGORIES
        for item in requirements[category]
    }
    non_required = [
        item
        for category in REQUIREMENT_CATEGORIES
        for item in requirements[category]
        if item["requirement_force"] != "required"
    ]
    for item in non_required:
        assert item["human_review_required"] is True
    assert forces  # at least something was classified


def test_requirement_extraction_uses_no_ai_and_no_network(
    requirements: dict,
) -> None:
    assert requirements["ai_used"] is False
    assert requirements["network_access_performed"] is False
    assert requirements["deterministic"] is True

    imported = _imported_module_names(
        REPO_ROOT
        / "src/nativeforge/services/grant_reporting_requirement_extraction_service.py"
    )
    for banned in BANNED_IMPORT_PREFIXES:
        assert banned not in imported, f"{banned} imported"


def test_extraction_is_deterministic(extracted_text: dict) -> None:
    a = extract_reporting_requirements(
        document_id="d", text=extracted_text["text"], is_post_award_document=True
    )
    b = extract_reporting_requirements(
        document_id="d", text=extracted_text["text"], is_post_award_document=True
    )
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


def test_empty_document_yields_no_requirements() -> None:
    result = extract_reporting_requirements(document_id="d", text=None)
    assert result["requirement_count"] == 0
    assert result["extraction_complete"] is False
    assert "no_document_text" in result["blocked_reasons"]


def test_a_fabricated_quote_is_rejected_by_the_invariant() -> None:
    """The invariant re-checks the quote rather than trusting the extractor."""
    doctored = {
        "schema_version": "nf_grant_reporting_requirement_extraction_v1",
        "reporting_requirements": [
            {
                "requirement_name": "invented",
                "evidence_quote": "Recipients must submit a lunar report.",
                "evidence_location": {"start": 0, "end": 10},
                "source_document_id": "d",
                "confidence": "quoted",
                "duty_holder": "recipient",
                "requirement_force": "required",
                "timing": "post_award",
                "human_review_required": False,
            }
        ],
        "financial_requirements": [],
        "performance_requirements": [],
        "compliance_requirements": [],
        "closeout_requirements": [],
        "application_requirements": [],
        "ai_used": False,
        "network_access_performed": False,
        "deterministic": True,
        "dates_inferred": 0,
        "fabricated": False,
    }
    failures = requirement_failures(doctored, source_text="a completely different text")
    assert any(f.startswith("quote_not_present_in_source") for f in failures)


# ---------------------------------------------------------------------------
# Projected and active must never be confused
# ---------------------------------------------------------------------------


def test_projected_and_active_are_structurally_distinct(requirements: dict) -> None:
    projection = project_pursuit_reporting_burden(
        opportunity_id="opp-1",
        reporting_requirements=requirements["reporting_requirements"],
        extraction_complete=True,
    )
    awarded = build_awarded_grant_record(
        awarded_grant_id="a1",
        customer_org_id="org-1",
        reporting_requirements=requirements["reporting_requirements"],
        **_award_details(),
    )

    # Different field names, different flags, no overlap.
    assert "projected_reporting_requirements" in projection
    assert "reporting_requirements" in awarded
    assert "reporting_requirements" not in projection
    assert "projected_reporting_requirements" not in awarded

    assert projection["is_active_obligation"] is False
    assert awarded["is_active_obligation"] is True

    # Only the awarded record carries a calendar.
    assert "reporting_calendar" in awarded
    assert "reporting_calendar" not in projection


def test_prior_gate_baselines_are_untouched() -> None:
    from nativeforge.services.discovery_baseline_x_service import (
        build_discovery_baseline_x,
    )

    baseline = build_discovery_baseline_x(repo_root=REPO_ROOT)
    assert baseline["corpus_summary"]["total_records"] == 185
    assert baseline["corpus_summary"]["live_records"] == 0
    assert baseline["source_coverage"]["monitored_sources"] == 0
    assert baseline["readiness_summary"]["baseline_quality_score"] == 0.0865
    assert baseline["improvement_claim_allowed"] is False
