# NativeForge Native-Relevant Grant Source Architecture

## Product doctrine

NativeForge is **Native-first, not Native-only**.

The platform prioritizes Native-specific and Native-relevant funding sources and opportunities. It must **not** reduce discovery to titles or descriptions containing words like “Native,” “Tribal,” or “Indigenous.” It must also surface broader opportunities—federal, state, local, philanthropic, corporate, and tribal consortium programs—where Native governments, Native-serving organizations, tribal colleges, Alaska Native or Native Hawaiian entities, or related applicants may be eligible, competitive, or strategically aligned.

**Doctrine statement (normative):**

NativeForge does not merely search for Native keywords. It evaluates opportunities for Native relevance, eligibility, competitiveness, geography, mission fit, source trust, operational burden, and sovereignty-adjacent considerations—then ranks and explains results transparently.

---

## Source lanes

### 1. Native-specific / tribal-focused lane

Programs explicitly designed for tribal governments, Native institutions, or Native communities (e.g., federal tribal offices, Indian Health Service pathways, tribal energy set-asides, tribal broadband carve-outs, Native-led philanthropic programs). These sources are expected to yield **high** Native relevance when ingest quality is sound.

### 2. Native-relevant broad lane

General competitions, formula programs, infrastructure, rural development, broadband, climate resilience, education, workforce, housing, public safety, language and culture, and similar domains where Native entities are often eligible or competitively positioned even when the solicitation is not “branded” as tribal-only.

### 3. General monitoring lane

Wide portals and catalogs (e.g., broad federal opportunity listings, state grant portals) used as **coverage backfill**. Opportunities from this lane **must** pass Native relevance assessment and typically require stronger eligibility evidence before being promoted broadly.

---

## Priority tiers

Sources are assigned **priority tiers** aligned with registry fields (e.g., `priority_level`, check cadence, and coverage goals):

| Tier | Intent |
|------|--------|
| **P0 — Sovereignty-critical** | Tribal-government-facing federal offices, tribal-specific NOFOs, major tribal consortium announcements |
| **P1 — Native institution / community** | IHS, tribal college pathways, Native-led funders, Native health/education intermediaries |
| **P2 — Broad but strategically recurring** | Grants.gov-wide federal scans, SAM.gov assistance listings, selected state portals |
| **P3 — Opportunistic / long-tail** | Corporate CSR, small foundations, regional prizes—high variance; intake discipline required |

Tiers drive **expected check frequency**, **review burden expectations**, and **operator attention**—not automatic suppression of lower tiers.

---

## What not to scrape yet (Sprint boundary)

Until connector policies, rate limits, robots compliance, legal review, and operator playbooks are in place:

- Do **not** implement live web scraping against third-party sites.
- Do **not** bypass authentication, paywalls, or terms of service.
- Do **not** automate submissions to grants portals.
- Do **not** ingest Grants.gov or other external APIs in production paths in this sprint.

Sprint 22 establishes **architecture, taxonomy, scoring rules, provenance contracts, and offline connector shells** only.

---

## Human review requirements

Certain signals **always** require human review before treating eligibility or Native relevance as authoritative:

- **Ambiguous eligibility** (unclear applicant classes, conflicting PDF vs. HTML language).
- **Keyword-only matches** without structured eligibility signals (see anti-keyword-only rule).
- **New or unverified sources** with low reliability ratings.
- **High-burden / high-risk** opportunities (extreme match ratios, unclear sovereign implications).

This aligns with the **operator review queue**, **resolution workflow**, and **HITP approval block** (below).

---

## Anti-keyword-only rule

**Keyword hits in titles or narrative alone are never sufficient** to conclude confirmed Native eligibility or “confirmed” Native relevance. Structured eligibility signals (e.g., explicit tribal eligibility, set-asides, documented applicant types, authoritative tags) are required to escalate confidence.

Scoring and UI copy must distinguish **“interesting because of language”** from **“actionable because of eligibility evidence.”**

---

## Trust and provenance

Every accepted candidate must trace to:

- A **source registry row** (publisher identity, scope, verification posture).
- **Captured artifacts** (URL, file hash, excerpt pointers—not necessarily full text in early phases).
- **Connector provenance metadata** (connector id, dry-run vs. live, timestamps, normalization version).

This connects directly to **discovery evidence / provenance packs**, audit logs, and operator tooling.

---

## Connection to existing Discovery systems

| System | Role |
|--------|------|
| **Source registry** | Canonical identity for each monitored publisher / endpoint |
| **Coverage catalog & gaps** | Ensures Native-specific and Native-relevant lanes are represented |
| **Source check scheduling & check-run workflow** | Executes periodic validation (even before live scraping—manual checks, dry runs) |
| **Freshness / health** | Detects stale publishers and broken ingestion assumptions |
| **Discovery intake runs** | Structured batches become normalized candidates and Grant Sparks |
| **Quality scoring & review queue** | Filters noise and escalates ambiguous cases |
| **Evidence packs** | Bundles citations for operator and tribal governance contexts |

---

## HITP approval block (Human-in-the-loop)

**HITP** gates prevent unreviewed automation from presenting low-trust or ambiguous Native relevance as fact:

1. **Connector promotion**: A connector moves from `dry_run` / shadow to **production-eligible** only after operator playbook sign-off (policy, robots, rate limits, privacy).
2. **Source elevation**: Raising a source priority tier or widening crawl scope requires explicit approval recorded in the **operator action ledger**.
3. **“Confirmed” relevance**: Product-facing “confirmed Native relevance” language requires structured eligibility signals per scoring doctrine—not keywords alone.

Until these gates pass, downstream UX should use **tentative** language and surface **review_required** reasons.

---

## Summary

NativeForge’s grant sourcing architecture intentionally separates **lanes**, **priority**, **scoring**, **review**, and **provenance** so that future connectors (Sprint 23+) plug into the **existing** discovery engine safely—without reducing tribal communities’ funding intelligence to a keyword search.
