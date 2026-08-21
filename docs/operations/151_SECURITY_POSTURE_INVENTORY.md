# Security Posture Inventory (Gate 06 / Block 18)

Schema: `nf_security_posture_inventory_v1`

Items: **15**
Status counts: `{"implemented": 8, "partial": 5, "unknown": 1, "missing": 1}`

## Items

- **demo_route_isolation** [implemented]: Demo/real data-mode isolation on SC route — Bridge flags live_ingestion/source_activation false
- **api_authz_surface** [partial]: API endpoint authz inventory — Existing app routes not expanded this gate; demo is static JSON
- **customer_org_isolation** [partial]: Customer/org profile isolation — Attribution checks + Block 18 isolation tests; no multi-tenant DB gate
- **generated_text_rendering** [partial]: Generated text rendering safety — React text nodes default-escape; no dangerouslySetInnerHTML on demo
- **feedback_input_handling** [implemented]: Feedback report input validation/bounds — Enums + sanitization + size bounds in Gate 06 hardening
- **slack_alert_formatting** [implemented]: Slack message injection resistance — Escape backticks/control chars; never fake sent
- **collaboration_dark_flags** [implemented]: Collaboration dark-flag defaults — All live claims forced false
- **package_export_overclaim** [implemented]: Package export overclaim resistance — export_allowed/final_export forced false under blockers
- **forms_upload_overclaim** [implemented]: Forms/upload persistence overclaim resistance — completion/persistence/upload forced false
- **secret_handling** [implemented]: Secret handling / no env dump — Inventory/security reports never print env values
- **logging_redaction** [partial]: Logging redaction — No new broad logger; avoid webhook URL logging
- **cors_security_headers** [unknown]: CORS / security headers — Not re-audited this gate for production deploy headers
- **dependency_risk** [missing]: Dependency vulnerability scan — No automated SCA run claimed this gate
- **prompt_injection_resistance** [partial]: Prompt/adversarial injection resistance — Fixtures + governance/QA block unsupported prose; not exhaustive
- **qa_bypass_resistance** [implemented]: QA / claim flag bypass resistance — Invariant suite + adversarial bypass tests

## Honesty

- pen_test_passed_claimed: `False`
- production_secure_claimed: `False`

## Notes

- Defensive inventory only — not a pen-test certificate.
- Do not claim NativeForge passed pen testing.
- Secrets and environment variable values are never included.
