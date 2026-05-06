# Five Pillars

Every NativeForge feature lands on exactly one of these. If a proposed feature does not, it is not in scope yet.

## 1. Sovereignty-first profile

The reusable organization profile. The most important data structure in the product. It powers eligibility, autofill, scoring, drafting, resolution tracking, and compliance.

**M0 scope:** legal identity (UEI, EIN, SAM status, entity type, federally recognized status, congressional district, addresses), authorized officials (AOR, alternate, grants manager, finance officer), financial (indirect cost rate, type, period, de minimis election), certifications (SF-424B assurances, SF-LLL, civil rights, drug-free workplace, debarment), and reusable narratives (org overview, governance, staffing capacity, past performance, community profile).

**Reference:** `domain/entity-profile-schema.md`

## 2. Grant Spark ingestion

A grant version of the ContractForge Spark. Each ingested opportunity becomes a Spark with structured metadata, raw NOFO text, and a tribal-relevance flag.

**M0 scope:** seeded ingestion only (12 demo Sparks). Live Grants.gov polling is M1. Native-specific agency ingestion (BIA, IHS, ANA, CTAS, DOE Indian Energy, HUD ONAP, EPA, USDA, NTIA) is M1.

**Reference:** `domain/grant-sources.md`

## 3. Requirement extraction

Every NOFO becomes a structured object: required forms, attachments, narrative sections, page limits, formatting rules, eligibility rules, match requirements, evaluation criteria, scoring weights, deadlines, reporting requirements, risk flags. The product's brain.

**M0 scope:** LLM extraction with confidence scoring; low-confidence fields flagged for human review. Hand-verified on the 12 demo Sparks before seeding.

**Reference:** `domain/nofo-extraction-schema.md`

## 4. Pursuit scoring

Six dimensions: eligibility confidence, mission alignment, capacity fit, funding value, reporting burden, win likelihood. Weighted composite. Recommendation tier (Strong Pursue / Pursue / Pursue with Conditions / Needs Review / Do Not Pursue / Disqualified).

**Critical rule:** scoring is deterministic. The LLM extracts facts and may rephrase explanations, but it does not produce the score and it does not reinterpret the score. Same inputs always produce the same output.

**M0 scope:** all six dimensions, full recommendation tier logic, templated explanation.

**Reference:** `domain/scoring-model.md`

## 5. Human-reviewed AI drafting

AI assists with outlines, summaries, drafts. Every AI output is badged. Every "final" state requires server-enforced human review.

**M0 scope:** AI NOFO summary, AI outline generation, SF-424 autofill (autofill is "drafting" in this context). Full narrative drafting with cultural guardrails is M1.

**Reference:** `domain/drafting-guardrails.md`

## What this list deliberately omits

- Post-award compliance. Critical for the full product, not a pillar of M0.
- Multi-tenant consortium licensing. M3.
- Private deployment. M3.
- Finance integrations. M3.

These are real, but they are not what the product is for at the wedge stage. Conflating them with the wedge dilutes the demo.
