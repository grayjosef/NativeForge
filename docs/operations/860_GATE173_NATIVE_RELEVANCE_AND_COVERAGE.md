# Gate 173 — Native Relevance and Coverage Intelligence

**Verifier:** `scripts/verify_nativeforge_native_relevance_gate173.sh` → `RESULT=PASS`, `gate173_ready=true` (84 checks)
**Migration:** `0059_native_relevance_and_coverage` (head `0058` → `0059`)
**Network requests: 0**, asserted by counting refused sockets.
**No sources added, no activations, nothing onboarded.**

---

## 1. The principle this gate exists to enforce

```text
Native relevance is NOT the presence of the words Native, Indian or Tribal.
```

Two real shapes make that concrete:

- A Grants.gov record coded **`99 — Unrestricted`** contains no Native word anywhere and is open to every Tribe in the country. A keyword filter throws it away.
- A broadband program open to *"units of general local government and Indian tribes"* says the word **once**, in a list, on page 14 of an attachment.

So **twelve of the thirteen** candidate signals never look at a word: applicant eligibility codes, general-government eligibility, breadth of eligible classes, geography, beneficiaries, statutory authority, prior Native awards, program history, sector alignment, source context, and document evidence.

## 2. What the survey found, and why it decided the gate

A real Native relevance stack already existed — eight labels, a deterministic evaluator, confidence bands, human-review triggers, an overclaim guard and an over-filter guard, built across Sprints 182–191. The survey's load-bearing finding:

> **Not one of its ten modules can reach a canonical opportunity.** Every relevance module in the repository sees fixture dictionaries and nothing else.

So this gate **binds** relevance to the Gate 167 graph rather than building a second engine, and reuses `native_eligibility_code_classification_service`, which already knew that *an absent code is not a negative finding*.

43 primitives surveyed: 7 AUTHORITATIVE, 22 REUSABLE, 3 READY_UNPOPULATED, 3 LEGACY, 8 UNWIRED.

**The survey's own first run was wrong twice**, and both were instrument defects rather than findings. It called `nf_source_operations_events`, `nf_opportunity_field_conflicts` and `nf_opportunity_identity_relationships` UNWIRED because they hold zero rows — they are empty because *reality* is empty. And it scanned only `services/`, so Gate 169's identity tables looked unread when the repository layer reads them every time. A table now needs three measurements, and `READY_UNPOPULATED` exists to separate "nothing uses this" from "nothing has happened yet".

`nf_award_documents` holds 876 archived demo rows of `financial_report` and `award_letter` hanging off `awarded_grant_id` — **post-award compliance artifacts**, a different lifecycle stage from NOFO evidence. Gate 175 cannot reuse it without conflating pre-award evidence with post-award proof.

## 3. Eight classes, never one score

Durable truth is **classification + evidence + reason + uncertainty**. A score exists for ranking only, because a score cannot be reviewed and cannot be argued with.

| class | meaning |
|---|---|
| `NATIVE_SPECIFIC` | only Native entities may apply |
| `NATIVE_PRIORITY` | open wider, Native applicants preferred or set aside for |
| `NATIVE_ELIGIBLE` | Native entities named alongside others |
| `BROADLY_ELIGIBLE_NATIVE_RELEVANT` | general eligibility that includes Tribes without naming them |
| `NATIVE_BENEFICIARY_RELEVANT` | applicant need not be Native; Native people are who the money reaches |
| `INDIRECTLY_RELEVANT` | real but weak — sector, geography, agency mission |
| `UNCERTAIN` | the evidence does not settle it; **a request for a human** |
| `NOT_RELEVANT` | evidence positively indicates it is not |

**Beneficiary relevance is not applicant relevance.** Who benefits and who may apply are different questions, and collapsing them is how a pipeline recommends opportunities nobody can submit. A **Native-serving** nonprofit is likewise not a **Native** entity — an eligibility list naming "Indian tribes" does not name it.

## 4. No classification without evidence

Twelve evidence types, each bound to the **sha256 of the payload it was read from**. A human assertion may have no payload — a person is the origin — and nothing else may. Confidence and ambiguity are separate fields, because *"we are sure the text says X"* and *"what X means here is contested"* are different problems.

Three rules are enforced by invariant checkers, and the two that matter most are enforced again by the database:

```sql
ck_..._decisive_needs_evidence    -- a decisive class with evidence_count = 0 is unrepresentable
ck_..._uncertain_asks_for_review  -- UNCERTAIN that asks for nobody is a contradiction
ck_..._is_traceable_to_a_payload  -- evidence with no bytes behind it, unless a human said it
```

## 5. High recall, and an honest third state

`NOT_CANDIDATE` is a **finding** and must be earned. With no signal and no stated eligibility the answer is `UNKNOWN`, never `NOT_CANDIDATE` — *"we have not looked"* and *"we looked and it is not relevant"* are different facts, and collapsing them is how a discovery pipeline silently stops discovering.

An **inference cannot drop an opportunity**. The candidate stage originally accepted `INFERRED` evidence as grounds for a negative; a permanent regression caught it. A false negative here is unrecoverable — nothing downstream ever sees the row again.

## 6. The gold corpus, and why its perfect score is not the claim

27 rows, 9 of them hard negatives: *Indian River County*, *native prairie species*, a Tribal grantee named only in a background paragraph, a prior award that does not imply current eligibility, an amendment that **removes** Tribal eligibility, agency mission language with no notice-level relevance.

Every row supplies **raw structured inputs only** and states no answer. It caught three defects on its first run:

1. **Beneficiary evidence was unreachable** whenever applicant evidence existed — branch order meant a state agency serving Tribal populations came back `UNCERTAIN`.
2. **`BROADLY_ELIGIBLE_NATIVE_RELEVANT` was effectively unreachable**, because entity-class ambiguity blocked it — and entity-class ambiguity is precisely what that class *means*.
3. **The recall metric scored accepted answers as misses**, because rows whose accepted set spans a relevant class *and* `UNCERTAIN` sat in the denominator.

| metric | value |
|---|---|
| candidate recall | **1.0** (0 false negatives at the irreversible stage) |
| candidate precision | 0.875 |
| classification recall / precision | 1.0 / 1.0 |
| review-required rate | 0.519 |
| unknown rate | 0.111 |

**These are INFO, not assertions.** A corpus written alongside the model it scores proves internal consistency, not correctness about the world. What is *asserted* is **falsifiability**: a keyword-only baseline scores **0.52** on the same rows against the real model's 1.0, and five planted breakages are each proven to be caught. Two genuinely ambiguous rows are **named** as excluded from the recall denominator rather than silently improving it.

## 7. The real projection — the finding that matters

22 real canonical opportunities, 166 real provenance rows, projected through the layer:

| | |
|---|---|
| classified | 22 |
| unknown | 0 |
| review required | 22 |
| **in the applicant band** | **0** |
| evidence types available | `AGENCY_CONTEXT`, `SECTOR_ALIGNMENT`, `SOURCE_CONTEXT` |

**Not one real opportunity can reach an applicant-relevant class, because the real graph carries no eligibility field at all.** Provenance holds title, agency, URL, dates, doc_type and assistance listings — nothing on file says who may apply. That is reported as the finding it is, and inventing `APPLICANT_ELIGIBILITY` evidence to improve the numbers would be refused by `ck_..._is_traceable_to_a_payload`, since there are no bytes to point at.

This is exactly what Gates 174 and 175 exist to change.

## 8. Coverage — knowing what we are not watching

13 source families × 7 coverage states, plus 8 gap-signal types that are traces of funding we may have missed: an award with no solicitation, an amendment with no original, a deadline with no opportunity, a recurring program absent this cycle.

Two refusals are structural:

- **Completeness is never claimed.** The denominator is unknown: the read model reports the publishers we have entered, not the publishers that exist. In the real run, **10 of 13 families have no entry at all**, reported rather than averaged away.
- **Discovery never onboards.** A discovered publisher stops at `DISCOVERED_PENDING_REVIEW`, and `ck_..._pending_review_has_no_source` makes it impossible for one to already have a source attached — the Gate 162–171 authorization boundary, in the schema.

## 9. Scale and access paths

| | 1,000 | 10,000 | 100,000 |
|---|---|---|---|
| classify | 67 ms | 686 ms | **7,149 ms** |
| ms per opportunity | 0.067 | 0.069 | 0.071 |

Population 100×, time 106×, per-opportunity cost flat. 50,000 rows written in **6 statements** (0.00012 per opportunity). Peak memory 367 MB.

**Relevance is global, measured:** classifier calls are **1,000 at one tenant and 1,000 at fifty**. There is no opportunity-by-tenant sweep, and the parameter exists in the phase solely so its being ignored can be proven.

All 9 critical queries are index-backed at 50,000 rows, with zero selective scans and no exemptions required.

## 10. Genericity

The scan was extended from **16 declared files to 22** so that `generic_layer_source_leaks = 0` actually covers the relevance engine. It had been true and *vacuous* — a guarantee that does not cover the thing it is quoted about is worse than none, because it reads like one. The relevance engine is where a source-specific branch would do the most damage: *"trust the codes if it came from Grants.gov"* works until somebody adds a source that codes differently.

0 leaks, 0 identity branches, scanner proven falsifiable against a planted leak.

## 11. Known unknowns

- **The corpus is ours.** 27 rows we thought of. It proves the model behaves as specified on those cases; it does not prove the world contains no case we missed.
- **No real opportunity has eligibility evidence.** The applicant band is empty on real data and will stay empty until document intelligence lands.
- **Coverage has no denominator.** We cannot say what fraction of Native-relevant publishers we monitor, and the read model refuses to pretend otherwise.
- **Gate 171's root cause remains UNKNOWN**, carried forward unchanged.

## 12. Lessons

**A guarantee that does not cover the thing it is quoted about is worse than none.** `generic_layer_source_leaks = 0` was true before this gate and said nothing about any of it.

**"Empty" is not a verdict about code.** The survey retired three working structures because they hold no rows; they are empty because reality is empty.

**Name the exemption.** Two corpus rows are genuinely ambiguous and excluded from recall — stated, so the number cannot quietly improve itself.

**A metric computed against an empty denominator is not a measurement**, which is why `ratio()` returns `None` rather than zero.
