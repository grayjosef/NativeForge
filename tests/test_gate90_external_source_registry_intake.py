"""Gate 90G - external source registry intake.

Four separations run through every test here, because collapsing any one of
them is how a seed registry turns into a claim:

    in the registry   !=  being monitored
    has an API        !=  approved to use it
    visible to a customer !=  that customer is eligible
    plausibly relevant to software  !=  an award can buy software

The heaviest test in the file is the leakage one. Every state row in this seed
is South Carolina, so a filter that defaults open shows SC broadband programs to
a customer in Oklahoma - and the SC pilot vocabulary starts spreading into
states it was never validated for.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
from pathlib import Path

import pytest

from nativeforge.services.customer_state_source_filter_service import (
    filter_invariant_failures,
    filter_sources_for_customer,
)
from nativeforge.services.external_source_registry_artifact_service import (
    CSV_NAME,
    JSON_NAME,
    STATE_SOURCES_NAME,
    SUMMARY_NAME,
    TERMS_QUEUE_NAME,
    WATCHLIST_NAME,
    RegistryArtifactError,
    artifact_claim_failures,
    build_registry_artifacts,
    load_customer_view,
    render_registry_summary,
    write_external_source_registry_artifacts,
)
from nativeforge.services.external_source_registry_import_service import (
    EXPECTED_COLUMNS,
    MONITORING_STATUS,
    REGISTRY_STATUS,
    SourceRegistryImportError,
    import_external_source_registry,
    import_invariant_failures,
    summarise_import,
)
from nativeforge.services.external_source_registry_seed_service import (
    build_registry_seed_set,
    seed_invariant_failures,
)
from nativeforge.services.nativeforge_software_allowability_source_service import (
    ALLOWABILITY_CLASSES,
    WATCHLIST_CLASSES,
    allowability_invariant_failures,
    build_software_allowability_watchlist,
    classify_software_allowability,
)
from nativeforge.services.source_registry_service import MONITORING_STATUSES

REPO_ROOT = Path(__file__).resolve().parents[1]
CSV_PATH = (
    REPO_ROOT / "fixtures/external_source_registry/nativeforge-source-registry.csv"
)


@pytest.fixture(scope="module")
def csv_text() -> str:
    return CSV_PATH.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def imported(csv_text: str) -> dict:
    return import_external_source_registry(csv_text=csv_text)


def _minimal_rows() -> list[dict[str, str]]:
    base = {c: "" for c in EXPECTED_COLUMNS}
    base.update(
        {
            "source_id": "TEST-1",
            "source_name": "Test source",
            "federal_or_state_or_private": "federal",
            "priority_tier": "Tier 1",
            "monitoring_method": "static HTML page monitor",
            "robots_or_terms_risk": "low",
            "has_api": "No",
            "has_rss_or_email": "No",
            "requires_login": "No",
        }
    )
    return [base]


def _csv_from(rows: list[dict[str, str]]) -> str:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=EXPECTED_COLUMNS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue()


# ---------------------------------------------------------------------------
# Import
# ---------------------------------------------------------------------------


def test_csv_imports_deterministically(csv_text: str) -> None:
    first = import_external_source_registry(csv_text=csv_text)
    second = import_external_source_registry(csv_text=csv_text)
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)
    assert first["imported_count"] == 55
    assert import_invariant_failures(first) == []


def test_expected_columns_are_enforced() -> None:
    rows = _minimal_rows()
    text = _csv_from(rows).replace("source_id", "id", 1)
    with pytest.raises(SourceRegistryImportError, match="columns"):
        import_external_source_registry(csv_text=text)


def test_duplicate_source_id_fails() -> None:
    rows = _minimal_rows() * 2
    with pytest.raises(SourceRegistryImportError, match="duplicate source_id"):
        import_external_source_registry(csv_text=_csv_from(rows))


@pytest.mark.parametrize("field", ["source_id", "source_name"])
def test_blank_required_field_fails(field: str) -> None:
    rows = _minimal_rows()
    rows[0][field] = ""
    with pytest.raises(SourceRegistryImportError, match="blank required field"):
        import_external_source_registry(csv_text=_csv_from(rows))


def test_unknown_priority_tier_fails() -> None:
    rows = _minimal_rows()
    rows[0]["priority_tier"] = "Tier 9"
    with pytest.raises(SourceRegistryImportError, match="priority_tier"):
        import_external_source_registry(csv_text=_csv_from(rows))


def test_unknown_values_are_preserved(imported: dict) -> None:
    """UNKNOWN is a value, not a missing one."""
    summary = summarise_import(imported)
    assert summary["unknown_cells_preserved"] == 23
    assert summary["has_api"]["UNKNOWN"] == 5
    assert summary["has_rss_or_email"]["UNKNOWN"] == 8
    unknown_recognition = [
        s for s in imported["sources"] if s["state_recognition_supported"] == "UNKNOWN"
    ]
    assert len(unknown_recognition) == 10
    for source in unknown_recognition:
        # Never coerced to a boolean or a default.
        assert source["state_recognition_supported"] == "UNKNOWN"


def test_no_url_fetch_occurs() -> None:
    source = (
        REPO_ROOT
        / "src/nativeforge/services/external_source_registry_import_service.py"
    ).read_text(encoding="utf-8")
    for banned in (
        "import requests", "import httpx", "urllib.request", "urllib.error",
        "import socket", "http.client",
    ):
        assert banned not in source, banned


def test_import_reports_zero_fetches(imported: dict) -> None:
    assert imported["urls_fetched"] == 0
    assert imported["network_access_performed"] is False
    assert imported["monitoring_started"] is False
    assert imported["live_coverage_claimed"] is False
    assert imported["source_monitoring_claimed"] is False


def test_every_row_is_not_started(imported: dict) -> None:
    for source in imported["sources"]:
        assert source["monitoring_status"] == MONITORING_STATUS == "not_started"
        assert source["registry_status"] == REGISTRY_STATUS == "seed_imported"
        assert "monitoring_not_started" in source["activation_blocked_reasons"]


def test_registry_never_asserts_eligibility_or_allowability(imported: dict) -> None:
    for source in imported["sources"]:
        assert source["eligibility_status"] == "NOT_DETERMINED_BY_REGISTRY"
        assert source["allowability_status"] == "NOT_DETERMINED_BY_REGISTRY"


# ---------------------------------------------------------------------------
# State scoping at import time
# ---------------------------------------------------------------------------


def test_state_row_without_state_is_refused() -> None:
    """A state row with no state cannot be filtered, so it must not import."""
    rows = _minimal_rows()
    rows[0]["federal_or_state_or_private"] = "state"
    rows[0]["state_if_applicable"] = ""
    with pytest.raises(SourceRegistryImportError, match="no state_if_applicable"):
        import_external_source_registry(csv_text=_csv_from(rows))


def test_federal_row_carrying_a_state_is_refused() -> None:
    """The opposite leak: silently narrowing a national source to one state."""
    rows = _minimal_rows()
    rows[0]["state_if_applicable"] = "SC"
    with pytest.raises(SourceRegistryImportError, match="must not be"):
        import_external_source_registry(csv_text=_csv_from(rows))


def test_all_state_rows_in_the_seed_carry_a_state(imported: dict) -> None:
    state_rows = [
        s for s in imported["sources"] if s["federal_or_state_or_private"] == "state"
    ]
    assert len(state_rows) == 10
    assert all(s["state_if_applicable"] == "SC" for s in state_rows)


# ---------------------------------------------------------------------------
# Seed set
# ---------------------------------------------------------------------------


def test_seed_set_activates_nothing(imported: dict) -> None:
    seed_set = build_registry_seed_set(imported=imported)
    assert seed_set["seed_count"] == 55
    assert seed_set["monitored_count"] == 0
    assert seed_set["api_approved_count"] == 0
    assert seed_set["monitoring_started"] is False
    assert seed_invariant_failures(seed_set) == []


def test_seed_bridge_can_never_reach_a_gate76_monitoring_status(
    imported: dict,
) -> None:
    """The bridge lands on Gate 76's weakest members, by construction."""
    seed_set = build_registry_seed_set(imported=imported)
    for seed in seed_set["seeds"]:
        assert seed["gate76_promotion_status"] == "discovered"
        assert seed["gate76_promotion_status"] not in MONITORING_STATUSES
        assert seed["gate76_robots_terms_status"] == "unreviewed"


def test_api_capable_is_not_api_approved(imported: dict) -> None:
    seed_set = build_registry_seed_set(imported=imported)
    capable = [s for s in seed_set["seeds"] if s["api_capable"]]
    assert len(capable) == 5
    for seed in capable:
        assert seed["api_approved"] is False
    assert seed_set["api_approved_count"] == 0


def test_login_required_rows_are_not_activated(imported: dict) -> None:
    seed_set = build_registry_seed_set(imported=imported)
    login_rows = [
        s
        for s in seed_set["seeds"]
        if s["requires_login"] in {"Yes", "Varies", "API key"}
    ]
    assert login_rows
    for seed in login_rows:
        assert seed["monitoring_status"] == "not_started"
        assert seed["legal_terms_review_required"] is True
        assert any(
            r.startswith("requires_login:") for r in seed["activation_blocked_reasons"]
        )


def test_human_review_only_sources_are_flagged(imported: dict) -> None:
    seed_set = build_registry_seed_set(imported=imported)
    human_only = [s for s in seed_set["seeds"] if s["human_review_only"]]
    ids = {s["source_id"] for s in human_only}
    # SCORF is authenticated; the two philanthropy rows are manual intake.
    assert "SC-SCORF" in ids
    for seed in human_only:
        assert seed["legal_terms_review_required"] is True
        assert "human_review_only" in seed["activation_blocked_reasons"]


# ---------------------------------------------------------------------------
# Customer state filtering - the leakage tests
# ---------------------------------------------------------------------------


def test_sc_sources_visible_to_sc_customer(imported: dict) -> None:
    view = load_customer_view(imported=imported, operating_states=["SC"])
    visible_ids = {s["source_id"] for s in view["visible_sources"]}
    assert "SC-BEAD" in visible_ids
    assert "SC-DHHS" in visible_ids
    assert view["visible_count"] == 55
    assert view["blocked_count"] == 0
    assert filter_invariant_failures(view) == []


def test_no_sc_source_leaks_to_a_non_sc_customer(imported: dict) -> None:
    """The test this module exists for."""
    for state in ("OK", "NM", "WA", "CA", "NY"):
        view = load_customer_view(imported=imported, operating_states=[state])
        leaked = [
            s["source_id"]
            for s in view["visible_sources"]
            if s.get("state_if_applicable")
        ]
        assert leaked == [], f"{state} customer saw state sources: {leaked}"
        assert view["blocked_count"] == 10
        assert filter_invariant_failures(view) == []


def test_federal_rows_visible_regardless_of_customer_state(imported: dict) -> None:
    for states in (["SC"], ["OK"], ["OK", "NM"], None):
        view = load_customer_view(imported=imported, operating_states=states)
        federal = [
            s
            for s in view["visible_sources"]
            if s["state_scope_status"] == "federal_all_customers"
        ]
        assert len(federal) == 43, states


@pytest.mark.parametrize("states", [None, [], ""])
def test_missing_customer_state_blocks_state_sources(imported: dict, states) -> None:
    view = load_customer_view(imported=imported, operating_states=states)
    assert view["customer_has_declared_operating_state"] is False
    assert view["blocked_count"] == 10
    for sid, reason in view["blocked_reasons"].items():
        assert reason == "customer_has_no_declared_operating_state", sid
    leaked = [
        s["source_id"] for s in view["visible_sources"] if s.get("state_if_applicable")
    ]
    assert leaked == []


def test_multi_state_customer_sees_only_their_states(imported: dict) -> None:
    view = load_customer_view(imported=imported, operating_states=["SC", "NC"])
    assert view["visible_count"] == 55
    view_nc_only = load_customer_view(imported=imported, operating_states=["NC"])
    assert view_nc_only["blocked_count"] == 10


def test_filter_uses_no_mailing_address(imported: dict) -> None:
    view = load_customer_view(imported=imported, operating_states=["SC"])
    assert view["mailing_address_used"] is False
    assert view["default_all_state_expansion"] is False
    source = (
        REPO_ROOT
        / "src/nativeforge/services/customer_state_source_filter_service.py"
    ).read_text(encoding="utf-8")
    assert "mailing" not in source.lower().replace("mailing_address_used", "").replace(
        "mailing address", ""
    )


def test_visibility_is_not_eligibility(imported: dict) -> None:
    view = load_customer_view(imported=imported, operating_states=["SC"])
    assert view["visibility_is_not_eligibility"] is True
    for seed in view["visible_sources"]:
        assert seed["eligibility_status"] == "NOT_DETERMINED_BY_REGISTRY"


def test_every_blocked_source_states_a_reason(imported: dict) -> None:
    view = load_customer_view(imported=imported, operating_states=["OK"])
    assert view["blocked_sources"]
    for seed in view["blocked_sources"]:
        assert view["blocked_reasons"].get(seed["source_id"])


def test_unrecognised_scope_is_blocked_not_guessed() -> None:
    seed = {
        "source_id": "ODD-1",
        "state_scope_status": "something_new",
        "state_if_applicable": "",
        "eligibility_status": "NOT_DETERMINED_BY_REGISTRY",
    }
    view = filter_sources_for_customer(seeds=[seed], operating_states=["SC"])
    assert view["visible_count"] == 0
    assert view["blocked_reasons"]["ODD-1"] == "unrecognised_state_scope"


# ---------------------------------------------------------------------------
# Terms review
# ---------------------------------------------------------------------------


def test_terms_review_queue_holds_every_non_clear_source(imported: dict) -> None:
    bundle = build_registry_artifacts(imported=imported)
    queue_ids = {s["source_id"] for s in bundle["terms_rows"]}
    assert len(queue_ids) == 13
    for expected in (
        "FED-SAM-AL", "NAT-ATC", "DOI-BIE", "HHS-HRSA",
        "NSF-FUNDING", "NASA-NSPIRES", "SC-SCORF", "PRIV-NDN", "PRIV-FNT",
    ):
        assert expected in queue_ids, expected
    for source in bundle["terms_rows"]:
        assert source["terms_status"] != "NO_REVIEW_REQUIRED"


def test_api_terms_rows_are_attribution_not_clearance(imported: dict) -> None:
    attribution = [
        s for s in imported["sources"] if s["terms_status"] == "ATTRIBUTION_REQUIRED"
    ]
    assert {s["source_id"] for s in attribution} >= {"FED-GRANTS", "FED-USA"}
    for source in attribution:
        assert source["robots_or_terms_risk"] == "API_TERMS"
        assert source["monitoring_status"] == "not_started"


# ---------------------------------------------------------------------------
# Software allowability
# ---------------------------------------------------------------------------


def test_allowability_preserves_unclear_and_unknown(imported: dict) -> None:
    watchlist = build_software_allowability_watchlist(sources=imported["sources"])
    by_class = watchlist["by_allowability_class"]
    assert by_class["unclear"] == 6
    assert by_class["clearly_allowable"] == 0
    assert by_class["likely_allowable"] == 3
    assert by_class["sometimes_allowable"] == 44
    assert allowability_invariant_failures(watchlist) == []


def test_watchlist_excludes_sometimes_allowable(imported: dict) -> None:
    """44 of 55 read 'sometimes'; a watchlist including them is not a watchlist."""
    watchlist = build_software_allowability_watchlist(sources=imported["sources"])
    assert watchlist["watchlist_count"] == 3
    assert {w["source_id"] for w in watchlist["watchlist"]} == {
        "EPA-GAP", "EPA-EN", "CISA-SLCGP"
    }
    for entry in watchlist["classifications"]:
        if entry["allowability_class"] == "sometimes_allowable":
            assert entry["on_watchlist"] is False


def test_allowability_never_claims_a_purchase_is_permitted(imported: dict) -> None:
    watchlist = build_software_allowability_watchlist(sources=imported["sources"])
    assert watchlist["customer_may_purchase_software"] is False
    assert watchlist["is_legal_advice"] is False
    for entry in watchlist["classifications"]:
        assert entry["customer_may_purchase_software"] is False
        assert entry["requires_live_nofo_and_approved_budget"] is True
        assert "requires_live_nofo_and_approved_budget" in entry["blocked_reasons"]


def test_unknown_allowability_value_is_preserved() -> None:
    result = classify_software_allowability(
        source={"source_id": "X", "software_cost_allowability": "UNKNOWN"}
    )
    assert result["allowability_class"] == "unknown"
    assert result["raw_allowability_value"] == "UNKNOWN"
    assert result["on_watchlist"] is False


def test_varies_is_unclear_not_sometimes() -> None:
    """'Varies' is a refusal to commit and must not be promoted."""
    result = classify_software_allowability(
        source={"source_id": "X", "software_cost_allowability": "Varies"}
    )
    assert result["allowability_class"] == "unclear"
    assert result["on_watchlist"] is False


def test_award_databases_are_unlikely_allowable(imported: dict) -> None:
    watchlist = build_software_allowability_watchlist(sources=imported["sources"])
    by_id = {c["source_id"]: c for c in watchlist["classifications"]}
    for sid in ("FED-USA", "NIH-REPORTER"):
        assert by_id[sid]["allowability_class"] == "unlikely_allowable"
        assert by_id[sid]["on_watchlist"] is False


def test_allowability_classes_are_closed(imported: dict) -> None:
    watchlist = build_software_allowability_watchlist(sources=imported["sources"])
    for entry in watchlist["classifications"]:
        assert entry["allowability_class"] in ALLOWABILITY_CLASSES
        if entry["on_watchlist"]:
            assert entry["allowability_class"] in WATCHLIST_CLASSES


# ---------------------------------------------------------------------------
# Artifacts
# ---------------------------------------------------------------------------


def test_artifacts_write_and_are_deterministic(tmp_path: Path, imported: dict) -> None:
    first = write_external_source_registry_artifacts(
        imported=imported, repo_root=tmp_path / "a"
    )
    write_external_source_registry_artifacts(
        imported=imported, repo_root=tmp_path / "b"
    )
    assert first["claim_failures"] == []
    for name in (JSON_NAME, CSV_NAME, SUMMARY_NAME, TERMS_QUEUE_NAME,
                 STATE_SOURCES_NAME, WATCHLIST_NAME):
        a = (tmp_path / "a" / "artifacts/source_registry_external" / name).read_bytes()
        b = (tmp_path / "b" / "artifacts/source_registry_external" / name).read_bytes()
        assert a == b, name
        assert a.strip()


def test_committed_artifact_matches_a_fresh_import(imported: dict) -> None:
    committed = REPO_ROOT / "artifacts/source_registry_external" / JSON_NAME
    if not committed.exists():
        pytest.skip("registry artifact not generated in this tree")
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        write_external_source_registry_artifacts(
            imported=imported, repo_root=Path(tmp)
        )
        fresh = (
            Path(tmp) / "artifacts/source_registry_external" / JSON_NAME
        ).read_bytes()
    assert hashlib.sha256(committed.read_bytes()).hexdigest() == (
        hashlib.sha256(fresh).hexdigest()
    )


def test_artifact_writer_refuses_a_monitoring_claim(
    tmp_path: Path, imported: dict
) -> None:
    doctored = json.loads(json.dumps(imported))
    doctored["monitoring_started"] = True
    with pytest.raises(RegistryArtifactError):
        write_external_source_registry_artifacts(
            imported=doctored, repo_root=tmp_path
        )
    assert not (tmp_path / "artifacts").exists()


def test_artifact_writer_refuses_a_banned_phrase(imported: dict) -> None:
    bundle = build_registry_artifacts(imported=imported)
    summary = render_registry_summary(
        imported=bundle["imported"],
        seed_set=bundle["seed_set"],
        watchlist=bundle["watchlist"],
    ) + "\nsource monitoring started\n"
    failures = artifact_claim_failures(bundle, summary)
    assert "banned_phrase:source monitoring started" in failures


def test_summary_states_the_boundaries(imported: dict) -> None:
    bundle = build_registry_artifacts(imported=imported)
    summary = render_registry_summary(
        imported=bundle["imported"],
        seed_set=bundle["seed_set"],
        watchlist=bundle["watchlist"],
    )
    assert "no scraper was" in summary.lower()
    assert "Sources being monitored: **0**" in summary
    assert "URLs fetched during import: **0**" in summary
    assert "NOT_DETERMINED_BY_REGISTRY" in summary
    assert "not legal advice" in summary.lower()


def test_no_existing_corpus_fixture_is_touched(imported: dict, tmp_path: Path) -> None:
    def digest() -> str:
        h = hashlib.sha256()
        for path in sorted((REPO_ROOT / "fixtures/real_grants_corpus").rglob("*.json")):
            h.update(path.read_bytes())
        return h.hexdigest()

    before = digest()
    write_external_source_registry_artifacts(imported=imported, repo_root=tmp_path)
    assert digest() == before


# ---------------------------------------------------------------------------
# Fields the reporting-requirements lane will need (doc 508)
# ---------------------------------------------------------------------------

# The reporting/lifecycle lane is a future gate, but it will read these columns
# off the registry rather than re-parsing the CSV. Pinned here so a refactor of
# the import shape cannot quietly drop one and only be noticed a gate later.
REPORTING_LANE_FIELDS = (
    "data_format",
    "monitoring_method",
    "source_type",
    "program_examples",
    "notes",
    "software_cost_allowability",
    "eligibility_classes",
    "agency_or_org",
    "subagency",
    "url",
    "robots_or_terms_risk",
)


@pytest.mark.parametrize("field", REPORTING_LANE_FIELDS)
def test_reporting_lane_fields_survive_import(imported: dict, field: str) -> None:
    assert field in EXPECTED_COLUMNS
    for source in imported["sources"]:
        assert field in source, f"{field} dropped from {source['source_id']}"


@pytest.mark.parametrize("field", REPORTING_LANE_FIELDS)
def test_reporting_lane_fields_survive_the_artifacts(
    tmp_path: Path, imported: dict, field: str
) -> None:
    write_external_source_registry_artifacts(imported=imported, repo_root=tmp_path)
    out = tmp_path / "artifacts/source_registry_external"

    payload = json.loads((out / JSON_NAME).read_text(encoding="utf-8"))
    for source in payload["sources"]:
        assert field in source, f"{field} missing from JSON artifact"

    header = (out / CSV_NAME).read_text(encoding="utf-8").splitlines()[0].split(",")
    assert field in header, f"{field} missing from seed CSV header"


def test_reporting_lane_fields_carry_real_content(imported: dict) -> None:
    """Present is not the same as populated.

    `notes` and `subagency` are legitimately sparse in the seed; the rest should
    be populated on every row, and a drop to zero would mean the column stopped
    being read rather than that the data changed.
    """
    sparse = {"notes", "subagency"}
    for field in REPORTING_LANE_FIELDS:
        populated = sum(
            1 for s in imported["sources"] if (s.get(field) or "").strip()
        )
        if field in sparse:
            assert populated > 0, field
        else:
            assert populated == 55, f"{field} populated on only {populated}/55"


# ---------------------------------------------------------------------------
# The registry does not move Baseline X
# ---------------------------------------------------------------------------


def test_baseline_x_is_untouched_by_the_registry() -> None:
    from nativeforge.services.discovery_baseline_x_service import (
        build_discovery_baseline_x,
    )

    baseline = build_discovery_baseline_x(repo_root=REPO_ROOT)
    assert baseline["corpus_summary"]["total_records"] == 185
    assert baseline["corpus_summary"]["live_records"] == 0
    assert baseline["source_coverage"]["monitored_sources"] == 0
    assert baseline["opportunity_quality"]["recorded_verified_records"] == 18
    assert baseline["readiness_summary"]["baseline_quality_score"] == 0.0865
    assert baseline["improvement_claim_allowed"] is False
    assert baseline["live_coverage_claimed"] is False
    assert baseline["source_monitoring_claimed"] is False
