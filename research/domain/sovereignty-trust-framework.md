# Sovereignty Trust Framework

Distilled from source report Section 11. The trust framework is in the product, not the marketing. Every commitment listed here is enforced by code, contract, or both.

## CARE Principles

Developed in 2019 by the International Indigenous Data Sovereignty Interest Group. The most applicable framework for Indigenous data governance in a U.S. tribal software context.

- **Collective Benefit:** Data systems should benefit the tribe, not just the vendor. NativeForge asks: how does each data point we collect create value for the tribe?
- **Authority to Control:** Tribes maintain control over their own data at all times. Tribes can export all data, delete all data, review all data at any time.
- **Responsibility:** NativeForge has an affirmative responsibility to document how it uses tribal data, disclose any sharing, and ensure data use upholds tribal dignity.
- **Ethics:** Any AI feature must be grounded in ethical use of tribal data. No training on customer data without explicit written consent.

## OCAP Principles

Ownership, Control, Access, Possession — a Canadian First Nations framework developed by the First Nations Information Governance Centre. Not directly applicable to U.S. tribes but widely cited; OCAP is trademarked by a Canadian organization, and NativeForge documentation acknowledges this distinction while applying the underlying principles.

## Three barriers to tribal data sovereignty (BJA)

The Bureau of Justice Assistance identifies three major barriers:

1. Exclusion of tribal nations from decision-making about how federal/state governments use tribal data
2. Lack of federal/state data-sharing agreements that protect tribal data ownership
3. Lack of federal/state mechanisms providing tribes equitable access to AI/AN data for governmental functions

NativeForge operates in a private-software context, not a federal-data context, but these barriers inform what tribes fear from outside vendors.

## NativeForge Trust Framework

| Commitment | Implementation |
|---|---|
| The tribe owns its data | Terms of service; enforced by tenant isolation architecture |
| No training on customer data without explicit written consent | Terms of service; AI model design; documented in privacy policy; contractually enforced with model providers |
| Full data export at any time | Export tool in product (CSV + JSON); M0 |
| Audit logs retained for configurable period | Admin panel with exportable audit log |
| Role-based access control | Enforced at database and API level |
| Configurable data retention | Admin setting; compliant with applicable law |
| Human approval required before any submission | Server-enforced state machine; cannot be disabled |
| Clear AI disclosure on all AI-generated content | AI badge on every AI-generated paragraph |
| No hidden resale or monetization of data | Terms of service; enforced contractually |
| Private deployment option for larger customers | M3 offering |
| Data deletion process documented | Step-by-step process in admin panel |
| Incident response commitments | Security policy; notification within 72 hours |
| Culturally respectful onboarding | Onboarding includes tribal sovereignty acknowledgment page |
| Tribal consultation before major roadmap decisions | Formal advisory group of tribal grant professionals |

## What this means for M0

The Data Sovereignty page (Sprint 7 in `04-m0-implementation-plan.md`) is the in-product expression of this framework. The page must:

- Read the framework table above as the source of truth (link or render directly).
- Distinguish between commitments that are enforced today (M0) versus deferred (M1, M2, M3).
- Provide a working "Export my data" button.
- Provide a working "View audit log" button (read-only display of the audit log entries for the requesting org).
- Surface the AI training policy: "We do not train AI models on your tribal data."
- Surface the model provider: "We use [model provider name] under a no-training agreement. View our agreement summary."

## AI training policy (binding)

NativeForge does not train any AI model on customer data. This applies to:

- Tribal profiles
- Spark records ingested by the customer
- AI-drafted narratives produced for the customer
- User-uploaded documents
- Audit log entries
- Any other content originating from the tribal customer's use of the product

The only exception is explicit, written, opt-in consent from a tribal authority for a specific use case. Such consent is recorded in the contract and surfaced in the customer's audit log.

This commitment is enforced by:

- Choosing model providers whose terms of service prohibit training on API inputs by default (or whose training-on-inputs is opt-in and we never opt in).
- Routing all customer-data LLM calls through the no-training endpoints / configurations.
- Recording every LLM call in `ai_runs` with the provider, model, endpoint, and configuration so an auditor can verify post-hoc.

## What M0 explicitly does not include

- SOC 2 Type II certification (M1+ as customer pilots demand it).
- Private deployment / on-premises option (M3).
- Configurable data retention windows beyond the default (M2).
- Incident response runbook in the customer-facing surface (M1; the back-office runbook exists from day one).
- Cross-tenant analytics opt-in flow (M2).

The trust framework page lists these as "deferred to [milestone]" rather than promising them today.
