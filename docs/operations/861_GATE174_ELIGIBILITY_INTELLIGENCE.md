# Gate 174 — Eligibility Intelligence

**Verifier:** `scripts/verify_nativeforge_eligibility_gate174.sh` → `RESULT=PASS`, `gate174_ready=true` (65 checks)
**Migration:** `0060_eligibility_intelligence` (head `0059` → `0060`)
**Network requests: 0.**

---

## 1. The question a boolean cannot answer

```text
who can apply, under what conditions, what disqualifies us, and what is
still unknown?
```

`True` hides a matching-funds condition nobody can meet. `False` hides that the only blocker is a UEI that takes a week to obtain. So eligibility is a set of **fifteen typed requirements**, each with its own status, and a **six-valued** result.

| result | meaning |
|---|---|
| `ELIGIBLE` | every requirement satisfied, none excludes |
| `LIKELY_ELIGIBLE` | everything checkable satisfied; the unchecked are not structural |
| `CONDITIONALLY_ELIGIBLE` | eligible **if** something addressable is obtained — and it is named |
| `INELIGIBLE` | an exclusion applies, or a structural requirement fails |
| `UNKNOWN` | not enough is known; **never** a soft no, never a yes |
| `REVIEW_REQUIRED` | evidence conflicts, or a human must read the text |

## 2. What the survey found

The same shape as Gate 173, one layer deeper — and worse:

> `existing_eligibility_is_unwired_from_canonical_graph = true`
> `stage7_consumes_an_unwired_stage6_preview = true`

Stage 7 eligibility consumes the **Stage 6 relevance preview**, which Gate 173 established cannot itself reach a canonical opportunity. The whole eligibility→relevance chain floats free of the graph.

**The survey's own first run hid that.** A `native_relevance_` prefix marker matched four Stage 7 modules that import the *old, unwired* stack and reported them as spine-wired. A naming convention is not a capability; the marker now names modules individually.

## 3. Negative requirements are first class

A model that stores only who **may** apply represents *"tribal governments are not eligible"* as the **absence** of a tribal class from a list — byte-identical to *"nobody wrote the list down"*. Those are different facts.

Migration 0060 gives a disqualifier its own `polarity` column, so it is a row with its own evidence. And an exclusion **ends the question** rather than being outvoted:

```sql
ck_..._exclusion_blocks_a_pursuable_result
```

Five satisfied requirements do not beat one disqualifier, and an `ELIGIBLE` row with an applied exclusion is unrepresentable.

## 4. Structural versus addressable

Not being a Tribe cannot be fixed before the deadline. A missing SAM registration can.

- failed **structural** requirement → `INELIGIBLE`
- failed **addressable** requirement → `CONDITIONALLY_ELIGIBLE`, with the condition named

Collapsing those into one "no" discards the only actionable half of the answer. `ck_..._conditional_names_its_condition` refuses a conditional result that names no condition — **it caught this gate's own scale fixture**, which claimed `CONDITIONALLY_ELIGIBLE` on 20,000 rows while leaving the condition null.

## 5. Entity classes do not lend each other eligibility

Deny by default. Naming *"Indian tribes"* names a `tribal_government` and **not** a tribal college, a tribal enterprise, or a Native nonprofit. Telling a Tribe otherwise costs them a cycle and their standing with the funder.

Only the **source's own** grouping language expands — `"tribal organizations"` names four classes because the funder scoped it that way, not because we inferred it. That lookup originally matched on case alone, so every real phrase returned an empty list; it now tolerates the spacing a source actually writes.

## 6. The organization profile

Three-valued and versioned from its content.

- **`UNANSWERED` is never a no.** "This Tribe has no matching funds" and "nobody has asked this Tribe about matching funds" are the difference between an opportunity discarded and an opportunity pursued.
- **A match names the profile version it used.** When a Tribe obtains a UEI, yesterday's `CONDITIONALLY_ELIGIBLE` does not become wrong — it becomes an answer about a superseded profile.
- **Gate 174 cannot verify authority.** `VERIFIED_BY_AUTHORITY` is reserved for Gate 177; the invariant refuses a profile that produces it here. The shape exists now so Gate 177 attaches rather than migrates.

## 7. The corpus, and why 1.0 is not the claim

16 rows, 7 pursuable and 9 blocked, feeding raw requirements and raw profiles into the real engine:

| | |
|---|---|
| false positives | **0** |
| false negatives | **0** |
| result accuracy | 1.0 |
| unknown / conditional / review | 2 / 3 / 1 |

**These are INFO.** What is *asserted* is falsifiability — five planted breakages each caught, and a naive entity-class-blind engine scores **0.31** on the same rows against the real engine's 1.0.

## 8. Global normalization, measured

| | 1 tenant | 50 tenants |
|---|---|---|
| normalizations | **1** | **1** |
| matches | 1 | 50 |

At population scale: **2,000 normalizations serve 40,000 matches across 20 tenants** — a 20× saving. And two tenants get **different** answers on the same opportunity, which is the point of separating global parsing from the per-tenant match.

## 9. Scale and access paths

| | 1,000 | 10,000 | 50,000 |
|---|---|---|---|
| evaluate | 65 ms | 636 ms | 3,777 ms |
| ms per opportunity | 0.065 | 0.064 | 0.076 |

40,000 rows written in **2 statements**. All 7 critical queries index-backed with zero selective scans. Peak memory 331 MB.

## 10. Known unknowns

- **No real opportunity has normalized requirements yet.** Gate 173 established the real graph carries no eligibility field; Gate 175's document intelligence is what supplies one.
- **The corpus is ours** — 16 cases we thought of.
- **Recognition is self-declared.** Nothing here verifies that an organisation is a federally recognised Tribe; the match flags when a legal-status claim rests only on the organisation's own word.
- **Gate 171's root cause remains UNKNOWN.**

## 11. Lessons

**A naming convention is not a capability.** A prefix marker reported four modules as wired to a spine they only share a name-stem with.

**A lookup miss and an empty answer are different.** `expand_class_group` returning `[]` read as "this phrase names no classes" rather than "this table was keyed differently."

**Let the schema catch the fixture.** The conditional-names-its-condition CHECK rejected 20,000 of my own rows, which is the constraint doing exactly what it exists for.
