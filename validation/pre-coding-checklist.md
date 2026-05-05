# Pre-Coding Checklist

Six things to confirm before any production code is written. Distilled from source report Section 20.

## 1. Tribal interview round one

At least 5 interviews completed before M1 production code begins (full 20 before M1 ships). M0 demo work can proceed in parallel. Findings logged in a private folder; key takeaways shape M1 sprint priorities.

**Status:** ☐ Not started ☐ In progress ☐ Complete (≥5)

## 2. Legal review on AI-assisted grant writing

Confirm that providing AI-assisted grant writing guidance does not constitute the unauthorized practice of law in any jurisdiction we sell into. Specifically:

- Drafting grant narratives is not legal advice.
- Drafting tribal resolution language is borderline; M1 templates must be marked as templates, not advice.
- Eligibility scoring is not legal advice; recommendations are advisory and overridable.
- The terms of service include explicit "this is a tool, not professional advice" language.

**Status:** ☐ Not started ☐ In progress ☐ Complete

## 3. NOFO parsing accuracy benchmark

Test LLM extraction against ≥20 real NOFOs across the major tribal-relevant agencies (BIA, IHS, ANA, CTAS, DOE Indian Energy, HUD ONAP, EPA tribal, USDA RD tribal, NTIA TBCP, plus Grants.gov general).

For each NOFO, score the extraction on:

- Eligibility section: 100% recall on disqualifying conditions.
- Funding section: ≥95% accuracy on award ceiling, floor, match requirement.
- Timeline section: 100% accuracy on application deadline.
- Forms required: ≥90% recall on form names.
- Page limits: ≥85% accuracy.

If we cannot meet these thresholds with the chosen model, the extraction schema is too aggressive and we cut M0 scope to summarization + structured-list extraction (no confidence-scored deep extraction).

**Status:** ☐ Not started ☐ In progress ☐ Complete

## 4. SAM.gov API terms of use review

Confirm that automated data pulls from SAM.gov are permitted for the intended use case (auto-verifying registration status, pre-populating profile fields). Specifically:

- Rate limits are documented and we comply.
- Caching strategy aligns with their refresh cadence.
- Attribution requirements are met.

If automated pulls are disallowed, we fall back to user-initiated lookup with a manual entry fallback. M0 does not block on this; M1 does.

**Status:** ☐ Not started ☐ In progress ☐ Complete

## 5. Data sovereignty architecture review

Have a tribal technology advisor (e.g., AIPI affiliated researcher, NCAI Center for Tribal Digital Sovereignty contact, or named tribal IT/security professional) review:

- The tenant isolation design from `execution/03-demo-isolation-spec.md`.
- The audit log design from the audit output (post-`01`).
- The AI training policy from `domain/sovereignty-trust-framework.md`.
- The data export format and completeness.

The advisor's redlines are addressed before Sprint 1 ships. This is non-negotiable; cultural and sovereignty review by a tribal expert is the difference between a credible product and a tone-deaf one.

**Status:** ☐ Not started ☐ In progress ☐ Complete

## 6. Pricing validation with tribal procurement officers

Test the proposed pricing model with at least 5 tribal procurement officers or tribal CFOs:

- One-time license vs. annual SaaS preference.
- Acceptable price points by tribe size (small / mid / large / enterprise / sovereignty/private).
- Acceptable implementation fee.
- Whether software costs can be paid from a grant award.

Findings adjust the pricing tiers in `domain/competitive-landscape.md` before the first paid pilot is sold.

**Status:** ☐ Not started ☐ In progress ☐ Complete

## When this checklist gates work

| Item | Gates |
|---|---|
| 1. Tribal interviews (≥5) | Start of M1 production code |
| 1. Tribal interviews (full 20) | M1 ship to first paid customer |
| 2. Legal review | Public M0 demo to external buyers |
| 3. NOFO parsing benchmark | Sprint 3 (NOFO summary + extraction) ship |
| 4. SAM.gov ToS review | M1 SAM.gov live integration |
| 5. Data sovereignty advisor review | Sprint 1 (tribal profile) ship |
| 6. Pricing validation | First paid pilot contract signed |

M0 internal demo work can proceed in parallel with these. External-facing work cannot.

## Open question

Should item 5 (sovereignty architecture review) gate the M0 demo too? Argument for: the demo's sovereignty page is the product's most differentiating claim, and shipping it without expert review is risky. Argument against: the demo is internal/buyer-only; the page is a description of intent, not a deployed system. **Working assumption: review is required before any external buyer demo, not internal practice runs.**
