"""Deterministic offline fixture corpus for connector dry-runs (no network).

JSON bundles live under ``fixtures/corpus/*.json``. Each bundle lists one or more
rows shaped for :func:`static_fixture_connector.dry_run_fixture_rows` after
optional Grants.gov-like field normalization.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Final

from nativeforge.services.source_connectors.grants_gov_shaped import (
    grants_gov_like_to_fixture_row,
)

CORPUS_DIR: Final[Path] = Path(__file__).resolve().parent / "fixtures" / "corpus"

CORPUS_SCHEMA_VERSION: Final[str] = "nf_fixture_corpus_v1"

# Sprint 25 category identifiers — one canonical bundle per category.
REQUIRED_FIXTURE_CATEGORIES: Final[frozenset[str]] = frozenset(
    {
        "grants_gov_broad_tribal_eligible",
        "bia_tribal_specific",
        "ihs_tribal_health",
        "ana_language_culture",
        "doe_indian_energy",
        "hud_onap_housing",
        "epa_tribal_environment",
        "foundation_native_serving",
        "broad_rural_broadband_tribes_eligible",
        "irrelevant_broad_opportunity",
        "keyword_only_false_positive",
        "ambiguous_eligibility_case",
    }
)


def list_corpus_bundle_paths() -> list[Path]:
    """Sorted JSON paths under :data:`CORPUS_DIR`."""
    return sorted(CORPUS_DIR.glob("*.json"))


def fixture_category_from_bundle(doc: dict[str, Any]) -> str:
    cat = doc.get("fixture_category") or doc.get("fixture_profile")
    if not cat or not str(cat).strip():
        raise ValueError("fixture bundle missing fixture_category (or fixture_profile)")
    return str(cat).strip()


def load_bundle(path: Path) -> dict[str, Any]:
    """Parse one corpus JSON file."""
    text = path.read_text(encoding="utf-8")
    doc = json.loads(text)
    if not isinstance(doc, dict):
        raise ValueError(f"corpus bundle must be a JSON object: {path}")
    return doc


def materialize_bundle_rows(doc: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Expand bundle metadata into row dicts ready for the static connector.

    - Applies Grants.gov-like aliasing when ``fixture_format`` is
      ``grants_gov_like`` or legacy ``rows_are_grants_gov_like``.
    - Sets ``fixture_category``, ``fixture_key``, and optional schema version
      on each row for provenance passthrough.
    """
    category = fixture_category_from_bundle(doc)
    schema_ver = doc.get("corpus_schema_version") or CORPUS_SCHEMA_VERSION
    fmt = str(doc.get("fixture_format") or "")
    legacy_gg = bool(doc.get("rows_are_grants_gov_like", False))
    use_gg_shape = fmt == "grants_gov_like" or legacy_gg

    rows_in = doc.get("rows")
    if not isinstance(rows_in, list):
        raise ValueError(f"bundle {category!r} requires a list 'rows'")

    out: list[dict[str, Any]] = []
    for idx, row in enumerate(rows_in):
        if not isinstance(row, dict):
            raise ValueError(f"bundle {category!r}: rows[{idx}] must be an object")
        raw = dict(row)
        if use_gg_shape:
            raw = grants_gov_like_to_fixture_row(raw)

        raw.setdefault("fixture_category", category)
        raw.setdefault("corpus_schema_version", schema_ver)

        fk = raw.get("fixture_key") or raw.get("opportunity_number")
        if fk is None or not str(fk).strip():
            fk = f"{category}-{idx:03d}"
        raw["fixture_key"] = str(fk).strip()

        synopsis = raw.get("synopsis")
        if synopsis is not None and raw.get("raw_nofo_text") is None:
            raw["raw_nofo_text"] = str(synopsis).strip()

        out.append(raw)
    return out


def load_category_rows(category: str) -> list[dict[str, Any]]:
    """Load rows for a single required category."""
    for path in list_corpus_bundle_paths():
        doc = load_bundle(path)
        if fixture_category_from_bundle(doc) == category:
            return materialize_bundle_rows(doc)
    raise KeyError(f"unknown fixture category: {category}")


def load_all_corpus_rows_flat() -> list[dict[str, Any]]:
    """Every materialized row from every bundle (deterministic path order)."""
    combined: list[dict[str, Any]] = []
    for path in list_corpus_bundle_paths():
        doc = load_bundle(path)
        combined.extend(materialize_bundle_rows(doc))
    return combined


def corpus_bundle_count() -> int:
    return len(list_corpus_bundle_paths())


def corpus_row_count() -> int:
    return len(load_all_corpus_rows_flat())


def validate_corpus_categories_present() -> dict[str, Any]:
    """
    Ensure each :data:`REQUIRED_FIXTURE_CATEGORIES` appears exactly once
    across bundles (filename may differ; identity is ``fixture_category``).
    """
    seen: dict[str, str] = {}
    for path in list_corpus_bundle_paths():
        doc = load_bundle(path)
        cat = fixture_category_from_bundle(doc)
        if cat in seen:
            raise ValueError(
                f"duplicate fixture_category {cat!r} in {path} and {seen[cat]}"
            )
        seen[cat] = str(path)
    missing = sorted(REQUIRED_FIXTURE_CATEGORIES - set(seen.keys()))
    extra = sorted(set(seen.keys()) - REQUIRED_FIXTURE_CATEGORIES)
    return {"present": seen, "missing": missing, "extra": extra}


def assert_complete_required_corpus() -> None:
    report = validate_corpus_categories_present()
    if report["missing"]:
        raise ValueError(f"corpus missing categories: {report['missing']}")
    if report["extra"]:
        raise ValueError(f"corpus has unknown categories: {report['extra']}")
