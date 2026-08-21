# Campaign Block 24 SPEC — Controlled Customer Pilot Auth Scaffolding

## Objective

Build access-boundary and org-scoped route/context scaffolding without claiming
live login or production multi-tenant auth.

## Auth modes (scaffolding)

* not_supported
* demo_operator_view
* fixture_scoped (default for this run)
* internal_preview
* external_pilot_not_enabled
* production_not_supported

## Deliverables

* `customer_access_boundary_contract_service.py`
* `customer_pilot_auth_assembler_service.py`
* SC demo panel: `sc-demo-customer-pilot-auth`
* Cross-org isolation tests

## Forbidden claims

* Customers can log in / login live
* Production multi-tenant auth complete
* RBAC production-ready
* Customer data isolation production-ready
* External users can access pilot
* Collaboration enabled for customers

## Readiness

Controlled customer pilot: **NO_GO**
