# Pricing and Tiers

Distilled from `source/nativeforge-revenue-model.md`. M0 ships none of these as billable products. They define the build envelope so M0 doesn't paint the architecture into a corner.

## The five tiers

| Tier | License (one-time) | Annual Maintenance | Implementation | Target |
|---|---|---|---|---|
| **Core** | $12,000 | $2,400/yr (20%) | Optional: $4,500 | Small tribe, tribal nonprofit, village corp; 1–5 grants/yr |
| **Pro** | $24,000 | $4,200/yr (17.5%) | Standard: $7,500 | Mid-size tribe or tribal org; 5–20 grants/yr |
| **Enterprise** | $45,000 | $7,800/yr (17.3%) | Required: $12K–$18K | Large tribe, consortium, $5M+ grant portfolio |
| **Sovereignty / Private** | $65,000 | $13,500/yr | Required: $20K–$30K | Org requiring private/dedicated cloud deployment |
| **Consortium** (up to 8 tribes) | $75,000 | $15,000/yr | Required: $18K–$25K | TTA program, intertribal consortium, regional body |

The Pro tier is the workhorse. All tiers stay below the $250,000 federal procurement threshold so they qualify as simplified-acquisition (3 quotes, no full RFP).

## Build implications (the only reason this file is in `domain/`)

### From the **Sovereignty** tier

A real customer will pay $65,000 + $13,500/yr to deploy NativeForge on infrastructure they control. M3 must support this without a rewrite. M0 decisions that block private deployment are blockers, not preferences.

What this means in practice:

- Every external dependency (LLM provider, NOFO ingestion, SAM.gov API, file storage) must be configurable per deployment, not hard-coded to one vendor's endpoint.
- Tenant isolation works the same in a single-deploy SaaS instance and a single-customer private deploy.
- No M0 feature relies on a multi-tenant assumption (e.g., cross-tenant analytics) that wouldn't make sense in a single-tenant private deploy.
- Secrets management must work in both cloud and air-gapped contexts (or fail loudly so private-deploy customers can substitute their own).

### From the **Consortium** tier

A real customer will pay $75,000 + $15,000/yr where one paying organization manages NativeForge for up to 8 member tribes. M3 must support this. M0 ships one-to-one (org → tribal profile) for simplicity, but the data model should not preclude future consortium support.

What this means in practice:

- `nf_tribal_profiles.organization_id` is one-to-one in M0. Make sure that's not enforced as a UNIQUE constraint at the DB level if it's easy to leave open. If it must be UNIQUE for M0 correctness, document the migration path to drop the constraint in M3.
- Multi-tribe billing, support roll-up, and consortium-admin roles are M3, not M0.
- Audit log scoping should anticipate that "org" and "tribe" might become distinct concepts later. M0 conflates them; M3 separates them.

### From the **license vs. SaaS** distinction

M0 has neither license enforcement nor subscription metering. Build neither.

- No license-key infrastructure.
- No "trial expired" UI.
- No usage caps.
- No billing integration (Stripe, etc.).
- No "upgrade to Pro" CTAs.

These belong to M3, after the architecture-boundary decision is stable and the first paid pilot has shipped. Building them earlier wastes engineering time on a moving target.

## Tribal procurement quick reference

| Threshold | What it means | NativeForge implication |
|---|---|---|
| Under $10,000 (micro-purchase) | No competitive bids required | Core tier ($12K) just over; close call |
| $10,001 – $250,000 (simplified acquisition) | 3 quotes required, no formal RFP | Pro and Enterprise both qualify; weeks not months sales cycle |
| Over $250,000 | Full competitive procurement; RFP, scoring, documentation | Stay below this. All NativeForge tiers do. |

Tribes can fund software via: direct cost on a grant, indirect cost pool, tribal general fund / enterprise revenue, or TTA program grant. One-time license fits grant procurement better than SaaS because it's a finite capital expenditure.

## Why this matters for M0

M0 is a demo, not a paid product. But three things in M0 are choices that lock in (or preserve) optionality for the paid tiers later:

1. **Tenant isolation architecture** (`execution/03-demo-isolation-spec.md`). Already strong. Do not regress.
2. **Profile-to-organization relationship.** Keep it changeable.
3. **Provider configurability** (LLM, ingestion, storage). Avoid hard-coding to specific vendors.

If those three stay clean, every pricing tier in this file is reachable from M0 without a rewrite. If any of them ship sloppy, the Sovereignty and Consortium tiers become rebuilds, not extensions.

## What this file does NOT decide

- The actual final pricing. The numbers above are the revenue model's recommendation. The user signs off after pilot validation per `validation/pre-coding-checklist.md` item 6.
- Whether to offer SaaS at all. The revenue model recommends a hybrid; the call is the user's.
- Implementation pricing for specific customers. Each engagement is scoped.
- Multi-year contract structures. Negotiated per consortium deal.
