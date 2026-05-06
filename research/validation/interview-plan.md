# Interview Plan

Distilled from source report Section 17. Building NativeForge without direct engagement with tribal grant professionals is a fundamental product risk. The 2024 Tribal CX Pilot itself was predicated on the principle that initial assumptions had to be challenged by speaking directly with recipients. No amount of secondary research substitutes for 20 interviews with working tribal grant managers.

## Interview targets (20 total minimum)

| Persona | Number | Priority |
|---|---|---|
| Tribal grant manager / grant administrator | 6–8 | Critical |
| Tribal administrator / tribal government leadership | 3–4 | Critical |
| Finance officer / CFO | 3–4 | Critical |
| Program director / department head | 2–3 | High |
| Tribal council member | 2 | High |
| Native nonprofit executive director | 3–4 | High |
| External grant consultant serving tribes | 3–4 | High |
| Tribal technology / security staff | 2–3 | Important |
| Federal program officer (BIA, IHS, ANA) | 2–3 | Important |
| Compliance / audit professional | 2 | Important |

## Sourcing channels

- NAFOA (Native American Finance Officers Association)
- NCAI (National Congress of American Indians)
- NIHB (National Indian Health Board)
- USET, ATNI, GLITC (regional tribal coalitions)
- Tribal technical assistance networks (e.g., HUD ONAP TA providers)
- Direct outreach via tribal government websites
- Existing ContractForge customer relationships, if applicable to tribal contracts

## Interview questions by persona

### Tribal Grant Manager / Administrator

1. Walk me through what a typical week looks like when you're managing a grant application.
2. What's the single most time-consuming thing you do in the grant process?
3. How do you currently find out about new grant opportunities relevant to your tribe?
4. How do you decide whether to pursue a particular grant?
5. How many grants are you currently managing or pursuing simultaneously?
6. What software or tools do you use today — even if just Excel or email?
7. How much do you currently spend on grant writing consultants, and how do you feel about that relationship?
8. What forms or documents do you find yourself filling out repeatedly?
9. What is the hardest part of the post-award compliance process?
10. Have you ever had to return grant funds or received an audit finding? What happened?
11. How does your tribal council get involved in the grant process?
12. What would you trust software to do automatically, and what would you never let software do without checking it yourself?
13. What concerns would you have about putting your tribe's data into a third-party software platform?
14. If a tool cost $12,000 once and saved your team 200 hours per year, would that be compelling?
15. What would make you distrust or stop using a software product?

### Finance Officer / CFO

1. How do you currently track grant budgets vs. actuals across multiple grants?
2. What accounting system do you use? Would you want a grant tool to integrate with it?
3. How do you manage indirect cost rate documentation and ensure it's applied correctly?
4. Have you ever had a disallowed cost finding? What caused it?
5. What does Single Audit preparation look like for your organization?
6. What financial data would you never put into a third-party cloud system?
7. What would a software tool need to do to make your job significantly easier?

### Tribal Council Member

1. How do you currently learn about grants your administration is pursuing?
2. What information would you want to see about a grant before authorizing a resolution?
3. How long does it typically take to get a resolution approved once requested?
4. What has surprised you — positively or negatively — about how your tribal government manages federal funding?
5. What would concern you about a software vendor having access to your tribe's grant data?

### External Grant Consultant

1. How many tribal clients do you serve, and what does a typical engagement look like?
2. What do tribal staff consistently struggle with that you end up doing for them?
3. What software, if any, do you use with tribal clients? What's missing?
4. If a tool let tribal staff do more independently, would that threaten your business or create new opportunities?
5. What cultural or political sensitivities do you navigate when writing grants for tribal clients?
6. What tribal-specific grant sources do you track that most tools miss?

### Native Nonprofit Executive Director

1. What is your annual grant budget, and how many grants do you manage at once?
2. What percentage of your staff time goes to grant management?
3. What is your biggest software-related pain point in grants today?
4. Would you pay for a software tool, or do you prefer grants management as a direct program cost within an award?
5. What would a "tribal-specific" feature actually mean to you in practice?

## What we learn from interviews (and feed back into the build)

| Question theme | Influences |
|---|---|
| Top time-consuming activities | Sprint priority for M0/M1 |
| Existing tool stack | Integration roadmap; objection handling |
| Consultant spend | Pricing; positioning |
| Repeated forms | Form autofill priorities |
| Compliance pain | Post-award M2 priorities |
| Council involvement | Resolution tracker M1 priorities |
| Trust concerns | Sovereignty page content; private deployment urgency |
| Pricing sensitivity | Final pricing model |

## Logistics

- 45–60 minutes per interview.
- Recorded with consent. Transcripts go to a private project folder, NOT this research repo.
- Anonymized summary findings go to `validation/interview-findings.md` (created after interviews run; not in this repo yet).
- Compensate interviewees. Tribal grant managers are not free research subjects.
- Tribal cultural advisor reviews the interview guide before fieldwork begins.

## What this plan does NOT do

- Replace ongoing tribal advisory relationships. The 20 interviews kick off a relationship, not conclude it.
- Validate the M0 build. M0 ships to the demo regardless of interview timing because the demo is for buyers (often the same population). Interview findings primarily shape M1 and M2.
- Substitute for legal/regulatory review. See `pre-coding-checklist.md`.
