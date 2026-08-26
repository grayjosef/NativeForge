"""External source registry artifacts (Gate 90F).

Renders the imported registry into `artifacts/source_registry_external/`.

Writing is confined to this module, as with the Baseline X artifacts: the
import, seed, filter and allowability services all return values and open
nothing for writing.

## Refusal

`write_external_source_registry_artifacts` raises before touching the
filesystem if the import or seed set carries a forbidden claim, or if the
rendered summary contains a banned phrase. A registry that has drifted into
claiming monitoring should leave nothing behind to be quoted later.
"""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path
from typing import Any

from nativeforge.services.customer_state_source_filter_service import (
    filter_sources_for_customer,
)
from nativeforge.services.external_source_registry_import_service import (
    EXPECTED_COLUMNS,
    import_invariant_failures,
    summarise_import,
)
from nativeforge.services.external_source_registry_seed_service import (
    build_registry_seed_set,
    seed_invariant_failures,
)
from nativeforge.services.nativeforge_software_allowability_source_service import (
    allowability_invariant_failures,
    build_software_allowability_watchlist,
)

SCHEMA_VERSION = "nf_external_source_registry_artifact_v1"

ARTIFACT_DIR = "artifacts/source_registry_external"
JSON_NAME = "external_source_registry_seed.json"
CSV_NAME = "external_source_registry_seed.csv"
SUMMARY_NAME = "external_source_registry_summary.md"
TERMS_QUEUE_NAME = "terms_review_queue.csv"
STATE_SOURCES_NAME = "state_specific_sources.csv"
WATCHLIST_NAME = "software_allowability_watchlist.csv"

# Phrases that must never reach an artifact. `monitoring active` and friends
# because nothing is monitored; the improvement phrases carried over from the
# Baseline X guard so one artifact family cannot say what the other refuses to.
BANNED_PHRASES: tuple[str, ...] = (
    "monitoring active",
    "monitoring is active",
    "source monitoring started",
    "live coverage",
    "live source coverage",
    "65% improvement",
    "improvement over",
    "scraper activated",
)


class RegistryArtifactError(RuntimeError):
    """Raised when a registry artifact would carry a forbidden claim."""


def _rows_to_csv(rows: list[dict[str, Any]], columns: list[str]) -> str:
    buffer = io.StringIO()
    writer = csv.DictWriter(
        buffer, fieldnames=columns, extrasaction="ignore", lineterminator="\n"
    )
    writer.writeheader()
    for row in rows:
        writer.writerow(
            {
                c: (
                    ";".join(str(v) for v in row.get(c))
                    if isinstance(row.get(c), list)
                    else row.get(c)
                )
                for c in columns
            }
        )
    return buffer.getvalue()


SEED_CSV_COLUMNS = [
    *EXPECTED_COLUMNS,
    "registry_status",
    "monitoring_status",
    "terms_status",
    "state_scope_status",
    "eligibility_status",
    "allowability_status",
    "activation_blocked_reasons",
]

TERMS_QUEUE_COLUMNS = [
    "source_id", "source_name", "priority_tier", "robots_or_terms_risk",
    "terms_status", "requires_login", "monitoring_method", "url",
    "activation_blocked_reasons",
]

STATE_COLUMNS = [
    "source_id", "source_name", "state_if_applicable", "priority_tier",
    "source_type", "federal_recognition_required", "state_recognition_supported",
    "notes", "url",
]

WATCHLIST_COLUMNS = [
    "source_id", "source_name", "priority_tier", "allowability_class",
    "raw_allowability_value", "on_watchlist",
]


def render_registry_summary(
    *, imported: dict[str, Any], seed_set: dict[str, Any], watchlist: dict[str, Any]
) -> str:
    summary = summarise_import(imported)
    lines: list[str] = []
    add = lines.append

    add("# External source registry seed")
    add("")
    add(
        "A seed registry of candidate funding sources, imported from a "
        "source-discovery dossier. **No URL was requested, no scraper was "
        "started, and nothing here is being watched.**"
    )
    add("")
    add(f"- Sources imported: **{summary['total_sources']}**")
    add(f"- Sources being monitored: **{summary['monitored_count']}**")
    add(f"- URLs fetched during import: **{summary['urls_fetched']}**")
    add("")

    add("## What a registry entry is not")
    add("")
    add(
        "Being listed here answers one question: *is this somewhere we might "
        "look?* It does not say a customer qualifies, and it does not say an "
        "award could pay for software. Those are tracked as separate statuses "
        "and both read `NOT_DETERMINED_BY_REGISTRY` on every row."
    )
    add("")

    add("## Tiers and jurisdiction")
    add("")
    add("| Priority tier | Sources |")
    add("| --- | --- |")
    for tier, n in summary["by_priority_tier"].items():
        add(f"| {tier} | {n} |")
    add("")
    add("| Jurisdiction | Sources |")
    add("| --- | --- |")
    for k, n in summary["by_jurisdiction_class"].items():
        add(f"| {k} | {n} |")
    add("")

    add("## Terms review")
    add("")
    add("| Terms status | Sources |")
    add("| --- | --- |")
    for k, n in summary["by_terms_status"].items():
        add(f"| `{k}` | {n} |")
    add("")
    add(
        f"**{summary['terms_review_required_count']} of "
        f"{summary['total_sources']} sources carry an obligation or a blocker.** "
        "None may be automated before that is resolved, and "
        f"{seed_set['human_review_only_count']} may only ever be checked by a "
        "person."
    )
    add("")

    add("## Capability is not approval")
    add("")
    add(
        f"{summary['api_capable_count']} sources expose an API. "
        f"**{summary['api_approved_count']} are approved for automated use.** "
        "The two are separate fields and an invariant keeps the approved count "
        "at zero until somebody clears them."
    )
    add("")

    add("## State scoping")
    add("")
    add(
        f"{summary['state_scoped_count']} sources are state-scoped, covering "
        f"{', '.join(summary['states_present']) or 'no states'}. They are "
        "visible only to customers whose declared **operating state(s)** "
        "include that state - not their mailing address. A customer with no "
        "declared operating state sees none of them."
    )
    add("")

    add("## Software allowability")
    add("")
    add("| Class | Sources |")
    add("| --- | --- |")
    for k, n in watchlist["by_allowability_class"].items():
        add(f"| `{k}` | {n} |")
    add("")
    add(
        f"**{watchlist['watchlist_count']} sources reach the watchlist.** "
        "`sometimes_allowable` is deliberately excluded from it: most of the "
        "registry reads that way, so a watchlist including it would be the "
        "registry with extra steps."
    )
    add("")
    add(
        "This is a prioritisation aid, not legal advice. No entry says a "
        "customer may buy anything; every one requires a live NOFO and an "
        "approved budget first."
    )
    add("")

    add("## Unknowns preserved")
    add("")
    add(
        f"{summary['unknown_cells_preserved']} cells read `UNKNOWN` and are "
        "carried through as written. An unknown capability is not an absent "
        "one."
    )
    add("")

    return "\n".join(lines) + "\n"


def build_registry_artifacts(*, imported: dict[str, Any]) -> dict[str, Any]:
    """Everything the artifact files are rendered from. Pure."""
    sources = imported.get("sources") or []
    seed_set = build_registry_seed_set(imported=imported)
    watchlist = build_software_allowability_watchlist(sources=sources)

    terms_rows = [
        s for s in sources if s.get("terms_status") != "NO_REVIEW_REQUIRED"
    ]
    state_rows = [
        s for s in sources if s.get("state_scope_status") == "state_scoped"
    ]

    return {
        "imported": imported,
        "seed_set": seed_set,
        "watchlist": watchlist,
        "summary": summarise_import(imported),
        "terms_rows": terms_rows,
        "state_rows": state_rows,
    }


def artifact_claim_failures(bundle: dict[str, Any], summary_text: str) -> list[str]:
    fails: list[str] = []
    fails += import_invariant_failures(bundle["imported"])
    fails += seed_invariant_failures(bundle["seed_set"])
    fails += allowability_invariant_failures(bundle["watchlist"])

    lowered = summary_text.lower()
    for phrase in BANNED_PHRASES:
        if phrase in lowered:
            fails.append(f"banned_phrase:{phrase}")

    # A last structural check: nothing may claim to be monitored.
    if bundle["summary"].get("monitored_count") != 0:
        fails.append("summary_reports_monitored_sources")
    return fails


def write_external_source_registry_artifacts(
    *,
    imported: dict[str, Any],
    repo_root: Any = None,
    artifact_dir: str = ARTIFACT_DIR,
) -> dict[str, Any]:
    bundle = build_registry_artifacts(imported=imported)
    summary_text = render_registry_summary(
        imported=bundle["imported"],
        seed_set=bundle["seed_set"],
        watchlist=bundle["watchlist"],
    )

    failures = artifact_claim_failures(bundle, summary_text)
    if failures:
        raise RegistryArtifactError(
            "refusing to write external source registry artifacts: "
            + ", ".join(sorted(failures))
        )

    root = Path(repo_root) if repo_root else Path(__file__).resolve().parents[3]
    out_dir = root / artifact_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    payload = json.dumps(
        {
            "schema_version": SCHEMA_VERSION,
            "summary": bundle["summary"],
            "seed_set": bundle["seed_set"],
            "sources": bundle["imported"]["sources"],
        },
        indent=2,
        sort_keys=True,
    ) + "\n"

    seed_csv = _rows_to_csv(bundle["imported"]["sources"], SEED_CSV_COLUMNS)
    terms_csv = _rows_to_csv(bundle["terms_rows"], TERMS_QUEUE_COLUMNS)
    state_csv = _rows_to_csv(bundle["state_rows"], STATE_COLUMNS)
    watch_csv = _rows_to_csv(
        bundle["watchlist"]["classifications"], WATCHLIST_COLUMNS
    )

    (out_dir / JSON_NAME).write_text(payload, encoding="utf-8")
    (out_dir / CSV_NAME).write_text(seed_csv, encoding="utf-8")
    (out_dir / SUMMARY_NAME).write_text(summary_text, encoding="utf-8")
    (out_dir / TERMS_QUEUE_NAME).write_text(terms_csv, encoding="utf-8")
    (out_dir / STATE_SOURCES_NAME).write_text(state_csv, encoding="utf-8")
    (out_dir / WATCHLIST_NAME).write_text(watch_csv, encoding="utf-8")

    return {
        "schema_version": SCHEMA_VERSION,
        "artifact_dir": str(out_dir),
        "files": [
            JSON_NAME, CSV_NAME, SUMMARY_NAME,
            TERMS_QUEUE_NAME, STATE_SOURCES_NAME, WATCHLIST_NAME,
        ],
        "source_count": len(bundle["imported"]["sources"]),
        "terms_queue_rows": len(bundle["terms_rows"]),
        "state_rows": len(bundle["state_rows"]),
        "watchlist_rows": bundle["watchlist"]["watchlist_count"],
        "monitored_count": 0,
        "urls_fetched": 0,
        "claim_failures": [],
    }


def load_customer_view(
    *, imported: dict[str, Any], operating_states: Any = None
) -> dict[str, Any]:
    """Convenience: seed set filtered for one customer. Used by tests and docs."""
    seed_set = build_registry_seed_set(imported=imported)
    return filter_sources_for_customer(
        seeds=seed_set["seeds"], operating_states=operating_states
    )
