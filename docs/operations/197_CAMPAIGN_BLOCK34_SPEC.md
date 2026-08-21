# Campaign Block 34 Spec — SCA Execution / Security Remediation Loop

Sprints 1351–1400.

Deliverables:

* Security tooling discovery (no new installs by default)
* Safe SCA execution (`npm audit`; `pip-audit` if present)
* Honest pass/fail/blocked reporting
* Scoped remediation only when safe (none required for npm clean)
* Operator/demo surface + smoke

Forbidden: SCA passed without run+pass evidence; pen-test passed; production secure.
