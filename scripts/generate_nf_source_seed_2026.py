#!/usr/bin/env python3
"""Generate fixtures/source_ingestion/NF_SOURCE_SEED_2026.csv (177 sources)."""

from __future__ import annotations

import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "fixtures" / "source_ingestion" / "NF_SOURCE_SEED_2026.csv"

FEDERAL_PROGRAMS: tuple[tuple[str, str, str], ...] = (
    ("BIA Road Maintenance", "bia.gov", "grants_gov_federal"),
    ("IHS Health Infrastructure", "ihs.gov", "grants_gov_federal"),
    ("HUD ONAP IHBG", "hud.gov", "grants_gov_federal"),
    ("EPA Tribal General Assistance", "epa.gov", "grants_gov_federal"),
    ("DOE Office of Indian Energy", "energy.gov", "grants_gov_federal"),
    ("Administration for Native Americans", "acf.hhs.gov", "grants_gov_federal"),
    ("DOJ Coordinated Tribal Assistance", "justice.gov", "grants_gov_federal"),
    ("USDA Rural Development Tribal", "rd.usda.gov", "grants_gov_federal"),
    ("FEMA Tribal Mitigation", "fema.gov", "grants_gov_federal"),
    ("NIH Native American Research", "nih.gov", "grants_gov_federal"),
    ("NEH Native Language Preservation", "neh.gov", "grants_gov_federal"),
    ("IMLS Native American Library Services", "imls.gov", "grants_gov_federal"),
    ("EDA Public Works Tribal", "eda.gov", "grants_gov_federal"),
    ("DOT Tribal Transportation", "transportation.gov", "grants_gov_federal"),
    ("CDC Tribal Public Health", "cdc.gov", "grants_gov_federal"),
    ("SAMHSA Tribal Behavioral Health", "samhsa.gov", "grants_gov_federal"),
    ("HRSA Tribal Health Professions", "hrsa.gov", "grants_gov_federal"),
    ("NSF Tribal Colleges STEM", "nsf.gov", "grants_gov_federal"),
    ("USFWS Tribal Wildlife Grants", "fws.gov", "grants_gov_federal"),
    ("NPS Tribal Heritage Grants", "nps.gov", "grants_gov_federal"),
    ("BLM Tribal Forest Management", "blm.gov", "grants_gov_federal"),
    ("NRCS Tribal Conservation", "nrcs.usda.gov", "grants_gov_federal"),
    ("Forest Service Tribal Relations", "fs.usda.gov", "grants_gov_federal"),
    ("NOAA Tribal Coastal Resilience", "noaa.gov", "grants_gov_federal"),
    ("DOL Native American Employment", "dol.gov", "grants_gov_federal"),
    ("Treasury CDFI Native Initiatives", "treasury.gov", "grants_gov_federal"),
    ("VA Tribal Veterans Outreach", "va.gov", "grants_gov_federal"),
    ("CNCS AmeriCorps Tribal", "americorps.gov", "grants_gov_federal"),
    ("Grants.gov Tribal Set-Aside Search", "grants.gov", "grants_gov_federal"),
    ("Simpler.Grants.gov Tribal Catalog", "simpler.grants.gov", "simpler_grants_gov"),
    ("GrantSolutions Federal Programs", "grantsolutions.gov", "grant_solutions"),
)

STATE_PORTALS: tuple[tuple[str, str, str, str], ...] = (
    ("CA", "California Grants Portal", "grants.ca.gov", "state_portal_ca"),
    ("CA", "California Tribal Affairs Funding", "tribalaffairs.ca.gov", "state_portal_ca"),
    ("CA", "California Energy Commission Tribal", "energy.ca.gov", "state_portal_ca"),
    ("HI", "OHA Native Hawaiian Programs", "oha.org", "state_portal_hi_oha"),
    ("HI", "DHHL Native Hawaiian Housing", "dhhl.hawaii.gov", "state_portal_hi_dhhl"),
    ("HI", "Hawaii DOH Native Health", "health.hawaii.gov", "state_portal_hi"),
    ("MN", "Minnesota Tribal State Relations Grants", "mn.gov", "state_portal_mn"),
    ("MN", "Minnesota Department of Health Tribal", "health.state.mn.us", "state_portal_mn"),
    ("MN", "Minnesota Housing Tribal", "mhfa.state.mn.us", "state_portal_mn"),
    ("NM", "New Mexico Indian Affairs", "indianaffairs.state.nm.us", "state_portal_nm"),
    ("NM", "New Mexico Finance Authority Tribal", "nmfa.net", "state_portal_nm"),
    ("NM", "New Mexico Aging Tribal", "aging.nm.gov", "state_portal_nm"),
    ("AZ", "Arizona Commission Tribal Relations", "aztribal.gov", "state_portal_az"),
    ("AZ", "Arizona Commerce Authority Tribal", "azcommerce.com", "state_portal_az"),
    ("AZ", "Arizona DES Tribal Programs", "des.az.gov", "state_portal_az"),
    ("WA", "Washington OFM Tribal Grants", "ofm.wa.gov", "state_portal_wa"),
    ("WA", "Washington Commerce Tribal", "commerce.wa.gov", "state_portal_wa"),
    ("WA", "Washington Ecology Tribal", "ecology.wa.gov", "state_portal_wa"),
    ("OR", "Oregon Tribal Relations", "oregon.gov", "state_portal_or"),
    ("OR", "Oregon Housing Tribal", "oregon.gov/ohcs", "state_portal_or"),
    ("MT", "Montana Tribal Economic Development", "commerce.mt.gov", "state_portal_mt"),
    ("MT", "Montana DNRC Tribal", "dnrc.mt.gov", "state_portal_mt"),
    ("AK", "Alaska Native Programs", "alaska.gov", "state_portal_ak"),
    ("AK", "Alaska DHSS Tribal Health", "health.alaska.gov", "state_portal_ak"),
    ("OK", "Oklahoma Native American Affairs", "oklahoma.gov", "state_portal_ok"),
    ("OK", "Oklahoma Commerce Tribal", "okcommerce.gov", "state_portal_ok"),
    ("ND", "North Dakota Indian Affairs", "nd.gov", "state_portal_nd"),
    ("ND", "North Dakota Housing Tribal", "ndhousing.gov", "state_portal_nd"),
    ("SD", "South Dakota Tribal Relations", "sd.gov", "state_portal_sd"),
    ("SD", "South Dakota Housing Tribal", "sdhda.org", "state_portal_sd"),
    ("WI", "Wisconsin Tribal Affairs", "wisconsin.gov", "state_portal_wi"),
    ("WI", "Wisconsin DOA Tribal", "doa.wi.gov", "state_portal_wi"),
    ("NV", "Nevada Indian Commission", "nic.nv.gov", "state_portal_nv"),
    ("NV", "Nevada Housing Tribal", "nvruralhousing.org", "state_portal_nv"),
)

FOUNDATION_ORGS: tuple[tuple[str, str, str, str], ...] = (
    ("NAP Member Directory", "nativephilanthropy.org", "foundation_org_page", "public"),
    ("AIHEC Member Colleges", "aihec.org", "foundation_org_page", "public"),
    ("Native Ways Federation Members", "nativewaysfederation.org", "foundation_org_page", "members"),
    ("First Nations Development Institute", "firstnations.org", "foundation_org_page", "public"),
    ("American Indian College Fund", "collegefund.org", "foundation_org_page", "public"),
    ("Native American Agriculture Fund", "nativeamericanagriculturefund.org", "foundation_org_page", "public"),
    ("Native American Rights Fund", "narf.org", "foundation_org_page", "public"),
    ("National Indian Health Board", "nihb.org", "foundation_org_page", "members"),
    ("National Congress of American Indians", "ncai.org", "foundation_org_page", "members"),
    ("Partnership With Native Americans", "nativepartnership.org", "foundation_org_page", "public"),
)


def _expand_federal() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    idx = 0
    for name, domain, adapter in FEDERAL_PROGRAMS:
        for variant in range(2):
            idx += 1
            slug = f"nf-seed-2026-fed-{idx:03d}"
            rows.append(
                {
                    "seed_id": slug,
                    "canonical_source_id": f"nf:source:{slug}",
                    "source_name": f"{name} Program {variant + 1}",
                    "source_url": f"https://www.{domain}/grants/tribal-program-{idx}",
                    "tier": "1",
                    "adapter_key": adapter,
                    "source_type": "federal",
                    "publisher_name": name.split()[0],
                    "state_code": "",
                    "access_posture_hint": "public",
                    "program_family": "federal_native_relevant",
                    "native_relevance_notes": "Federal program with tribal eligibility pathway",
                }
            )
            if len(rows) >= 61:
                return rows[:61]
    return rows[:61]


def _expand_state() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for i, (st, name, domain, adapter) in enumerate(STATE_PORTALS):
        slug = f"nf-seed-2026-st-{i + 1:03d}"
        rows.append(
            {
                "seed_id": slug,
                "canonical_source_id": f"nf:source:{slug}",
                "source_name": name,
                "source_url": f"https://{domain}/grants",
                "tier": "2",
                "adapter_key": adapter,
                "source_type": "state",
                "publisher_name": f"{st} State",
                "state_code": st,
                "access_posture_hint": "public",
                "program_family": "state_direct_grant",
                "native_relevance_notes": "State portal with tribal or Native-serving programs",
            }
        )
    # pad to 52 state-tier rows
    while len(rows) < 52:
        n = len(rows) + 1
        rows.append(
            {
                "seed_id": f"nf-seed-2026-st-{n:03d}",
                "canonical_source_id": f"nf:source:nf-seed-2026-st-{n:03d}",
                "source_name": f"State Tribal Grants Portal {n}",
                "source_url": f"https://example-state-{n}.gov/grants/tribal",
                "tier": "2",
                "adapter_key": "state_portal_generic",
                "source_type": "state",
                "publisher_name": "Illustrative State Agency",
                "state_code": "XX",
                "access_posture_hint": "public",
                "program_family": "state_direct_grant",
                "native_relevance_notes": "Illustrative state tribal grants listing",
            }
        )
    return rows[:52]


def _expand_tier3(start_idx: int) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for i, (name, domain, adapter, posture) in enumerate(FOUNDATION_ORGS):
        slug = f"nf-seed-2026-t3-{i + 1:03d}"
        rows.append(
            {
                "seed_id": slug,
                "canonical_source_id": f"nf:source:{slug}",
                "source_name": name,
                "source_url": f"https://{domain}/grants",
                "tier": "3",
                "adapter_key": adapter,
                "source_type": "foundation",
                "publisher_name": name,
                "state_code": "",
                "access_posture_hint": posture,
                "program_family": "foundation_org_page",
                "native_relevance_notes": "Native-serving foundation or directory org page",
            }
        )
    while len(rows) < 64:
        n = start_idx + len(rows)
        rows.append(
            {
                "seed_id": f"nf-seed-2026-t3-{len(rows) + 1:03d}",
                "canonical_source_id": f"nf:source:nf-seed-2026-t3-{len(rows) + 1:03d}",
                "source_name": f"Native-Serving Foundation Grants {n}",
                "source_url": f"https://foundation-example-{n}.org/grants",
                "tier": "3",
                "adapter_key": "foundation_org_page",
                "source_type": "foundation",
                "publisher_name": f"Illustrative Foundation {n}",
                "state_code": "",
                "access_posture_hint": "public" if n % 3 else "login",
                "program_family": "foundation_org_page",
                "native_relevance_notes": "Foundation grants page for Native-serving organizations",
            }
        )
    return rows[:64]


def main() -> None:
    fieldnames = [
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
    ]
    rows = _expand_federal() + _expand_state() + _expand_tier3(113)
    assert len(rows) == 177, f"expected 177 rows, got {len(rows)}"
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {len(rows)} rows to {OUT}")


if __name__ == "__main__":
    main()
