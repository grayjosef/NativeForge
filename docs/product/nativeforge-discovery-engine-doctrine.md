# NativeForge Discovery Engine Doctrine

## 1. Executive thesis

Discovery is a core moat for NativeForge. Without systematic, trustworthy discovery of funding opportunities, the product remains a downstream workflow tool for leads users already found elsewhere. That ceiling is unacceptable for Native communities that depend on timely access to capital.

NativeForge must **not** rely only on Grants.gov or other government feeds. Federal portals are necessary inputs, but they are neither sufficient nor representative of the full funding landscape relevant to Native nations, tribal enterprises, Native-led nonprofits, and Native entrepreneurs.

Native organizations should not have to hunt across hundreds of scattered websites, PDF bulletins, foundation portals, corporate CSR programs, and tribal consortium announcements to assemble a complete picture of what they might qualify for.

The **long-term goal** is for NativeForge to host the most comprehensive **Native-relevant opportunity intelligence database** possible: a living corpus of opportunities—properly attributed, deduplicated, freshness-monitored, and matched to organizations—with trust built through verification, auditability, and transparent sourcing.

---

## 2. Source universe

Funding and grant opportunities can originate from **any** channel. The discovery engine must assume a broad **source universe**, including at minimum:

| Category | Examples (non-exhaustive) |
|----------|---------------------------|
| **Federal agencies** | Departments, bureaus, cross-agency initiatives, congressionally directed programs published on agency sites |
| **State agencies** | Economic development, housing, education, natural resources, broadband, workforce |
| **Local governments** | Counties, municipalities, joint powers authorities, economic development corporations |
| **Tribal entities and consortia** | Tribal nations, intertribal organizations, regional tribal associations, tribal colleges’ sponsored programs |
| **Foundations** | Private family foundations, community foundations, Native-focused funders |
| **Nonprofits** | Fiscal sponsors, intermediaries, capacity-building networks distributing subgrants or partner opportunities |
| **Universities** | Research offices, extension, tribal partnerships, sponsored programs and RFAs |
| **Corporations** | CSR, supplier diversity, community grants, innovation challenges |
| **Regional funders** | Place-based collaboratives, rural development intermediaries |
| **Philanthropic networks** | Funder collaboratives, pooled funds, affinity groups |
| **Private programs** | Accelerators, prizes, fellowships, debt/equity adjacent vehicles framed as opportunities |
| **Other nontraditional sources** | Industry associations, cooperatives, crowdsourced or community-posted leads (with verification discipline) |

This list defines **intent**, not a one-time checklist: the product must continuously expand what “counts” as a source while maintaining quality and trust.

---

## 3. Product engine pillars

NativeForge is architected as a set of engines that together turn raw possibility into confident pursuit:

1. **Discovery Engine** — systematically finds, ingests, normalizes, and continuously refreshes opportunities from the full source universe; tracks coverage, freshness, and amendments.
2. **Qualification Engine** — maps opportunities to eligibility dimensions (entity type, geography, mission, capacity, funding rules) and surfaces fit vs. friction for each organization.
3. **Pursuit Engine** — turns qualified opportunities into actionable work: briefs, timelines, collaboration, and submission orchestration (aligned with existing pursuit workflows).
4. **Reuse Engine** — captures narrative, evidence, budgets, and boilerplate so organizations compound effort across cycles and programs instead of restarting from zero.
5. **Trust Engine** — verification, provenance, review workflows, scoring transparency, and audit trails so users can rely on NativeForge when stakes are high.

Discovery is the **front door**; the other engines multiply its value. Without discovery depth, qualification and pursuit lack fuel; without trust, discovery scale creates noise instead of signal.

---

## 4. Discovery Engine future capabilities

The Discovery Engine will grow beyond “import a feed” into a full **opportunity intelligence pipeline**:

- **Source registry** — canonical catalog of sources, endpoints, formats, ownership, and ingestion contracts.
- **Source coverage tracking** — which domains, programs, and opportunity types are represented vs. gaps.
- **Ingestion pipeline** — scheduled crawls, API pulls, file drops, partner feeds, and human-curated intake with consistent normalization.
- **Source freshness monitoring** — detect stale sources, broken endpoints, or silent publishers.
- **Deadline monitoring** — rolling deadlines, amendments, extensions, and closing windows with alerting semantics.
- **Deduplication** — identify the same logical opportunity across publishers (government mirror sites, PDF vs. HTML, re-announcements).
- **Native relevance tagging** — structured signals for why an opportunity matters for Native communities (not just keyword matches).
- **Eligibility taxonomy** — shared vocabulary for who and what qualifies, spanning federal, philanthropic, and corporate idioms.
- **Organization–opportunity matching** — configurable fit rules tied to org profiles and priorities.
- **Opportunity quality scoring** — composite signals (clarity of criteria, award size predictability, burden, historical noise).
- **Verification / review status** — human or automated gates before opportunities surface broadly.
- **Audit trail** — immutable history of what changed, when, and from which ingested artifact.
- **Source attribution** — every surfaced opportunity traces to authoritative URLs, documents, or partner attestations.
- **Update / amendment tracking** — diff-aware tracking when solicitations change post-publication.

---

## 5. Future data model implications

Engineering the Discovery Engine will imply **first-class data** beyond a simple “opportunity row.” Conceptual extensions include:

- **Opportunity source registry** — stable IDs for publishers and ingestion endpoints linked to opportunities.
- **Source type taxonomy** — federal vs. foundation vs. tribal vs. corporate, etc., with room for hybrid sources.
- **Source confidence / reliability** — qualitative and quantitative measures of publisher consistency and ingestion quality.
- **Opportunity freshness** — last verified ingest, last publisher update detected, staleness flags.
- **Duplicate clusters** — graph or cluster IDs linking multiple records to one logical funding action.
- **Native relevance reasons** — structured explanations (e.g., tribal eligibility, Native-serving priority, Indian Country geography, cultural heritage alignment).
- **Eligibility criteria** — normalized predicates with provenance to source text.
- **Geographic scope** — tribal lands, states, regions, national, international where relevant.
- **Deadline type** — single date, rolling, multi-stage, anticipated vs. firm, amendment-driven changes.
- **Funding type** — grant, cooperative agreement, loan, guarantee, prize, contract-like RFP, in-kind, blended.
- **Verification status** — draft, ingested-only, reviewed, disputed, deprecated.

These implications are **directional**: schema design should emerge from shipped increments, but the doctrine anchors **why** these entities exist.

---

## 6. Proposed Sprint 10 direction

**Sprint 10: NativeForge Opportunity Discovery Engine**

Sprint 10 is reserved for implementing the Discovery Engine as a product increment—registry, ingestion strategy, trust primitives, and user-visible intelligence—consistent with this doctrine.

**This document is planning only.** It does not prescribe Sprint 10 tickets, schema migrations, or API contracts. Implementation choices belong in sprint planning, technical design, and incremental delivery after explicit prioritization.

---

## 7. Product principle

**A Native organization should be able to trust NativeForge as the place to go so they do not miss relevant funding opportunities.**

Trust implies breadth **and** precision: comprehensive sourcing without drowning users in junk; Native relevance that respects sovereignty and diversity of Native contexts; and transparency when uncertainty remains.

---

*Doctrine version: aligned with repo head `0e24337` (feat: add NativeForge pursuit brief engine). Planning artifact—subject to revision as the product learns from users and data.*
