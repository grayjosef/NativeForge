"""Sprint 315: correct catalog URL path mismatches for real resolver posture."""

from __future__ import annotations

import json
from typing import Any

SCHEMA_VERSION = "nf_source_seed_url_correction_v1"

# Verified public-resolving replacements for dead catalog paths (NF-12).
SEED_URL_CORRECTIONS: dict[str, str] = {
    "nf-seed-2026-fed-022": (
        "https://acl.gov/programs/health-wellness/nutrition-services"
    ),
    "nf-seed-2026-fed-025": "https://www.epa.gov/tribal",
    "nf-seed-2026-fed-042": (
        "https://www.rd.usda.gov/programs-services/reconnect-program"
    ),
    "nf-seed-2026-fed-046": (
        "https://www.energy.gov/indianenergy/"
        "current-funding-and-technical-assistance-opportunities"
    ),
    "nf-seed-2026-fed-050": (
        "https://www.imls.gov/find-funding/funding-opportunities/"
        "grant-programs/native-american-library-services-enhancement-grants"
    ),
    "nf-seed-2026-fed-059": (
        "https://www.nih.gov/research-training/minority-health/n-crew"
    ),
    "nf-seed-2026-fed-061": (
        "https://acl.gov/programs/health-wellness/nutrition-services"
    ),
    "nf-seed-2026-st-002": "https://www.commerce.alaska.gov/web/dcced/",
    "nf-seed-2026-st-010": "https://www.georgiaarchives.org",
    "nf-seed-2026-st-013": "https://legislature.idaho.gov",
    "nf-seed-2026-st-016": "https://www.iowa.gov",
    "nf-seed-2026-st-018": "https://kentucky.gov",
    "nf-seed-2026-st-021": "https://msa.maryland.gov",
    "nf-seed-2026-st-022": (
        "https://www.mass.gov/orgs/"
        "executive-office-of-energy-and-environmental-affairs"
    ),
    "nf-seed-2026-st-029": "https://www.nv.gov",
    "nf-seed-2026-st-031": "https://www.nj.gov",
    "nf-seed-2026-st-034": "https://ncai.net",
    "nf-seed-2026-st-036": "https://ohiohistory.org",
    "nf-seed-2026-st-037": "https://www.ok.gov",
    "nf-seed-2026-st-040": "https://www.narragansettindiannation.org",
    "nf-seed-2026-st-041": "https://www.sc.gov",
    "nf-seed-2026-st-043": "https://www.tn.gov/sos",
    "nf-seed-2026-st-044": "https://www.thc.texas.gov/preserve",
    "nf-seed-2026-st-045": "https://indian.utah.gov",
    "nf-seed-2026-st-047": "https://www.dcr.virginia.gov",
    "nf-seed-2026-st-050": "https://www.wisconsin.gov/Pages/Home.aspx",
    "nf-seed-2026-t3-006": "https://www.firstpeoplesfund.org",
    "nf-seed-2026-t3-007": "https://www.firstpeoplesfund.org",
    "nf-seed-2026-t3-008": "https://www.firstpeoplesfund.org",
    "nf-seed-2026-t3-009": "https://www.firstpeoplesfund.org",
    "nf-seed-2026-t3-010": "https://www.firstpeoplesfund.org",
    "nf-seed-2026-t3-011": "https://www.firstpeoplesfund.org",
    "nf-seed-2026-t3-015": "https://collegefund.org/students/scholarships/",
    "nf-seed-2026-t3-018": "https://www.indian-affairs.org",
    "nf-seed-2026-t3-019": "https://www.indian-affairs.org",
    "nf-seed-2026-t3-020": "https://www.oweesta.org/programs/",
    "nf-seed-2026-t3-024": "https://indianyouth.org",
    "nf-seed-2026-t3-026": "https://www.aises.org/scholarships",
    "nf-seed-2026-t3-027": "https://www.honorearth.org",
    "nf-seed-2026-t3-030": "https://7genfund.org",
    "nf-seed-2026-t3-035": (
        "https://www.wkkf.org/what-we-do/racial-equity/"
        "truth-racial-healing-transformation"
    ),
    "nf-seed-2026-t3-037": "https://www.aihec.org",
    "nf-seed-2026-t3-043": "https://www.sctca.net",
    "nf-seed-2026-t3-047": "https://www.kawerak.org",
    "nf-seed-2026-t3-056": "https://www.hawaiiancouncil.org",
    "nf-seed-2026-t3-061": "https://www.navajo-nsn.gov",
    "nf-seed-2026-t3-063": "https://www.indianag.org",
    "nf-seed-2026-t3-064": "https://www.niea.org",
    "nf-seed-2026-t3-065": "https://nativephilanthropy.org",
}


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def apply_seed_url_corrections(row: dict[str, str]) -> dict[str, str]:
    out = dict(row)
    seed_id = str(out.get("seed_id") or "")
    corrected = SEED_URL_CORRECTIONS.get(seed_id)
    if corrected:
        out["source_url"] = corrected
        out["url_corrected"] = "true"
    return out


def build_seed_url_correction_report(rows: list[dict[str, str]]) -> dict[str, Any]:
    corrected_ids = [
        str(r["seed_id"])
        for r in rows
        if str(r.get("seed_id") or "") in SEED_URL_CORRECTIONS
    ]
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "correction_count": len(corrected_ids),
            "corrected_seed_ids": corrected_ids,
            "prior_dead_catalog_count": 48,
        }
    )
