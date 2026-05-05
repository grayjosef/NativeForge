# Guardrails and Risks

Cultural sensitivity does not live in the marketing. It lives in the code, the data model, the prompts, and the review gates. If any of these slip, the product is not credible.

## AI guardrails — what the AI cannot do

These are non-negotiable. They are enforced in system prompts, in review gates, and in templates that constrain the LLM's output structure.

1. **Never invent community statistics or facts.** If a number isn't in the entity profile or a cited source, the AI does not write it. If asked, the AI says "no source" and refuses.
2. **Never use pan-Indian generalizations.** Phrases like "Native peoples have always..." are blocked. Tribe-specific data is required for any cultural claim.
3. **Never fabricate citations.** If a section requires a citation and none is available, the AI flags it for human authorship rather than inventing one.
4. **Never claim impacts that have not been achieved.** The AI describes plans and proposed activities, not future outcomes as if accomplished.
5. **Never write tribal sovereignty positions.** Statements about tribal political stance, sovereignty assertions, or treaty interpretations come from tribal leadership only.
6. **Never write tribal resolutions.** Templates exist; the human edits them.
7. **Never write letters from tribal leaders or elders.** Those have a single human author.
8. **Never use deficit-based framing as default.** Strength-based language is the default; the AI flags deficit-framed prompts and rewrites toward asset-and-aspiration framing unless explicitly overridden.
9. **Never auto-submit anything.** Every submission has a server-enforced human approval step.
10. **Never persist user content for model training.** No customer data goes into a training corpus without explicit written consent.

## What the AI can do (with badges and review gates)

- NOFO plain-language summary
- Requirement extraction into structured fields
- Outline generation for narrative sections
- Needs statement draft from profile + cited sources
- SMART objectives draft from program description
- Project description / implementation plan draft
- Staffing plan draft from organizational profile
- Budget justification narrative draft from line items
- Sustainability plan template
- Evaluation plan framework
- Past performance narrative draft from stored project history
- Recommendation explanation rephrasing (within the templated structure)

Every one of these gets an AI badge in the UI. None of them is "final" until a human transitions the review state.

## Sovereignty must-haves (architectural, not aspirational)

These are commitments the product enforces, not promises the marketing makes.

- Tribe owns its data. Enforced by tenant isolation and full data export.
- No training on customer data. Enforced contractually with model providers.
- Full data export at any time. CSV + JSON. Built into the product.
- Audit logs retained for a configurable period.
- Role-based access. Enforced at API and database layer.
- Human approval required before any submission. Server-enforced state machine.
- Clear AI disclosure on every AI-generated element. Not hideable.
- No hidden resale of data. Contractual.
- Private deployment available for customers who require it. M3.

## Cultural review process

Before any AI feature ships:

- The system prompts and templates are reviewed by a tribal cultural advisor.
- Sample outputs are reviewed against the guardrails list above.
- Any guardrail violation is a blocker. Not a "fix later" — a blocker.

The advisory group is not optional. Building NativeForge without sustained tribal input produces a tone-deaf product. The Tribal CX Pilot literally said this. The 2022 OMB discovery sprint said this. Every interview in `validation/interview-plan.md` will say this. Believe it.

## Risk register (high-severity only)

| Risk | Severity | Mitigation |
|---|---|---|
| Building without tribal input → tone-deaf product | Critical | Mandatory tribal advisory review before any cultural-touching feature ships; 20+ interviews before M1 |
| AI hallucination in narrative drafts → ineligible/non-compliant submission | Critical | Server-enforced review gates; AI badge on every AI element; templated explanations only |
| Tribal data stored without sovereignty controls → trust collapse | Critical | Demo isolation spec (sprint 0); tenant separation; no training on customer data; explicit Trust Framework page |
| Cultural insensitivity in AI drafts → reputational damage | High | Cultural guardrails in system prompts; tribal review of drafts before feature ship; pan-Indian generalization detection |
| Missing eligibility restriction extracted → ineligible application submitted | High | Confidence scoring; human review required for low-confidence eligibility fields; never auto-confirm |
| Auto-fill writes wrong field on SF-424 → compliance issue | High | Diff view on autofill; human review required before "final"; mapping table version-controlled |
| Federal source ingestion breaks silently → demos fail | Medium | Multiple ingestion methods per source; monitoring alerts; manual upload fallback |
| Underpricing support → customer success burnout | Medium | Annual maintenance set at sustainable level; per-hour support beyond SLA |
| Established vendor (Euna, Arctic IT) adds tribal AI features → market window narrows | Medium | Move quickly on the wedge; sovereignty-first architecture is hard to retrofit so we hold the moat there |

The full risk matrix is in the source report Section 18.
