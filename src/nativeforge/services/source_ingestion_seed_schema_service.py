"""Sprint 257: NF_SOURCE_SEED_2026.csv schema contract."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Final

SCHEMA_VERSION: Final[str] = "nf_source_seed_2026_csv_v1"
SEED_FILENAME: Final[str] = "NF_SOURCE_SEED_2026.csv"

#: The corpus as Sprint 257 shipped it. Never changes: rows added afterwards
#: are named below rather than absorbed into this number.
BASELINE_ROW_COUNT: Final[int] = 177

#: Seed ids added after the baseline, each with the gate that added it and the
#: reason. A bumped count is a changelog; this says WHICH row and on whose
#: authority, so a future change to the corpus size has to say the same thing.
#:
#: The row-count guard exists to make a corpus change impossible to miss, and
#: it worked: adding the row below turned 82 tests red in one stroke. Bumping
#: a bare 177 to 178 would have silenced it without recording anything.
POST_BASELINE_SEED_IDS: Final[tuple[str, ...]] = (
    # Gate 163. None of the 177 baseline rows had host api.grants.gov - all
    # six grants.gov rows were individual opportunity pages, not the API - so
    # the first authorized live source needed a row of its own. Approved by
    # MAYHEM with signed terms, human review and activation decisions.
    "nf-seed-2026-api-grants-gov-search2",
    # Gate 171. The API-shaped half of the first heterogeneous pair. No
    # baseline row had this host, and none was API-shaped at all - every one
    # of the 40 database registry rows is `check_method='web_page'` - so the
    # second adapter family needed a row of its own. Approved by MAYHEM for
    # exactly one robots preflight and one bounded collection.
    #
    # The HTML half needed no row: the approved BIA program page was already
    # in the corpus as nf-seed-2026-fed-007, and minting a parallel id for a
    # source already registered is how a second registry starts.
    "nf-seed-2026-api-federal-register-documents",
    # Phase 1A. Five discovery lanes on the Grants.gov search2 endpoint.
    #
    # NOT APPROVED BY ANYBODY, and that is the point of adding them. HUD ONAP,
    # IHS, EPA and CDFI do not publish machine-readable feeds - each Tranche 2
    # close says "Grants.gov owns the records" - so they are query lanes on an
    # endpoint the corpus already has, not new publishers. Forecasts are a
    # fifth lane on the same endpoint.
    #
    # They need rows because capability is measured against a row and
    # authorization is recorded on one. One row per lane is what lets Mayhem
    # authorize HUD ONAP without thereby authorizing EPA.
    #
    # Their `health_evidence` reads
    # `phase1a:capability_registered:awaiting_human_authorization`, never
    # `operator_approved`. A grep for approval still finds exactly the two
    # rows that have it.
    "nf-seed-2026-api-grants-gov-forecast",
    "nf-seed-2026-api-grants-gov-hud-onap",
    "nf-seed-2026-api-grants-gov-ihs",
    "nf-seed-2026-api-grants-gov-epa",
    "nf-seed-2026-api-grants-gov-cdfi",
    # Phase 1A, second adapter family. Denali Commission publishes a public
    # WordPress REST listing: no baseline row had this host and none was
    # WordPress-shaped, so the binding needed a row of its own. Also NOT
    # APPROVED - registered so its capability can be measured, nothing more.
    "nf-seed-2026-api-denali-wp-posts",
)

#: Derived, so the count follows the named additions instead of being a magic
#: number somebody has to remember to keep in step.
#:
#: Gate 166D: this is HISTORICAL FIXTURE INTEGRITY, not runtime source
#: authority. It records what the shipped corpus contained and is enforced as
#: a FLOOR - the corpus may not shrink below it, and each named post-baseline
#: addition must still be present by id. It is no longer an equality check,
#: because "what sources exist" must not be a constant in this file: at 1,000
#: sources that made every addition a code change and a deploy.
#:
#: What sources exist at runtime is answered by the catalog; which of them may
#: EXECUTE is answered by `source_authority_service` from signed rows. A seed
#: row grants nothing - it makes a source `registered`, which is the floor of
#: the authority ladder and never the answer.
EXPECTED_ROW_COUNT: Final[int] = BASELINE_ROW_COUNT + len(POST_BASELINE_SEED_IDS)

#: The same number, named for what Gate 166D actually enforces. Callers that
#: mean "the corpus must not have shrunk" should say so rather than reaching
#: for a constant whose name implies an equality that no longer holds.
MINIMUM_ROW_COUNT: Final[int] = EXPECTED_ROW_COUNT

REQUIRED_COLUMNS: Final[tuple[str, ...]] = (
    "seed_id",
    "canonical_source_id",
    "source_name",
    "source_url",
    "tier",
    "adapter_key",
    "source_type",
    "publisher_name",
    "state_code",
    "access_posture_hint",
    "program_family",
    "native_relevance_notes",
)

_SEED_PATH = (
    Path(__file__).resolve().parents[3]
    / "fixtures"
    / "source_ingestion"
    / SEED_FILENAME
)


def seed_csv_path() -> Path:
    return _SEED_PATH


def build_seed_schema_contract() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "seed_filename": SEED_FILENAME,
        "expected_row_count": EXPECTED_ROW_COUNT,
        "required_columns": list(REQUIRED_COLUMNS),
        "tier_values": ["1", "2", "3"],
        "access_posture_hints": ["public", "members", "login"],
        "preview_only": False,
        "candidates_not_active_by_default": True,
    }


def assert_seed_schema_contract() -> None:
    contract = build_seed_schema_contract()
    json.dumps(contract)
    assert contract["expected_row_count"] == EXPECTED_ROW_COUNT
