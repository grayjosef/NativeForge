# NativeForge Native Relevance Scoring v1

Version: `nativeforge-native-relevance-scoring-v1`

Deterministic, explainable scoring for **offline** connector shells and future live ingestion. Scores inform ranking, review queues, and operator copy—they are not legal eligibility determinations.

---

## Principles

1. **Transparency** — Every score has enumerated `native_relevance_reasons`.
2. **No keyword oracle** — Title/body keyword hits inform hypotheses; they **cannot** yield `eligibility_confidence: confirmed` alone.
3. **Structured beats narrative** — Tribal eligibility flags, set-asides, applicant-type tables, and authoritative tags outweigh linguistic coincidence.
4. **Ambiguity escalates** — Missing applicant-class clarity triggers `review_required`.

---

## Score dimensions (conceptual)

The implementation maps these dimensions into bounded integer contributions:

| Dimension | Examples |
|-----------|----------|
| Native-specific language match | Title/body phrases (hypothesis only without structure) |
| Eligible entity type match | Tribal government; tribal organization; Native nonprofit |
| Tribal set-aside / priority points | Explicit set-aside; evaluation preference |
| Geography / service area | Indian Country; Alaska Native villages; NH community relevance |
| Funding domain relevance | Broadband, health, language, housing, climate |
| Rural / underserved / sovereignty-adjacent | Persistent disparities; trust or treaty context hints |
| Agency / source trust | Known tribal office vs. unknown publisher |
| Historical Native award pattern | Reserved for future cycles when data exists |
| Mission fit | Heuristic alignment from tags / domains |
| Match / cost-share burden | High burden lowers actionable priority (optional signals) |
| Application complexity | Optional friction hints |

---

## Hard rule

**Keyword hits alone can never produce confirmed Native relevance.**

If the only affirmative signals are `text_signal:*` reasons (linguistic matches), then:

- `eligibility_confidence` ∈ {`unknown`, `low`} — never `confirmed`.
- `review_required` should be `true` unless operators attach structured eligibility later.

---

## Output shape

Connectors and services emit:

```json
{
  "native_relevance_score": 0,
  "native_relevance_band": "low|medium|high|native_specific",
  "native_relevance_reasons": [],
  "eligibility_confidence": "unknown|low|medium|high|confirmed",
  "review_required": true,
  "review_reason_codes": []
}
```

### Bands

| Band | Typical drivers |
|------|-----------------|
| `low` | Keywords only; weak signals; conflicting hints |
| `medium` | Mixed structured + narrative signals; partial eligibility |
| `high` | Strong structured eligibility or tribal-government eligibility paths |
| `native_specific` | Tribal set-aside / dedicated tribal competition / unmistakable tribal-only program framing |

### Eligibility confidence

| Value | Meaning |
|-------|---------|
| `unknown` | Applicant classes not extracted |
| `low` | Mostly narrative / keyword hypotheses |
| `medium` | Some structured hints (tags, partial tables) |
| `high` | Strong structured hints short of legal confirmation |
| `confirmed` | Structured tribal eligibility path present (not keyword-only) |

`confirmed` is a **product intelligence** label—users still exercise their own legal review.

---

## Review reason codes (extensible)

Examples used in v1:

- `ambiguous_eligibility` — insufficient structured applicant-class data.
- `keyword_hypothesis_only` — linguistic signals without structured backing.
- `missing_applicant_types` — broad solicitation without extracted applicant classes.
- `burden_unknown` — cost-share / match not assessed.

---

## Implementation reference

Python reference implementation: `nativeforge.services.source_connectors.native_relevance` (`assess_native_relevance`).

This module is **offline-safe** (no network I/O).
