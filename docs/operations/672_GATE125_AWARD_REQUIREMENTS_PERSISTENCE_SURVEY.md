# 672 — Gate 125A: award requirements persistence survey

Read before implementing. Every answer below was measured, not recalled.

## The twelve questions

```text
1  requirement service contracts       3 services, ~1,150 lines, no storage
2  model/calendar/proof/audit          all four exist, all four contract-only
3  award requirements table/repo       neither
4  proof/audit persistence             no. The contract exists; the store does not
5  document storage                    no. award_document_store_service is absent
6  same table or separate              proof *state* on the row; proof *audit*
                                       gets its own table in a later gate
7  reference nf_awarded_grants         yes, FK, ON DELETE CASCADE
8  organization_id directly on the row yes, and this is not redundant
9  migration required                  yes - 0033
10 API route exists                    no
11 repository-backed without auth      yes, the Gate 120/123/124 shape
12 readiness change                    yes, and one derivation is wrong again
```

## 1–2. Three services, and not one of them stores anything

```text
award_requirement_model_service          494 lines   what a requirement is
award_requirements_calendar_service      329         when it is due
award_requirement_proof_audit_service    329         what proves it was done
```

Plus `awarded_grants_requirements_artifact_service` (354) and
`..._readiness_service` (381), which report on the three.

Gate 108 built all of it. Gate 124 gave awards a table and left this half
deliberately, because a requirement recurs and one award produces dozens of
rows with their own due dates and proof trails.

### The vocabularies already exist — bridge, never restate

```text
REQUIREMENT_TYPES                   15  audit, financial_report, closeout, ...
REQUIREMENT_STATUSES                10  not_started .. accepted, waived, unknown
DUE_DATE_STATUSES                    6  verified, calculated, estimated,
                                        unknown, unsupported, needs_human_review
DATE_CALCULABLE_STATUSES             2  verified, calculated
EXTRACTION_STATUSES                  6  human_entered, evidence_extracted,
                                        projected_from_nofo, unknown,
                                        needs_human_review,
                                        unsupported_document_type
ACTIVE_CAPABLE_EXTRACTION_STATUSES   2  human_entered, evidence_extracted
PROOF_STATUSES                       6  not_submitted, proof_missing,
                                        proof_attached, proof_accepted,
                                        proof_rejected, unknown
RECURRENCES                          7  one_time .. annual, on_request, unknown
SUBMITTED_STATUSES                   2  submitted, accepted
CLOSED_STATUSES                      3  accepted, not_applicable, waived
PROOF_ACTIONS                        6  attach_proof, mark_submitted, ...
```

`DUE_DATE_STATUSES` already distinguishes the five states this gate must
preserve, and `estimated` is deliberately outside `DATE_CALCULABLE_STATUSES`.
An estimate is not a date you can count down to.

## The defect this survey found: two booleans for one derivation

The gate brief asks for two columns:

```text
active_obligation    boolean not null default false
projected_burden     boolean not null default false
```

with a constraint that both cannot be true. But Gate 108 does not model this as
two facts. It models it as **one derivation off provenance**:

```python
# award_requirement_model_service, line 308
is_active_obligation = (
    extraction in ACTIVE_CAPABLE_EXTRACTION_STATUSES
    and bool(tenant_id)
    and bool(award_id)
)
if extraction == "projected_from_nofo":
    blocked_reasons.append("projected_burden_is_not_an_active_obligation")
```

Two independent booleans admit four states. Three are meaningful and the fourth
— both false — is the unsupported/unknown case, which already has its own field.
Worse, two booleans that can be *set* are two more places for a caller to assert
what the provenance does not support: exactly the declared-versus-derived defect
this campaign has found in Gates 120, 121, 122, 123 and 124.

**Decision.** Both columns are built, because they are what a query needs to
filter on. Neither is ever accepted as input. Both are derived from
`requirement_source` (Gate 108's `extraction_status`, bridged by import), a
CHECK constraint refuses the contradiction, and an invariant refuses a result
where the pair disagrees with the provenance that produced it.

```text
requirement_source                    active_obligation  projected_burden
human_entered / evidence_extracted    true               false
projected_from_nofo                   false              true
unsupported_document_type             false              false
unknown / needs_human_review          false              false
```

## 3–5. No tables, and the migrations confirm it

```text
tables in migrations                     32
matching requirement / proof / document  nf_spark_requirements (0005)
                                         nf_authority_proof_records (0026)
                                         nf_audit_events (0002)
                                         nf_awarded_grants (0032)
```

`nf_spark_requirements` is **pursuit-side** — what a NOFO asks of an applicant
before they apply. `nf_authority_proof_records` is Gate 52's authority
lifecycle, an entirely different proof. Neither is an award requirement.

```text
nf_award_requirements                   does not exist
nf_award_requirement_proofs             does not exist
nf_award_documents                      does not exist
repositories/award_requirements.py      does not exist
api/award_requirements.py               does not exist
services/award_document_store_service   does not exist
```

## 6. One table, and the proof audit trail deferred

Two questions look alike and are not:

```text
proof state    one per requirement. What is true now.
proof audit    many per requirement. What happened, and when.
```

The gate brief's schema puts proof *state* on the requirement row —
`proof_required`, `proof_status`, `proof_document_ref`, `submission_status`,
`submitted_at`, `accepted_at`, `rejected_at`. That is correct: it is the current
state of one requirement, one row.

`award_requirement_proof_audit_service` builds something else. `PROOF_ACTIONS`
has six verbs and `build_audit_trail` returns a sequence, so a single
requirement submitted, rejected, resubmitted and accepted is four rows with four
actors and four timestamps. Putting that on the requirement row would mean
either overwriting the history — which is the one thing an audit trail may never
do — or a JSON array nothing can query by actor or date.

**Decision.** Proof audit gets its own table in a later gate. Same reasoning
Gate 124A used to defer requirements, applied one level down.

## 7–8. Both identifiers, and why neither is redundant

```text
organization_id    UUID, FK organizations, the RLS predicate's left side
awarded_grant_id   UUID, FK nf_awarded_grants, ON DELETE CASCADE
```

`awarded_grant_id` is a row relationship. It is **not** an RLS authority, and
carrying only it would be the same substitution Gates 110–113 exist to refuse:
the RLS predicate is `organization_id = current_setting(...)::uuid`, so a table
without that column cannot be scoped at all. Reaching the organization through a
join would mean every policy on this table depended on a policy on another one.

Carrying only `organization_id` would be worse in the other direction: nothing
would relate a requirement to the award it came from, and a compliance calendar
is a list of requirements *for an award*.

An invariant refuses a result where the two disagree, and a test asserts a
requirement cannot be written by supplying `awarded_grant_id` alone.

`ON DELETE CASCADE` on the award is safe because there is no delete path.
Archiving sets `archived_at` and the row stays.

## 9. Migration 0033

```text
0033_nf_award_requirements    head 0032 -> 0033
```

## The anchors the contracts use today

```text
service                                org_id  tenant_id  award_id
award_requirement_model_service           0       13        13
award_requirements_calendar_service       0        7         7
award_requirement_proof_audit_service     0       12        11
```

Zero `organization_id` in all three — correct for a contract layer with no
storage, and identical to what Gate 124A found on the awards side. The moment a
row exists, `organization_id` anchors it and `tenant_id` is not carried at all:
unlike an award, a requirement has no tenant-facing label of its own. It
inherits its tenant through the award.

## 10. No API route

Ten route decorators in the whole API, none for awards or requirements.

**Skip it,** for the Gate 120/122/123/124 reasons plus one specific to this
gate:

```text
1  a read route needs a session to scope by, and /current-user 401s for
   everybody, so the authenticated branch is unreachable and untestable
2  the table will hold zero rows, so the route's only behaviour is
   `no_requirements`
3  a requirement is a deadline somebody is held to. The first surface that
   serves one is the surface that will be believed when it says nothing is
   due, and an empty table returning `no_requirements` is indistinguishable
   from a tenant with no obligations. That distinction is the entire product;
   building the route before it can be made is building the failure mode
```

## 11–12. Repository-backed without auth, and what readiness may say

```text
customer_auth_live                     false
verified_operational_binding           false
customer_persistence_live              false
document_storage_live                  false
requirement_extraction_live            false
ui_available                           false
ready_for_operational_awarded_tracking false
```

The Gate 120/123/124 shape applies unchanged: a repository can exist, be
exercised against an isolated database, and refuse every production write.

What readiness may say afterwards:

```text
award_requirements_persistence schema_available      false -> true
award_requirements_persistence repository_available  false -> true
award_requirements_persistence write_path_available  false -> true
award_requirements_persistence operational           false, unchanged
document_storage_live                                false, unchanged
proof_audit_persistence_available                    false, new and false
ready_for_operational_awarded_tracking               false, unchanged
```

### The second defect: `operational` is not the same as "ready to operate"

Gate 124 fixed `operational_awarded_recommended` to require both lanes:

```python
operational_awarded_recommended = bool(
    awarded.get("operational") and awarded_requirements.get("operational")
)
```

That was right as far as it went, and Gate 125 will break it again. A lane's
`operational` means schema + anchor + RLS + repository + contract + auth. It
says nothing about the lane's own product prerequisites, and this lane has one
the spine has always named:

```text
SPINE_PREREQUISITES["award_requirements_persistence"]
  = (customer_auth, awarded_grants_persistence, document_storage)
```

`document_storage` is false. So after this gate, with auth forged, both lanes
report `operational` and the invariant guarding the recommendation fires:

```text
awarded_recommended_operational_without_document_persistence
```

The invariant is right — evidence needs a home before anything claims to track
compliance. The derivation is reading capability-operational where it means
ready-to-operate. Gate 125E adds the unmet-prerequisite conjunct so the two
agree.

## Docs referenced

The brief cites `599_GATE108_AWARDED_GRANTS_REQUIREMENTS_TRACKING.md`. No such
file: 599 is Gate 109's survey. The Gate 108 requirement docs are

```text
594_GATE108_AWARDED_GRANTS_REQUIREMENTS_TRACKING_SURVEY.md
597_GATE108_REQUIREMENT_MODEL_AND_CALENDAR_CONTRACT.md
598_GATE108_PROOF_AUDIT_AND_READINESS_DELTA.md
```

Doc 598 already names this gate as next action 2, and document storage as next
action 4 — in that order.

## Implementation constraints carried out of this survey

```text
1  migration 0033 creates nf_award_requirements; proof audit is named, not built
2  organization_id anchors; awarded_grant_id is a row relationship and is
   refused as an anchor; tenant_id, customer_org_id and organization_profile_id
   are refused by name
3  active_obligation and projected_burden are DERIVED from requirement_source,
   never accepted as input, and a CHECK refuses the contradiction
4  unsupported_requirement can never be an active obligation
5  an unknown or estimated due date requires human review; estimated is not
   calculable and is never counted down
6  proof_document_ref is a dangling reference by construction. Document storage
   is false and this gate does not move it
7  a submitted proof is not an accepted proof, and a document reference is not
   a submission
8  the Core sa.Table restates every CHECK constraint (Gate 119C's defect)
9  archive by setting archived_at; no DELETE path
10 bridge Gate 108's vocabularies by import - REQUIREMENT_TYPES,
   REQUIREMENT_STATUSES, DUE_DATE_STATUSES, DATE_CALCULABLE_STATUSES,
   EXTRACTION_STATUSES, ACTIVE_CAPABLE_EXTRACTION_STATUSES, PROOF_STATUSES,
   RECURRENCES, SUBMITTED_STATUSES, CLOSED_STATUSES
11 production writes require customer_auth_live AND verified operational binding
12 every new conjunct both derived and injectable
13 fix operational_awarded_recommended to require unmet prerequisites to be empty
14 no API route; document why
```
