# Scoring Model

Distilled from source report Section 8. The score is **deterministic**. The LLM extracts facts and may rephrase explanations, but it does not produce the score.

## Six dimensions, weighted

| Dimension | Weight | What it measures |
|---|---|---|
| Eligibility Confidence | 25% | Does entity type match? Is SAM active? Is there a tribal set-aside? Any disqualifying conditions? |
| Mission Alignment | 20% | Does the program area match the tribe's stated priorities? |
| Capacity Fit | 15% | Staff capacity? Resolution feasible in timeline? Required partners available? |
| Funding Value | 15% | Award amount vs. tribe's typical grant size; indirect cost recovery opportunity |
| Reporting Burden | 10% | Frequency of reports; data elements required; platform complexity |
| Win Likelihood | 15% | Competition level; past award history with agency; tribal priority points available |

Total = weighted sum of the six. Each dimension scored 0–100. Composite is also 0–100.

## Recommendation tiers

| Recommendation | Composite range (rough) | Required conditions |
|---|---|---|
| Strong Pursue | 80–100 | Eligibility confirmed; high mission match; manageable reporting; sufficient timeline; tribal priority points |
| Pursue | 65–79 | Eligibility confirmed; mission match moderate-to-high; timeline adequate; no major capacity gaps |
| Pursue with Conditions | 55–64 | Eligibility confirmed BUT match needs sourcing OR timeline tight |
| Needs Review | 40–54 | Eligibility ambiguous OR major capacity gap OR extreme reporting burden |
| Do Not Pursue | < 40 | Low mission match AND high reporting burden AND/OR insufficient timeline |
| Disqualified | (overrides composite) | Entity type explicitly ineligible OR currently debarred OR expired SAM |

## Rules per dimension

### Eligibility Confidence (deterministic)

Start at 100. Subtract for each gap.

- If extracted eligibility list does not include this entity_type: **disqualified** (overrides everything).
- If `sam_registration_status` is expired: **disqualified**.
- If `tribal_profile.federally_recognized = FALSE` and `extracted.eligibility.federally_recognized_tribe_required = TRUE`: **disqualified**.
- If `extracted.eligibility.disqualifying_conditions` matches profile: **disqualified**.
- If `extracted.eligibility.population_threshold` and tribe is below threshold: **disqualified**.
- If extraction confidence < 0.75 on the eligibility section: cap score at 60, flag for human review.

### Mission Alignment

Match the Spark's program area against `tribal_profile` priorities (M0 stub: a stored list of program areas the tribe has marked as priority).

- Direct match (exact program area): 100
- Adjacent match (related program area): 60
- No match but tribally eligible: 30
- No match: 0

### Capacity Fit

- Staff capacity (from profile, M1) ≥ NOFO complexity estimate: +50
- Resolution required AND timeline allows resolution path (≥ 30 days OR resolution already on file): +30
- Required partners (e.g., letter of support from external entity): +20 if present, 0 if not

M0 stub: simplifies to (timeline ≥ 30 days) → 80, (timeline < 30 days) → 40.

### Funding Value

- Award ceiling within typical grant size band: +50
- Indirect cost allowable: +25
- High match-to-funding ratio penalty: -20 if match > 25% and waiver unavailable

M0 stub: (award_ceiling between $100k and $5M) → 80, otherwise 50.

### Reporting Burden

Inverse score — high burden gets a low score.

- Quarterly or more frequent reporting: 30
- Semi-annual: 60
- Annual: 90
- Single closeout report: 100

### Win Likelihood

- Tribal priority points or set-aside: +50
- Past award history with this agency (M1): +20 per past award (cap 40)
- Number of expected awards / total program funding ratio (M1): up to +30

M0 stub: (tribal priority points present) → 80, otherwise 50.

## The recommendation explanation is templated

The explanation is **not** a freeform LLM paragraph. It is a templated sentence with slots filled from rule outputs.

Example template for Strong Pursue:

```
Strong match for {tribal_profile.legal_name}. You are an eligible {entity_type_display},
the program directly addresses your stated priority of {matched_priority}, and the
${award_ceiling_display} award ceiling is within your typical grant size. The
{deadline_days}-day window is {feasibility_phrase}. We recommend immediately
{recommended_action}.
```

Example template for Disqualified (entity type):

```
Your entity type ({entity_type_display}) is not listed as eligible for this program.
The NOFO restricts eligibility to {eligible_entity_types_display}. Do not apply.
```

The LLM is allowed to rephrase the templated explanation for tone or readability, but it is **not allowed** to introduce new facts or change the recommendation. The rephrased version is logged in `ai_runs` so the original templated version is always recoverable.

## Override

Every recommendation has a "Review this recommendation" link that opens the full scoring rationale and allows the user to override the system recommendation with a documented reason. The override is logged. NativeForge never prevents a user from pursuing a grant — it advises.

## Tests required (M0)

- Snapshot test on every dimension's rule with known inputs.
- Snapshot test on the composite calculation.
- Test that disqualifying conditions override the composite.
- Test that the same inputs produce the same recommendation across calls.
- Test that the templated explanation correctly fills slots from rule outputs.
- Test that an override is recorded with user, timestamp, and reason.
