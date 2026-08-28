"""Tribal eligibility classification bridge guard (Gate 105C).

Keeps mixed-corpus classification from drifting away from the canonical Tribal
eligibility vocabulary again.

## The drift this exists to catch

Gate 105A found `mixed_corpus_grant_field_derivation_service` importing the
canonical `_TRIBAL_TYPE_RE` and then rebinding the same name to a narrower local
regex. The module read as bridged and was not. Two alternatives were missing, so
"Indian tribe" and "tribal government" - ordinary federal NOFO phrasing - were
not recognised as Tribal applicant types.

## Detected, not declared

Alignment is measured by running both sides on the same phrase, not by comparing
pattern strings and not by reading a flag. A module that claims to bridge and
does not will fail here, which is precisely the case that shipped.

The mixed-corpus side is probed through its public entry point
`derive_mixed_corpus_grant_fields` rather than by reaching for its module
globals, because what matters is the answer a caller actually gets. Both real
detection paths are exercised:

```text
structured_applicant_type  synopsis applicantTypes[].description
eligibility_text           free-text eligibility on a tribal_eligible grant
```

## The rules

```text
canonical positive, mixed-corpus positive   aligned
canonical positive, mixed-corpus negative   under-detection - a defect
canonical negative, mixed-corpus positive   over-claim - prohibited outright
canonical negative, mixed-corpus negative   aligned
```

Under-detection is the failure mode Gate 105 fixed and it is treated as a defect
rather than a tolerable conservatism: a Native-relevant platform that fails to
notice Tribal eligibility scores a genuinely eligible opportunity as excluded.

Over-claiming stays prohibited and is reported separately as
`fabricated_eligibility`, because the two failures are not symmetric. Missing an
opportunity costs a tenant a deadline; inventing eligibility costs them a
rejected application and their credibility. Widening detection must never become
licence to assert eligibility the source text does not support.

## No local shadows

`find_shadowed_canonical_names` parses each bridged module with `ast` and reports
any module-level assignment to a name it imported from the canonical module. A
text search would miss a rebinding written differently and would trip over its
own documentation; the syntax tree answers the actual question.
"""

from __future__ import annotations

import ast
import csv
import importlib
import io
import json
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "nf_tribal_eligibility_classification_bridge_guard_v1"

CANONICAL_MODULE = (
    "nativeforge.services.real_grant_classification_input_adapter_service"
)

# Every module that consumes the canonical Tribal vocabulary.
BRIDGED_MODULES: tuple[str, ...] = (
    "nativeforge.services.mixed_corpus_grant_field_derivation_service",
    "nativeforge.services.tribal_grant_eligibility_reingest_service",
)

# Names owned by the canonical module. Importing them is the point; rebinding
# them at module level is the drift.
CANONICAL_NAMES = frozenset({"_TRIBAL_TYPE_RE"})

DETECTION_PATHS = frozenset({"structured_applicant_type", "eligibility_text"})

# The three phrases Gate 104 reported, plus realistic variants the canonical
# vocabulary already supports. Nothing here is invented for the guard.
CANONICAL_POSITIVE_PHRASES: tuple[str, ...] = (
    "Eligible: any Indian tribe",
    "Open to tribal governments",
    "Federally recognized tribe only",
    "Indian Tribes",
    "Tribal governments",
    "federally recognized Indian Tribe",
    "Native American tribal organization",
    "Native American tribal governments (Federally recognized)",
)

# Text with no Tribal applicant type in it. Both sides must stay negative.
NON_TRIBAL_PHRASES: tuple[str, ...] = (
    "Open to state governments and universities",
    "Nonprofits having a 501(c)(3) status",
    "City or township governments",
    "Public and State controlled institutions of higher education",
    "This program funds rural broadband deployment.",
    "",
)

ROW_FIELDS: tuple[str, ...] = (
    "canonical_phrase",
    "canonical_detected",
    "mixed_corpus_detected",
    "classification_aligned",
    "blocked_reasons",
    "fabricated_eligibility",
)

# Under-detection this gate does not own.
#
# The free-text path runs through `grants_gov_eligibility_parser_service`, which
# decides `tribal_eligible` from body text using its own vocabulary. If it says
# a grant is not Tribal-eligible, mixed-corpus derivation never reaches the
# applicant-type branch at all, so the applicant-type bridge cannot be the cause
# and fixing the bridge cannot be the cure.
#
# Registered here so the row stays visible and attributed instead of being
# quietly dropped from the phrase list. Each entry is *verified* against the
# upstream parser at report time rather than trusted - see
# `_upstream_gap_confirmed` - and a test fails the moment an entry stops being
# real, so this registry expires itself when upstream is fixed rather than
# rotting into a permanent excuse.
UPSTREAM_GAP_OWNER = "grants_gov_eligibility_parser_service.tribal_eligible"
BRIDGE_OWNER = "applicant_type_bridge"

KNOWN_UPSTREAM_GAPS: tuple[dict[str, str], ...] = (
    {
        "canonical_phrase": "Native American tribal organization",
        "detection_path": "eligibility_text",
        "owner": UPSTREAM_GAP_OWNER,
        "reason": (
            "the body-text parser does not treat a tribal organization as "
            "tribal_eligible, so derivation never reaches the applicant-type "
            "branch this gate owns"
        ),
    },
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def canonical_detects(phrase: str) -> bool:
    """Does the canonical classifier see a Tribal applicant type in this text?

    Asked through `derive_explicit_source_evidence` rather than the raw pattern,
    so the guard measures the lane's answer and not one of its internals.
    """
    from nativeforge.services.real_grant_classification_input_adapter_service import (
        derive_explicit_source_evidence,
    )

    evidence = derive_explicit_source_evidence({"eligibility_text": phrase})
    return "applicant_types_tribal_in_source" in evidence


def mixed_corpus_detects(phrase: str, *, path: str = "eligibility_text") -> bool:
    """Does mixed-corpus derivation see a Tribal applicant type in this text?

    Probed through the public entry point, along whichever real detection path
    the caller names.
    """
    from nativeforge.services.mixed_corpus_grant_field_derivation_service import (
        derive_mixed_corpus_grant_fields,
    )

    if path not in DETECTION_PATHS:
        raise ValueError(f"unknown detection path: {path}")

    if path == "structured_applicant_type":
        derived = derive_mixed_corpus_grant_fields(
            {"grant_id": "guard-probe"},
            synopsis={"applicantTypes": [{"description": phrase}]},
        )
    else:
        # Free text arrives as applicantEligibilityDesc, which is how
        # `_pull_to_grant` builds a row and therefore the shape the shadowed
        # pattern actually mis-answered.
        #
        # Passing `tribal_eligible=True` on the grant instead would prove
        # nothing: `parse_grants_gov_synopsis_eligibility(None)` returns
        # `tribal_eligible: False` and derivation overwrites the caller's flag
        # with it, so the branch under test would never run and every phrase
        # would read as under-detected. Probe the real path or the probe lies.
        derived = derive_mixed_corpus_grant_fields(
            {"grant_id": "guard-probe"},
            synopsis={"applicantEligibilityDesc": phrase},
        )
    return derived.get("applicant_types_include_tribal") is True


def _upstream_gap_confirmed(phrase: str) -> bool:
    """Is the upstream body-text parser really the reason this phrase is missed?

    Verified by asking the parser, not by trusting the registry entry. An entry
    whose stated cause has stopped being true returns False here and the guard
    reports the gap as stale.
    """
    from nativeforge.services.grants_gov_eligibility_parser_service import (
        parse_grants_gov_synopsis_eligibility,
    )

    parsed = parse_grants_gov_synopsis_eligibility({"applicantEligibilityDesc": phrase})
    return parsed.get("tribal_eligible") is not True


def _registered_upstream_gap(phrase: str, path: str) -> dict[str, str] | None:
    for gap in KNOWN_UPSTREAM_GAPS:
        if gap["canonical_phrase"] == phrase and gap["detection_path"] == path:
            return gap
    return None


def build_bridge_alignment_row(
    phrase: str, *, path: str = "eligibility_text"
) -> dict[str, Any]:
    """One phrase, both sides, and what the disagreement means."""
    canonical = canonical_detects(phrase)
    mixed = mixed_corpus_detects(phrase, path=path)

    blocked_reasons: list[str] = []
    fabricated = False
    under_detection_owner: str | None = None
    upstream_gap_stale = False

    if canonical and not mixed:
        blocked_reasons.append(f"under_detection_against_canonical:{path}")
        gap = _registered_upstream_gap(phrase, path)
        if gap is None:
            under_detection_owner = BRIDGE_OWNER
        elif _upstream_gap_confirmed(phrase):
            under_detection_owner = gap["owner"]
            blocked_reasons.append(f"upstream_gap_not_owned_here:{gap['owner']}")
        else:
            # Registered as upstream, but upstream no longer explains it.
            under_detection_owner = BRIDGE_OWNER
            upstream_gap_stale = True
            blocked_reasons.append("registered_upstream_gap_is_stale")

    if mixed and not canonical:
        # Not merely misaligned - this is the prohibited direction.
        blocked_reasons.append(f"over_claimed_tribal_eligibility:{path}")
        fabricated = True

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "canonical_phrase": phrase,
            "detection_path": path,
            "canonical_detected": canonical,
            "mixed_corpus_detected": mixed,
            "classification_aligned": canonical == mixed,
            "under_detection_owner": under_detection_owner,
            "upstream_gap_stale": upstream_gap_stale,
            "blocked_reasons": sorted(set(blocked_reasons)),
            "fabricated_eligibility": fabricated,
        }
    )


def find_shadowed_canonical_names(module_name: str) -> list[str]:
    """Canonical names this module imports and then rebinds at module level."""
    module = importlib.import_module(module_name)
    source_file = getattr(module, "__file__", None)
    if not source_file:
        return []
    tree = ast.parse(Path(source_file).read_text(encoding="utf-8"))

    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == CANONICAL_MODULE:
            for alias in node.names:
                if alias.name in CANONICAL_NAMES:
                    imported.add(alias.asname or alias.name)

    shadowed: set[str] = set()
    for node in tree.body:
        targets: list[ast.expr] = []
        if isinstance(node, ast.Assign):
            targets = list(node.targets)
        elif isinstance(node, ast.AnnAssign):
            targets = [node.target]
        for target in targets:
            if isinstance(target, ast.Name) and target.id in imported:
                shadowed.add(target.id)

    return sorted(shadowed)


def build_bridge_guard_report() -> dict[str, Any]:
    """Full alignment picture across every phrase, path and bridged module."""
    rows: list[dict[str, Any]] = []
    for phrase in CANONICAL_POSITIVE_PHRASES + NON_TRIBAL_PHRASES:
        for path in sorted(DETECTION_PATHS):
            rows.append(build_bridge_alignment_row(phrase, path=path))

    shadows = {name: find_shadowed_canonical_names(name) for name in BRIDGED_MODULES}
    modules_with_shadows = sorted(k for k, v in shadows.items() if v)

    misaligned = [r for r in rows if not r["classification_aligned"]]
    under = [r for r in rows if r["under_detection_owner"] is not None]
    over = [r for r in rows if r["fabricated_eligibility"]]

    # Under-detection this gate owns, versus under-detection it merely reports.
    bridge_under = [r for r in under if r["under_detection_owner"] == BRIDGE_OWNER]
    upstream_under = [r for r in under if r["under_detection_owner"] != BRIDGE_OWNER]
    stale_gaps = [r for r in rows if r["upstream_gap_stale"]]

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "canonical_module": CANONICAL_MODULE,
            "bridged_modules": list(BRIDGED_MODULES),
            "rows": rows,
            "row_count": len(rows),
            "aligned_count": len(rows) - len(misaligned),
            "misaligned_count": len(misaligned),
            "under_detection_count": len(under),
            "bridge_owned_under_detection_count": len(bridge_under),
            "upstream_owned_under_detection_count": len(upstream_under),
            "stale_upstream_gap_count": len(stale_gaps),
            "known_upstream_gaps": [dict(g) for g in KNOWN_UPSTREAM_GAPS],
            "over_claim_count": len(over),
            "shadowed_canonical_names": shadows,
            "modules_with_shadowed_names": modules_with_shadows,
            # The bridge is intact when nothing it owns under-detects, nothing
            # over-claims, and no module has re-shadowed a canonical name.
            # Under-detection owned upstream is reported, not absorbed.
            "bridge_intact": (
                not bridge_under and not over and not modules_with_shadows
            ),
            # Constants: this guard measures classification, it does not perform it.
            "fabricated_eligibility": False,
            "eligibility_determined": False,
            "live_source_collection": False,
            "source_monitoring_live": False,
            "source_coverage_claimed": False,
        }
    )


def bridge_guard_invariant_failures(report: dict[str, Any]) -> list[str]:
    fails: list[str] = []

    if report.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")

    for constant in (
        "fabricated_eligibility",
        "eligibility_determined",
        "live_source_collection",
        "source_monitoring_live",
        "source_coverage_claimed",
    ):
        if report.get(constant) is not False:
            fails.append(f"bridge_guard_claimed:{constant}")

    rows = report.get("rows") or []
    if not rows:
        fails.append("bridge_guard_report_without_rows")

    for row in rows:
        for field in ROW_FIELDS:
            if field not in row:
                fails.append(f"bridge_row_missing_field:{field}")
        phrase = repr(row.get("canonical_phrase"))
        # Under-detection is a defect, not an acceptable conservatism - but only
        # where the applicant-type bridge is the cause. A miss owned by the
        # upstream body-text parser is reported and attributed; failing on it
        # here would make this guard unfixable from inside its own lane.
        if row.get("under_detection_owner") == BRIDGE_OWNER:
            fails.append(f"under_detection:{phrase}")
        # A registered upstream gap that upstream no longer explains is an
        # excuse that outlived its reason. Fail it so the registry cannot rot.
        if row.get("upstream_gap_stale"):
            fails.append(f"stale_registered_upstream_gap:{phrase}")
        # Over-claiming stays prohibited, whoever owns it.
        if row.get("mixed_corpus_detected") and not row.get("canonical_detected"):
            fails.append(f"over_claimed_eligibility:{phrase}")
        # A disagreement must name itself.
        if not row.get("classification_aligned") and not row.get("blocked_reasons"):
            fails.append("misalignment_without_a_reason")
        if row.get("detection_path") not in DETECTION_PATHS:
            fails.append("detection_path_out_of_vocabulary")

    # No module may rebind a canonical name it imported.
    for module_name, shadowed in (report.get("shadowed_canonical_names") or {}).items():
        for name in shadowed:
            fails.append(f"canonical_name_shadowed:{module_name}:{name}")

    if report.get("bridge_intact") is not (
        report.get("bridge_owned_under_detection_count") == 0
        and report.get("over_claim_count") == 0
        and not report.get("modules_with_shadowed_names")
    ):
        fails.append("bridge_intact_disagrees_with_the_measurements")

    return fails


ARTIFACT_DIR = "artifacts/tribal_eligibility_classification_bridge"

MATRIX_COLUMNS: tuple[str, ...] = (
    "canonical_phrase",
    "detection_path",
    "canonical_detected",
    "mixed_corpus_detected",
    "aligned",
    "under_detection_owner",
    "fabricated_eligibility",
)


def render_bridge_matrix_csv(report: dict[str, Any]) -> str:
    """One row per phrase per detection path. Deterministic ordering."""
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(MATRIX_COLUMNS)
    for row in report.get("rows") or []:
        writer.writerow(
            [
                row.get("canonical_phrase"),
                row.get("detection_path"),
                str(bool(row.get("canonical_detected"))).lower(),
                str(bool(row.get("mixed_corpus_detected"))).lower(),
                str(bool(row.get("classification_aligned"))).lower(),
                row.get("under_detection_owner") or "",
                str(bool(row.get("fabricated_eligibility"))).lower(),
            ]
        )
    return buffer.getvalue()


def render_bridge_summary_md(report: dict[str, Any]) -> str:
    """Prose summary. States what the guard measured, not what it hopes."""
    lines: list[str] = []
    lines.append("# Tribal eligibility classification bridge")
    lines.append("")
    lines.append(f"Schema: `{report.get('schema_version')}`")
    lines.append("")
    lines.append("## What was measured")
    lines.append("")
    lines.append(
        "Every phrase is run through the canonical classifier and through "
        "mixed-corpus derivation, along both real detection paths. Alignment is "
        "observed, not declared."
    )
    lines.append("")
    lines.append("```text")
    for key in (
        "row_count",
        "aligned_count",
        "misaligned_count",
        "under_detection_count",
        "bridge_owned_under_detection_count",
        "upstream_owned_under_detection_count",
        "stale_upstream_gap_count",
        "over_claim_count",
        "bridge_intact",
    ):
        lines.append(f"{key:<40} {report.get(key)}")
    lines.append("```")
    lines.append("")
    lines.append("## No canonical name is shadowed")
    lines.append("")
    lines.append(
        "Each bridged module is parsed with `ast` and checked for a module-level "
        "rebinding of a name it imported from the canonical module. This is the "
        "defect Gate 105 removed."
    )
    lines.append("")
    lines.append("```text")
    for module_name in report.get("bridged_modules") or []:
        shadowed = (report.get("shadowed_canonical_names") or {}).get(module_name) or []
        lines.append(f"{module_name}")
        lines.append(f"    shadowed: {shadowed or 'none'}")
    lines.append("```")
    lines.append("")
    lines.append("## Under-detection this bridge does not own")
    lines.append("")
    gaps = report.get("known_upstream_gaps") or []
    if not gaps:
        lines.append("None registered.")
    else:
        lines.append(
            "Registered, verified against the upstream service at report time, "
            "and failed as stale the moment upstream stops explaining it."
        )
        lines.append("")
        lines.append("```text")
        for gap in gaps:
            lines.append(f"phrase: {gap.get('canonical_phrase')}")
            lines.append(f"    path:   {gap.get('detection_path')}")
            lines.append(f"    owner:  {gap.get('owner')}")
            lines.append(f"    reason: {gap.get('reason')}")
        lines.append("```")
    lines.append("")
    lines.append("## Boundaries")
    lines.append("")
    lines.append("```text")
    for key in (
        "fabricated_eligibility",
        "eligibility_determined",
        "live_source_collection",
        "source_monitoring_live",
        "source_coverage_claimed",
    ):
        lines.append(f"{key:<30} {report.get(key)}")
    lines.append("```")
    lines.append("")
    lines.append(
        "This guard measures classification. It determines no eligibility, "
        "collects from no source, and claims no coverage."
    )
    lines.append("")
    return "\n".join(lines)


def write_bridge_artifacts(*, repo_root: Any = None) -> dict[str, Any]:
    """Write the matrix and summary. Output root only - inspection is by import.

    `repo_root` chooses where files land. It deliberately does not influence what
    is inspected: `find_shadowed_canonical_names` resolves modules through the
    import system, so pointing this at a temp directory still measures the real
    tree rather than an empty one.
    """
    root = Path(repo_root) if repo_root else Path(__file__).resolve().parents[3]
    out_dir = root / ARTIFACT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    report = build_bridge_guard_report()
    written: dict[str, Any] = {}

    matrix_path = out_dir / "tribal_eligibility_classification_bridge_matrix.csv"
    matrix_path.write_text(render_bridge_matrix_csv(report), encoding="utf-8")
    written["matrix"] = str(matrix_path)

    summary_path = out_dir / "tribal_eligibility_classification_bridge_summary.md"
    summary_path.write_text(render_bridge_summary_md(report), encoding="utf-8")
    written["summary"] = str(summary_path)

    written["report"] = report
    return written
