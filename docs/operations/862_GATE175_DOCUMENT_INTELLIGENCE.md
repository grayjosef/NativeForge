# Gate 175 — Document / NOFO / Attachment Intelligence

**Verifier:** `scripts/verify_nativeforge_document_intelligence_gate175.sh` → `RESULT=PASS`, `gate175_ready=true` (61 checks)
**Migration:** `0061_document_intelligence` (head `0060` → `0061`)
**Network requests: 0. Documents downloaded: 0.** Every byte is a synthetic fixture.

---

## 1. The premise

```text
the landing page is not the authoritative answer
```

Eligibility lives on page 14 of an attachment. The match requirement lives in Appendix C. The FAQ published a month later is what the programme officer will cite. A pipeline that reads the API record and stops is reading a summary of the thing, not the thing.

## 2. What the survey found

```text
no_table_binds_a_document_to_a_canonical_opportunity = true
```

`nf_award_documents` exists — 876 **archived** rows of `financial_report` and `award_letter`, hanging off `awarded_grant_id` and `award_requirement_id`. Those are **post-award compliance artifacts**. A NOFO, an appendix and an FAQ are pre-award evidence about an opportunity nobody has won, and filing a funder's eligibility language against a grant that does not exist would conflate two lifecycle stages permanently.

The existing text extractor already separates *unsupported* from *empty*, so it is reused rather than rebuilt.

## 3. The rule this gate exists for

**A document we could not READ must never read as a document with nothing in it.**

```sql
ck_..._absence_is_meaningful_only_when_parsed
```

`UNSUPPORTED` and `PARTIAL` can never carry `absence_is_meaningful`. A scanned PDF reporting *"no requirements found"* is byte-identical to a NOFO that genuinely imposes none — and only one of those means the applicant is safe.

Of the eight document states, exactly one (`PARSED`) makes an absent fact meaningful. Five (`NOT_FETCHED`, `FETCHED`, `PARSE_PENDING`, `UNSUPPORTED`, `FAILED`) cannot support a factual claim at all.

## 4. Identity is the content, not the URL

| situation | result |
|---|---|
| same URL, changed bytes | a **new** version |
| same bytes, second URL | the **same** document |

Keying on the URL would make an agency's mirror look like an amendment, and would make a silent republication invisible.

## 5. Conflicts are represented, never silently resolved

| rule | effect |
|---|---|
| `AMENDMENT_SUPERSEDES` | the amendment's value wins; **the predecessor is retained** |
| `NOTICE_OUTRANKS_SUMMARY` | the notice beats a landing-page summary of it |
| `FAQ_CLARIFIES` | **nobody wins** — both values survive, the pair goes to review |
| `UNRESOLVED` | no explicit rule applies; a human decides |

`ck_..._winner_needs_a_selecting_rule` makes a winner under a non-selecting rule unrepresentable, and `ck_..._clarification_does_not_overwrite` stops an FAQ erasing what it clarifies. A silent resolution is a guess wearing a value, and the person who finds out it was wrong is the one whose application was rejected.

## 6. Every fact is a citation

A fact carries its document, its page or section, the extraction method, a confidence, and **the funder's own quoted words**. `ck_..._fact_quotes_its_source` refuses one without them — a value nobody can be shown is a value nobody can defend. A citation past the document's last page is refused.

## 7. Falsifiability — and a check that was passing for the wrong reason

Eight planted breakages, each asserted by its **specific** detector:

supersession cycle · missing predecessor · latest pointer not newest · citation beyond the document · fact with no document · fact from an unreadable document · clarification overwrite · false absence claim

The cycle check originally asserted only that the chain came back *invalid* — and the fixture also tripped `successor_ordinal_not_newer`, so it would have passed with cycle detection removed entirely. The fixture now uses equal ordinals so only the cycle can explain the result.

## 8. Scale

| | 500 | 2,000 | 10,000 |
|---|---|---|---|
| opportunities | 500 | 2,000 | 10,000 |
| documents | 3,000 | 12,000 | **60,000** |
| facts | 6,000 | 24,000 | **120,000** |
| total | 157 ms | 641 ms | **3,975 ms** |
| ms per opportunity | 0.314 | 0.321 | 0.398 |

All 10,000 version chains valid. 65,000 rows written in **3 statements**. All 10 critical queries index-backed, zero selective scans. Peak memory 299 MB.

## 9. The integrated 173→175 proof

| case | result |
|---|---|
| **A** — no Native word in the title; eligibility on page 14; match requirement in the appendix; amendment moves the deadline | CANDIDATE → `NATIVE_ELIGIBLE` from document evidence → tribal eligibility identified → `LIKELY_ELIGIBLE` when match capability is unasked, `CONDITIONALLY_ELIGIBLE` naming `MATCHING_FUNDS` when it is known false → amendment supersedes, original retained → 3 citations, each quoting its page |
| **B** — Native terms only in the background; applicant class explicitly excluded | background mention did not fire → `NOT_CANDIDATE` → `NOT_RELEVANT` → exclusion applied → `INELIGIBLE` |
| **C** — award announcement for an unseen solicitation | gap signal with a recommended action; publisher `DISCOVERED_PENDING_REVIEW`; **no source auto-onboarded**; coverage refuses completeness |
| **D** — FAQ clarifying ambiguous NOFO eligibility | both documents preserved, clarification linked, `FAQ_CLARIFIES`, no silent overwrite, both values retained, review required |

Zero invariant failures across all four. **Case A is the one the whole block exists for**: a keyword filter never sees it, a landing-page pipeline cannot answer it, and a boolean eligibility model cannot express the answer.

## 10. Known unknowns

- **No real document has been ingested.** Every byte here is synthetic; live retrieval remains behind the Gate 162–171 authorization boundary.
- **The parsers are fixtures.** This gate builds the document *model*, states, versioning, conflicts and citations — not a production PDF pipeline.
- **The authority rules are deliberately few.** Three rules select or clarify; everything else is `UNRESOLVED` and asks for a human. That is a choice, and it will generate review load.
- **Gate 171's root cause remains UNKNOWN.**

## 11. Lessons

**A detector that passes for the wrong reason is not a detector.** The cycle check asserted chain-invalidity, which another rule already guaranteed.

**Pick the lifecycle stage before picking the table.** `nf_award_documents` was the obvious reuse and the wrong one.

**Absence is a claim.** Recording that a document said nothing is only honest when we actually read it.
