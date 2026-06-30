#!/usr/bin/env python3
"""SH-0: seed catalog hygiene report — collisions, reconciliation, identity audit."""

from __future__ import annotations

import csv
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_SRC = ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from nativeforge.services.seed_catalog_health_service import (  # noqa: E402
    build_catalog_reconciliation_report,
)
from nativeforge.services.source_ingestion_seed_loader_service import (  # noqa: E402
    build_source_seed_candidate_bundle,
)
from nativeforge.services.source_ingestion_seed_schema_service import (  # noqa: E402
    seed_csv_path,
)

ALN_RE = re.compile(r"(\d{2}\.\d{3})")


def _program_key(name: str) -> str:
    aln = ALN_RE.search(name or "")
    if aln:
        return f"aln:{aln.group(1)}"
    if "—" in name:
        a, p = name.split("—", 1)
        return f"name:{a.strip()}|{p.strip()}"
    return f"name:{name.strip()}"


def build_collision_report() -> dict:
    rows = list(csv.DictReader(seed_csv_path().open(encoding="utf-8")))
    by_url: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        by_url[row["source_url"]].append(row)

    true_dup = 0
    shared_resolver = 0
    shared_groups: list[dict] = []
    for url, group in by_url.items():
        if len(group) < 2:
            continue
        keys = {_program_key(r["source_name"]) for r in group}
        if len(keys) == 1:
            true_dup += 1
        else:
            shared_resolver += 1
            shared_groups.append(
                {
                    "url": url,
                    "seed_count": len(group),
                    "distinct_programs": len(keys),
                    "seed_ids": [r["seed_id"] for r in group],
                }
            )

    return {
        "total_rows": len(rows),
        "unique_urls": len(by_url),
        "collision_url_groups": sum(1 for g in by_url.values() if len(g) > 1),
        "true_duplicate_url_groups": true_dup,
        "shared_resolver_url_groups": shared_resolver,
        "shared_resolver_samples": sorted(
            shared_groups, key=lambda g: -g["seed_count"]
        )[:8],
        "identity_key_bug": {
            "wrong_key": "source_url",
            "correct_key": "seed_id",
            "secondary_key": "canonical_source_id",
            "locations": [
                "source_ingestion_orchestrator_service.py:persist_seed_candidates_to_registry",
                "tier1_batch_federal_activation_service.py:activate_tier1_public_batch_human_gate",
                "seed_source_human_activation_service.py:activate_single_seed_source_human_gate",
                "tier1_batch_live_fetch_service.py:update_source_freshness_after_batch",
            ],
            "fix_status": "seed_id re-key in SH-2",
        },
    }


def main() -> int:
    bundle = build_source_seed_candidate_bundle()
    recon = build_catalog_reconciliation_report(bundle["candidates"])
    activatable = recon["headline"]["activatable_now"]
    report = {
        "schema_version": "nf_seed_catalog_hygiene_report_v1",
        "collisions": build_collision_report(),
        "reconciliation": recon,
        "headline": (
            f"177 catalog programs; activatable count is {activatable} (not 177)"
        ),
    }
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
