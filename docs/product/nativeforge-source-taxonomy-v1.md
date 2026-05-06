# NativeForge Source Taxonomy v1

Version: `nativeforge-source-taxonomy-v1`

This taxonomy classifies monitoring targets for Native-relevant grant sourcing. Each category row is conceptual; registry rows carry concrete endpoints and schedules.

---

## Lane definitions

| Lane | Meaning |
|------|---------|
| `native_specific` | Publisher or program family primarily serving tribal governments or Native institutions |
| `native_relevant_broad` | General solicitations where Native entities are commonly eligible or competitive |
| `general_monitoring` | Wide catalogs requiring filtering through Native relevance scoring |

---

## Categories

### A. Native-specific / tribal-focused

Examples (illustrative): BIA; IHS; ANA; CTAS / DOJ tribal programs; DOE Office of Indian Energy; HUD ONAP; EPA tribal programs; NTIA tribal broadband; USDA tribal / rural-tribal pathways; tribal consortia; Native-serving philanthropy; Native-led foundations.

| source_type | source_lane | priority | expected check frequency | Native relevance signals | eligibility signals | review burden | connector approach |
|-------------|-------------|----------|--------------------------|--------------------------|---------------------|---------------|-------------------|
| `federal_tribal_office` | native_specific | P0 | daily–weekly | agency mandate; tribal set-aside language; historic tribal portfolio | explicit tribal applicant classes | low–medium | `api_connector` or `html_page_monitor` (future) |
| `tribal_consortium` | native_specific | P0 | weekly–monthly | tribal membership services; intertribal charter | consortium membership rules | medium | `rss_feed`, `html_page_monitor` |
| `native_philanthropy` | native_specific | P1 | monthly–quarterly | mission statements; grantee portfolios | 501(c) eligibility; geography | medium–high | `foundation_page_monitor`, `manual_upload` |

### B. Broad but Native-relevant

Examples: Grants.gov federal breadth; SAM.gov assistance listings; Federal Register notices; state portals; local government grants; broadband/digital equity; rural development; infrastructure; climate resilience; health access; education/workforce; housing; public safety; language/culture where eligible; university/foundation/corporate programs.

| source_type | source_lane | priority | expected check frequency | Native relevance signals | eligibility signals | review burden | connector approach |
|-------------|-------------|----------|--------------------------|--------------------------|---------------------|---------------|-------------------|
| `federal_wide_catalog` | native_relevant_broad | P2 | daily–weekly | tribal eligibility flags; applicant-type tables; rural/underserved geography | structured applicant classes | medium | `api_connector` (future), `downloaded_csv`, `manual_upload` |
| `state_portal` | native_relevant_broad | P2 | weekly | region + domain fit vs. org profile | state entity-type vocabularies | medium–high | `state_portal_monitor` |
| `foundation_general` | native_relevant_broad | P2–P3 | monthly | program areas aligned to Native priorities | IRS determination; geography | high | `foundation_page_monitor` |
| `university_sponsored` | native_relevant_broad | P3 | monthly | tribal partnerships; Indigenous research priorities | institutional eligibility | high | `html_page_monitor`, `manual_upload` |

### C. General monitoring

| source_type | source_lane | priority | expected check frequency | Native relevance signals | eligibility signals | review burden | connector approach |
|-------------|-------------|----------|--------------------------|--------------------------|---------------------|---------------|-------------------|
| `corporate_csr` | general_monitoring | P3 | quarterly | thematic alignment | eligibility narratives | high | `html_page_monitor` |
| `regional_collaborative` | general_monitoring | P3 | quarterly | place-based fit | membership / geography | high | `rss_feed`, `manual_upload` |

---

## Cross-cutting fields

For every registry entry, operators should capture:

- **`source_type`**: taxonomy key (tables above + extensible enums in code).
- **`source_lane`**: `native_specific` \| `native_relevant_broad` \| `general_monitoring`.
- **`priority`**: P0–P3 (maps to product tiers and registry priority levels).
- **`expected check frequency`**: drives `check_interval_days` and overdue intelligence.
- **`Native relevance signals`**: what the connector should extract or preserve for scoring.
- **`eligibility signals`**: structured paths that feed eligibility confidence.
- **`review burden`**: expected operator time—feeds capacity planning.
- **`connector approach`**: planned mechanism (`api_connector`, `rss_feed`, etc.)—**Sprint 22 defines interfaces only**.

---

## Sprint boundary

No live connectors are activated in Sprint 22. Taxonomy rows inform documentation, scoring tests, and offline fixture connectors only.
