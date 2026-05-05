# AI Drafting Guardrails

Distilled from source report Section 9. M0 ships AI summary and outline only. Full narrative drafting is M1. The guardrails apply to both.

## What AI can safely draft (with human review gate)

| Output | M0 | M1 |
|---|---|---|
| NOFO plain-language summary | yes | yes |
| Requirement extraction (structured) | yes | yes |
| Outline generation for narrative sections | yes | yes |
| Needs statement draft (from profile + cited sources) | — | yes |
| SMART objectives draft (aligned to evaluation criteria) | — | yes |
| Project description / implementation plan draft | — | yes |
| Staffing plan draft (from organizational profile) | — | yes |
| Budget justification narrative draft (from line items) | — | yes |
| Sustainability plan template | — | yes |
| Evaluation plan framework | — | yes |
| Past performance narrative (from stored project history) | — | yes |
| Recommendation explanation rephrasing (within templated structure) | yes | yes |

Every output above goes through the server-enforced review state machine: `draft → review_requested → reviewed → approved → submitted`. The frontend can hide UI affordances; it cannot grant transitions.

## What requires human authorship and tribal voice

These are explicitly off-limits to the AI:

- Any claim about tribal history, culture, or traditional knowledge
- Any description of community values or worldviews
- Community-specific data that is not in the organizational profile
- Statements about tribal sovereignty or political positions
- Letters from tribal leadership or elders
- Tribal resolutions
- Any claims about impacts that have not yet been achieved

## Drafting principles (enforced via system prompts)

These ten rules are baked into every system prompt. Each has a corresponding test in M1's drafting-quality CI.

1. **Never invent community statistics or facts.** If a number isn't in the profile or a cited source, refuse rather than fabricate.
2. **Clearly distinguish AI-generated text from cited source material.** Inline citations or footnote markers required when sources are used.
3. **Default to strength-based, sovereignty-aligned language.** Asset-and-aspiration framing, not deficit-and-trauma framing.
4. **Every draft includes prominent human review warnings.** A standard preamble is appended to every export that includes AI-drafted content.
5. **Tribe-specific first — not pan-Indian.** A draft that doesn't reference the specific tribe by name fails review.
6. **Preserve tribal voice — AI drafts are starting points, not final submissions.** The product UI consistently surfaces "this is a draft" framing.
7. **Cultural relevance over generic language.** Generic phrases trigger a "specificity warning" suggesting tribal-profile-grounded alternatives.
8. **Never use exploitative or savior-oriented framing.** External-savior framings are blocked at template level.
9. **Explicitly support tribal self-determination framing where appropriate.**
10. **Allow local editors to override AI language completely at any time.** The AI never resists a manual override.

## Pan-Indian generalization detection

A pre-export check scans drafts for:

- Phrases like "Native peoples have always", "Indigenous communities are", "Native Americans face", "Tribal nations need" — without a specific tribe named.
- Generic statistics about "Native populations" not anchored to the tribe's profile.
- Cultural claims not sourced from `tribal_profile.community_profile` or a cited reference.

When detected, the draft is annotated with warnings. The user can override (and the override is logged), but the warning is never silently suppressed.

## Source attribution

Any AI draft that uses a statistic must cite the source. The pipeline:

1. The user attaches sources (uploaded PDF, URL, or text snippet) to the Spark or profile.
2. The drafting pipeline retrieves those sources.
3. Generated paragraphs that use a statistic include an inline citation marker linking back to the source.
4. If no source is available for a needed statistic, the AI emits `[CITATION NEEDED]` rather than fabricating one.
5. Export to PDF preserves citations in a footnote section.

## What M0 needs from this domain

For M0:

- The AI summary feature has the badge, the review gate state machine, and the pan-Indian generalization check.
- The outline generation feature uses templates that explicitly require tribe-specific naming.
- The recommendation explanation is templated, with the LLM only allowed to rephrase within the slot structure.

For M1:

- All ten principles enforced via system prompts.
- Cultural review by tribal advisor before any drafting feature ships.
- Sample outputs reviewed against the guardrails for the first 20 drafts produced in any pilot.
