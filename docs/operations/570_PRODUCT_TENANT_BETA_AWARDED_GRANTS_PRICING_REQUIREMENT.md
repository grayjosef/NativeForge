# 570 — Product requirement: tenant beta, awarded grants, persistent-license pricing

Carry-forward requirement recorded 2026-08-28. **Not an authorization to activate
collectors, start monitoring, or claim source coverage.** Every truth boundary
from Gates 87–102 holds unchanged.

## Positioning

NativeForge is **a persistent-license grant intelligence, pursuit, and
award-compliance operating system for Tribal governments** — not generic grant
search software.

The demo is not "here is a grants database". It is:

> Here is what your Tribe should look at this week, why it matches you, what
> would disqualify you, what it requires, and what happens next if you pursue or
> win it.

## Beta scope

Four initial Tribe/tenant customers. Source priority: **South Carolina first,
federal second.**

Each tenant configurable by: recognition status, geography/operating state,
applicant class, service area, program priorities, department routing,
exclusions, source watchlist, alert preferences, digest frequency,
document/library requirements, awarded-grant compliance requirements.

**Applicant classes stay distinct.** Federally recognized, state-recognized,
historic-affiliation, Native nonprofit, Native business, Tribal college and any
other class are not interchangeable. Unknown eligibility stays `UNKNOWN` or
`NEEDS_HUMAN_REVIEW` — the Gate 92 rule, unchanged.

## The ten beta features

```text
 1  Tenant Eligibility Profile
 2  SC + Federal Source Watchlist
 3  Weekly Matched NOFO Digest (default)
 4  Optional Daily Alerts
 5  Pursuit Suppression once in the pipeline
 6  Tenant Pursuit Pipeline
 7  Reporting Burden Preview before pursuit
 8  Awarded Grants Workspace
 9  Tenant Document Library
10  Tenant Rules, Routing, Alert Configuration
```

### Digest

Weekly, Monday morning by default. Daily reserved for grants/admin users, urgent
deadline changes, amendments, high-fit opportunities, approaching deadlines.

Contents: newly matched NOFOs; high-fit not yet reviewed; changed deadlines;
amendments; approaching deadlines; newly excluded or downgraded; needing human
review.

Each item explains why it matched *this tenant*, what eligibility evidence
supports it, what uncertainty remains, why it may be excluded or downgraded,
deadline status, and reporting burden preview where evidence exists.

### Pursuit suppression

Starting a pursuit moves the opportunity into the tenant pipeline and removes it
from future *new/unpursued* digests. It stays visible in the pipeline. It is
**not deleted**, **not removed from source history**, and **not removed from
audit/provenance records**. Suppression is **tenant-specific** — never global.

### Pipeline stages

`review · pursue · drafting · submitted · awarded · not_pursued · archived`

Answers: *should we chase this, and where are we?* Distinct from Awarded Grants.

### Awarded Grants workspace — mandatory, separate section

Answers: *what are we now legally, financially, administratively and
operationally responsible for?*

Tracks per award: reporting deadlines, audit requirements, reimbursement
deadlines, drawdown deadlines, performance period, match requirements, budget
categories, allowable/unallowable cost flags, required documents, board/council
resolution requirements, subrecipient or vendor reporting obligations, closeout
requirements, recurring narrative reports, recurring financial reports, assigned
owner, internal reminder schedule, proof of submission, status of each
requirement.

**Projected reporting burden before pursuit and active compliance obligations
after award are different things and must not be blurred.** Unsupported or
unclear requirements are `UNKNOWN`, `NEEDS_HUMAN_REVIEW`, or
`UNSUPPORTED_DOCUMENT_TYPE`. No fabricated reporting deadlines.

## What already exists that this lane must reuse, not rebuild

Surveyed 2026-08-28:

```text
32  eligibility_* services        evidence contract, quality, exclusion evidence,
                                  fit assessment (blockers, confidence, deadline
                                  risk, demo fixture)
 7  pursuit_* services            incl. m0 pursuit pipeline kanban planning packet
 4  tenant_* services
 1  awarded_grant_portfolio_service.py
 2  deadline_normalization_service.py, deadline_provenance_service.py
 0  digest services               <- the genuine greenfield
```

Gate 87 built the deadline provenance contract (doc 490); Gate 91 built the
awarded-vs-pursuit reporting parser. The awarded/pursuit distinction this
requirement insists on is **already modelled** — Gate 105 extends it rather than
inventing it.

## SC priority is supported by the registry

```text
fixtures/external_source_registry/nativeforge-source-registry-v2.csv
  381 rows total
   57 rows scoped state_if_applicable = SC
    1 authoritative source of SC state recognition
```

So "South Carolina first" rests on real registry coverage, not an aspiration.
What does **not** exist is any live collection from those 57 sources — Gate 93
found all five Phase 1 collectors `not_active`, and Gates 98–102 have kept them
that way.

## Three tensions to resolve before building, not during

### 1. Change detection needs a time series that does not exist

"Changed deadlines", "amendments", "newly excluded or downgraded" all require
comparing an observation to an earlier one. With no live collection there is no
second observation.

The demo must therefore use **recorded multi-snapshot fixtures**, explicitly
labelled as such, and the digest contract must be able to say *this comparison
is between two recorded snapshots, not two live checks*. Designing this in at
Gate 104 is cheap; discovering it at Gate 109 is not.

### 2. The allowability review is self-referential

The requirement includes a feature assessing whether software, grant
administration, compliance and capacity-development costs may be allowable — and
NativeForge is such a cost. A tool telling a customer that buying the tool is
grant-fundable has an obvious incentive problem.

The labels are already conservative (`clearly allowable` … `requires human
review`), and the required wording is *may be fundable*, never *is always grant
funded* and never *this cost is allowable* without supporting source text.

**Recommendation to carry into Gate 105/110:** when the assessed cost is
NativeForge itself, cap the label at `requires human review` regardless of
evidence strength, and say why on the surface. A self-assessment that can only
ever return "ask a human" is defensible; one that can return "clearly allowable"
is not, however good the citation.

### 3. Deadline confidence is already known to be uneven

Gates 87–89 measured the corpus and found deadline provenance sparse enough to
need its own contract. "Approaching deadlines" in a weekly digest is a
high-trust surface built on that data. Gate 104 should consume
`deadline_provenance_service` rather than reading dates directly, so an
unverified deadline surfaces as unverified rather than as a countdown.

## Pricing — persistent license, drafted by the operator

Modelled on ContractForge: **one license, owned not rented; persistent; first 12
months maintenance included; annual maintenance after year one; named-seat
tiers; fair-use limits; activated pursuit economics; upgrade credit;
contact-sales enterprise motion.** Not monthly SaaS.

These figures are the operator's drafts, recorded verbatim as drafts:

```text
Starter / Solo Tribe   $14,995   1-2 seats   ~$2,999/yr after yr 1
                                 $300-500 per activated pursuit after allotment
                                 full license credit toward Professional 5

Professional 5         $34,999   5 seats     ~$6,999/yr after yr 1
                                 5,000 API/query units/month fair use

Professional 10        $49,999   10 seats    ~$8,999/yr after yr 1
                                 upgrade from Pro 5: $15,000

Enterprise / Tribal    custom    $75k-$150k+ maintenance custom
Government                       multi-department, board/council reporting,
                                 SSO/admin later, dedicated onboarding

Founding Tribe Beta    $24,999   5 seats     $4,999-6,999/yr after yr 1
Founding Tribe Plus    $34,999   10 seats    $6,999-8,999/yr after yr 1
```

Positioning note from the operator: discovery gets them interested, pursuit helps
them win, **awarded grants and reporting deadlines keep them retained.** Do not
underprice as generic grant search.

## Sales framing

Use:

> NativeForge helps Tribal governments build durable grant capacity: funding
> discovery, pursuit management, document reuse, reporting requirements tracking,
> audit deadline visibility, and award compliance operations in one
> tenant-specific system.

> Finding funding is only the first step. NativeForge helps the Tribe understand
> fit, pursue intelligently, and manage the requirements that come after an
> award.

Avoid: grant search tool · AI grant writer · generic grants database · always
grant-funded · guaranteed eligibility · guaranteed award.

## Demo story — fourteen beats

```text
 1 tenant-specific Tribe profile      8 pursuit pipeline
 2 SC + federal priority sources      9 reporting burden preview
 3 weekly matched NOFO digest        10 mark as awarded
 4 why an opportunity matched        11 awarded grants workspace
 5 why another is excluded /         12 reporting/audit/deadline tracking
   needs human review                13 software/capacity allowability label
 6 start pursuit                     14 trust/provenance/evidence surface
 7 suppression from future digest
```

Fixtures are acceptable **when clearly represented as demo/recorded/
synthetic-safe.** No fake live collection, no fake source monitoring, no
fabricated eligibility, no fabricated deadline, no fabricated reporting
requirements, no fake source coverage, no fake 65% improvement claim.

## Gate sequence

```text
103  Tenant Beta Feature Contract
104  Tenant NOFO Digest + Pursuit Suppression Contract
105  Awarded Grants Requirements Tracking Contract
106  Grants.gov Daily Extract Collector Scaffold (fixture/dry-run only)
107  Tenant Match Engine
108  Demo Tenant Seed Pack: 4 SC Tribes
109  Customer-Facing Digest / Pipeline / Awarded Demo
110  Demo Hardening and Pricing/Packaging Page
```

The infrastructure lane left open after Gate 102 — background worker, periodic
trigger, object store deployment — is **not a blocker for 103–105, 107 or 108**.
None of the ten beta features needs live collection to be built as a contract
against fixtures. Gate 106 is explicitly fixture/dry-run only.

If a technical dependency forces the Grants.gov scaffold earlier, this
requirement is preserved here and resumes immediately after.
