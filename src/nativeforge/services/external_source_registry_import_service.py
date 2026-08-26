"""External source registry import (Gate 90B).

Parses the Perplexity source-discovery CSV into validated registry seed entries.

**This module reads a committed CSV. It does not fetch anything.** The `url`
column is carried through as data and is never requested - a test greps this
source for every HTTP client to keep it that way.

## What an imported row is, and is not

It is a *candidate source*: somewhere NativeForge might one day look. It is:

- **not** live coverage - nothing has been fetched
- **not** monitoring - ``monitoring_status`` is a constant ``not_started``
- **not** an eligibility finding - ``eligibility_classes`` is the dossier's
  summary of what a program family generally contemplates, and the NOFO controls
- **not** an allowability finding - ``software_cost_allowability`` is a
  prioritisation hint, not a determination that anyone may buy software with it

Those four separations are the whole point of the import, and each gets its own
status field so a later reader cannot collapse them.

## UNKNOWN is preserved literally

23 cells in the seed CSV read ``UNKNOWN``. They are carried through as the
string, never coerced to ``False``, ``None``, or a default. An unknown
capability is not an absent one - this campaign spent four gates on a field that
meant less than it looked like, and the fix is to keep not-knowing visible.

## Capability is not approval

``has_api: Yes`` says an API exists. It does not say NativeForge may use it: 4
of the 5 API-capable rows in the seed carry ``API_TERMS`` obligations. The two
facts stay in separate fields (``has_api`` and ``terms_status``) and
``activation_blocked_reasons`` records the gap.
"""

from __future__ import annotations

import csv
import io
import json
from typing import Any

SCHEMA_VERSION = "nf_external_source_registry_import_v1"

# Exact column set, in order. A CSV that does not match is refused rather than
# partially read - a silently missing column would become a silently missing
# blocker.
EXPECTED_COLUMNS: tuple[str, ...] = (
    "source_id",
    "source_name",
    "source_type",
    "agency_or_org",
    "subagency",
    "jurisdiction",
    "federal_or_state_or_private",
    "state_if_applicable",
    "url",
    "monitoring_method",
    "scraper_difficulty",
    "robots_or_terms_risk",
    "native_relevance",
    "eligibility_classes",
    "federal_recognition_required",
    "state_recognition_supported",
    "software_cost_allowability",
    "program_examples",
    "deadline_pattern",
    "update_frequency",
    "data_format",
    "has_api",
    "has_rss_or_email",
    "requires_login",
    "notes",
    "priority_tier",
)

REQUIRED_NON_BLANK: tuple[str, ...] = (
    "source_id",
    "source_name",
    "federal_or_state_or_private",
    "priority_tier",
)

PRIORITY_TIERS = frozenset({"Tier 1", "Tier 2", "Tier 3", "Tier 4"})

JURISDICTION_CLASSES = frozenset({"federal", "state", "private"})

MONITORING_METHODS = frozenset(
    {
        "API monitor",
        "RSS/feed monitor",
        "static HTML page monitor",
        "PDF/NOFO page monitor",
        "search endpoint monitor",
        "email bulletin/manual intake",
        "human review only",
    }
)

# Risk buckets. UNKNOWN is a member, not an error.
ROBOTS_TERMS_RISKS = frozenset(
    {"low", "API_TERMS", "TERMS_REVIEW_REQUIRED", "HUMAN_REVIEW_ONLY", "UNKNOWN"}
)

# Risks that block activation outright. Derived as the complement of the
# permitted set, so a bucket added later blocks until someone permits it.
NON_BLOCKING_RISKS = frozenset({"low"})
BLOCKING_RISKS = ROBOTS_TERMS_RISKS - NON_BLOCKING_RISKS

# Tri-state. The CSV uses several spellings for "it depends"; all of them mean
# not-a-plain-yes and are kept distinct from a plain No.
TRISTATE_YES = frozenset({"Yes"})
TRISTATE_NO = frozenset({"No"})
TRISTATE_OTHER = frozenset({"UNKNOWN", "Varies", "API key"})
TRISTATE_VALUES = TRISTATE_YES | TRISTATE_NO | TRISTATE_OTHER

REGISTRY_STATUS = "seed_imported"
MONITORING_STATUS = "not_started"

TERMS_STATUSES = frozenset(
    {"NO_REVIEW_REQUIRED", "ATTRIBUTION_REQUIRED", "TERMS_REVIEW_REQUIRED",
     "HUMAN_REVIEW_ONLY", "UNKNOWN"}
)

STATE_SCOPE_STATUSES = frozenset(
    {"federal_all_customers", "state_scoped", "private_unscoped", "unknown"}
)

# Both constants, on every row. Import establishes neither.
ELIGIBILITY_STATUS = "NOT_DETERMINED_BY_REGISTRY"
ALLOWABILITY_STATUS = "NOT_DETERMINED_BY_REGISTRY"


class SourceRegistryImportError(ValueError):
    """Raised when the CSV cannot be trusted enough to import."""


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _clean(value: Any) -> str:
    return (value or "").strip() if isinstance(value, str) else ""


def _terms_status_for(risk: str, requires_login: str) -> str:
    """Map a risk bucket plus login requirement onto a review obligation.

    Login is resolved **before** the risk bucket, deliberately. A source needing
    an API key or an account requires somebody to obtain and own a credential,
    and that is a decision, not an implementation detail - so it outranks a
    merely-attribution risk bucket.

    Getting this order wrong made `FED-SIMPLER` (`requires_login: API key`,
    `robots_or_terms_risk: API_TERMS`) read as attribution-only and clear for
    automation, which it is not.
    """
    if risk == "HUMAN_REVIEW_ONLY" or requires_login == "Yes":
        return "HUMAN_REVIEW_ONLY"
    if requires_login in {"Varies", "API key"}:
        return "TERMS_REVIEW_REQUIRED"
    if risk == "TERMS_REVIEW_REQUIRED":
        return "TERMS_REVIEW_REQUIRED"
    if risk == "API_TERMS":
        # Attribution and rate obligations rather than a blocker. Still not a
        # clearance: it is a condition somebody has to implement.
        return "ATTRIBUTION_REQUIRED"
    if risk == "UNKNOWN":
        return "UNKNOWN"
    return "NO_REVIEW_REQUIRED"


def _state_scope_for(jurisdiction_class: str, state: str) -> str:
    if jurisdiction_class == "federal":
        return "federal_all_customers"
    if jurisdiction_class == "state":
        return "state_scoped" if state else "unknown"
    if jurisdiction_class == "private":
        return "state_scoped" if state else "private_unscoped"
    return "unknown"


def import_external_source_registry(
    *, csv_text: str, source_label: str = "external_source_registry_csv"
) -> dict[str, Any]:
    """Parse and validate the registry CSV.

    Raises :class:`SourceRegistryImportError` on any structural problem. The
    import is all-or-nothing: a registry that is half-valid would be a registry
    whose blockers might be in the missing half.
    """
    reader = csv.DictReader(io.StringIO(csv_text))
    columns = tuple(reader.fieldnames or ())

    if columns != EXPECTED_COLUMNS:
        missing = [c for c in EXPECTED_COLUMNS if c not in columns]
        extra = [c for c in columns if c not in EXPECTED_COLUMNS]
        raise SourceRegistryImportError(
            "csv columns do not match the expected set; "
            f"missing={missing} extra={extra}"
        )

    imported: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    for index, raw in enumerate(reader, start=2):  # start=2: row 1 is the header
        row = {key: _clean(raw.get(key)) for key in EXPECTED_COLUMNS}

        for field in REQUIRED_NON_BLANK:
            if not row[field]:
                raise SourceRegistryImportError(
                    f"row {index}: blank required field {field!r}"
                )

        source_id = row["source_id"]
        if source_id in seen_ids:
            raise SourceRegistryImportError(
                f"row {index}: duplicate source_id {source_id!r}"
            )
        seen_ids.add(source_id)

        tier = row["priority_tier"]
        if tier not in PRIORITY_TIERS:
            raise SourceRegistryImportError(
                f"row {index}: priority_tier {tier!r} not in {sorted(PRIORITY_TIERS)}"
            )

        jclass = row["federal_or_state_or_private"]
        if jclass not in JURISDICTION_CLASSES:
            raise SourceRegistryImportError(
                f"row {index}: federal_or_state_or_private {jclass!r} "
                f"not in {sorted(JURISDICTION_CLASSES)}"
            )

        method = row["monitoring_method"]
        if method and method not in MONITORING_METHODS:
            raise SourceRegistryImportError(
                f"row {index}: monitoring_method {method!r} not recognised"
            )

        risk = row["robots_or_terms_risk"] or "UNKNOWN"
        if risk not in ROBOTS_TERMS_RISKS:
            raise SourceRegistryImportError(
                f"row {index}: robots_or_terms_risk {risk!r} not a known bucket"
            )

        for field in ("has_api", "has_rss_or_email", "requires_login"):
            value = row[field]
            if value and value not in TRISTATE_VALUES:
                raise SourceRegistryImportError(
                    f"row {index}: {field}={value!r} is not a tri-state value"
                )

        state = row["state_if_applicable"]

        # A state row without a state cannot be filtered, so it cannot be
        # imported - it would be visible to every customer by default, which is
        # precisely the leak this gate exists to prevent.
        if jclass == "state" and not state:
            raise SourceRegistryImportError(
                f"row {index}: state row {source_id!r} has no state_if_applicable"
            )

        # And a federal row must not carry a state, which would silently narrow
        # a nationally available source.
        if jclass == "federal" and state:
            raise SourceRegistryImportError(
                f"row {index}: federal row {source_id!r} carries "
                f"state_if_applicable={state!r}; a federal source must not be "
                "scoped to one state"
            )

        blocked: list[str] = []
        terms_status = _terms_status_for(risk, row["requires_login"])
        if risk in BLOCKING_RISKS:
            blocked.append(f"robots_or_terms_risk:{risk}")
        if row["requires_login"] in {"Yes", "Varies", "API key"}:
            blocked.append(f"requires_login:{row['requires_login']}")
        if method == "human review only":
            blocked.append("monitoring_method:human_review_only")
        # Nothing is monitored, so every row carries this. Stated per row rather
        # than assumed, so the artifact shows it on its face.
        blocked.append("monitoring_not_started")

        entry = dict(row)
        entry.update(
            {
                "registry_status": REGISTRY_STATUS,
                "monitoring_status": MONITORING_STATUS,
                "terms_status": terms_status,
                "state_scope_status": _state_scope_for(jclass, state),
                "eligibility_status": ELIGIBILITY_STATUS,
                "allowability_status": ALLOWABILITY_STATUS,
                "activation_blocked_reasons": blocked,
            }
        )
        imported.append(entry)

    if not imported:
        raise SourceRegistryImportError("csv contained no data rows")

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "source_label": source_label,
            "columns": list(columns),
            "imported_count": len(imported),
            "sources": imported,
            # Constants, asserted rather than described.
            "urls_fetched": 0,
            "network_access_performed": False,
            "monitoring_started": False,
            "live_coverage_claimed": False,
            "source_monitoring_claimed": False,
            "fabricated": False,
        }
    )


def summarise_import(result: dict[str, Any]) -> dict[str, Any]:
    """Counts over an imported registry, for the artifact and the docs."""
    sources = result.get("sources") or []

    def tally(field: str) -> dict[str, int]:
        counts: dict[str, int] = {}
        for s in sources:
            key = s.get(field) or "(blank)"
            counts[key] = counts.get(key, 0) + 1
        return dict(sorted(counts.items()))

    blocked = [s for s in sources if s.get("terms_status") != "NO_REVIEW_REQUIRED"]
    state_rows = [s for s in sources if s.get("state_scope_status") == "state_scoped"]

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "total_sources": len(sources),
            "by_priority_tier": tally("priority_tier"),
            "by_jurisdiction_class": tally("federal_or_state_or_private"),
            "by_monitoring_method": tally("monitoring_method"),
            "by_robots_terms_risk": tally("robots_or_terms_risk"),
            "by_terms_status": tally("terms_status"),
            "by_state_scope_status": tally("state_scope_status"),
            "has_api": tally("has_api"),
            "has_rss_or_email": tally("has_rss_or_email"),
            "requires_login": tally("requires_login"),
            "terms_review_required_count": len(blocked),
            "state_scoped_count": len(state_rows),
            "states_present": sorted(
                {
                    s["state_if_applicable"]
                    for s in state_rows
                    if s["state_if_applicable"]
                }
            ),
            # An API existing is not an API approved. Both counted so the gap is
            # visible rather than inferred.
            "api_capable_count": sum(1 for s in sources if s.get("has_api") == "Yes"),
            "api_approved_count": 0,
            "monitored_count": 0,
            "unknown_cells_preserved": sum(
                1
                for s in sources
                for k in EXPECTED_COLUMNS
                if s.get(k) == "UNKNOWN"
            ),
            "urls_fetched": 0,
            "monitoring_started": False,
            "fabricated": False,
        }
    )


def import_invariant_failures(result: dict[str, Any]) -> list[str]:
    fails: list[str] = []

    if result.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")
    if result.get("fabricated") is not False:
        fails.append("fabricated_must_be_false")
    for constant in (
        "network_access_performed",
        "monitoring_started",
        "live_coverage_claimed",
        "source_monitoring_claimed",
    ):
        if result.get(constant) is not False:
            fails.append(f"import_claimed:{constant}")
    if result.get("urls_fetched") != 0:
        fails.append("urls_fetched_non_zero")

    seen: set[str] = set()
    for source in result.get("sources") or []:
        sid = source.get("source_id")
        if not sid:
            fails.append("source_without_id")
            continue
        if sid in seen:
            fails.append(f"duplicate_source_id:{sid}")
        seen.add(sid)

        if source.get("registry_status") != REGISTRY_STATUS:
            fails.append(f"registry_status_not_seed_imported:{sid}")
        if source.get("monitoring_status") != MONITORING_STATUS:
            fails.append(f"monitoring_status_not_not_started:{sid}")
        if source.get("eligibility_status") != ELIGIBILITY_STATUS:
            fails.append(f"eligibility_asserted_by_registry:{sid}")
        if source.get("allowability_status") != ALLOWABILITY_STATUS:
            fails.append(f"allowability_asserted_by_registry:{sid}")
        if source.get("terms_status") not in TERMS_STATUSES:
            fails.append(f"terms_status_out_of_vocabulary:{sid}")
        if source.get("state_scope_status") not in STATE_SCOPE_STATUSES:
            fails.append(f"state_scope_status_out_of_vocabulary:{sid}")

        if (
            source.get("federal_or_state_or_private") == "state"
            and not source.get("state_if_applicable")
        ):
            fails.append(f"state_source_without_state:{sid}")
        if (
            source.get("federal_or_state_or_private") == "federal"
            and source.get("state_if_applicable")
        ):
            fails.append(f"federal_source_scoped_to_state:{sid}")

        # Every row must name at least the monitoring-not-started reason.
        if not source.get("activation_blocked_reasons"):
            fails.append(f"no_activation_blocked_reasons:{sid}")

    return fails
