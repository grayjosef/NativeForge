import type { ReactNode } from "react";

import { PageHeader, Section, StatusBadge } from "../components/ui/primitives";

/**
 * Settings, and the operator surfaces that used to sit in the header.
 *
 * Workbench, Activation and the two demo walkthroughs were four of the six
 * buttons in the old header strip, given the same weight as the workspace
 * itself. They are operator tools. They stay reachable by `?view=` and by
 * Settings when `?ops=1` is present; they are not on the customer path.
 */

export interface SettingsPageProps {
  environment: "demo" | "live";
  onEnvironmentChange: (environment: "demo" | "live") => void;
  organizationId: string;
  onOrganizationIdChange: (value: string) => void;
  organizationIdValid: boolean;
  /** Session membership owns the org; the identifier is displayed, not edited. */
  organizationLocked?: boolean;
  onOpen: (view: string) => void;
  onSignOut?: () => void;
  /** Operator workbench / demos. Off the customer Settings path; still reachable by `?view=`. */
  showOperatorTools?: boolean;
  children?: ReactNode;
}

const OPERATOR_SURFACES: Array<{ view: string; label: string; detail: string }> = [
  {
    view: "workbench",
    label: "Operator workbench",
    detail: "Discovery review queues, source freshness and the decision pack.",
  },
  {
    view: "activation",
    label: "Activation",
    detail: "Deployment readiness and the activation boundary.",
  },
  {
    view: "beta_onboarding_cockpit",
    label: "Beta onboarding cockpit",
    detail: "Readiness of this deployment for a controlled beta.",
  },
  {
    view: "sc_customer_demo",
    label: "Customer walkthrough (SC)",
    detail: "A scripted offline walkthrough. Uses bundled data only.",
  },
  {
    view: "nm_wa_operator_demo",
    label: "Operator walkthrough (NM/WA)",
    detail: "A scripted offline walkthrough. Uses bundled data only.",
  },
];

export function SettingsPage(props: SettingsPageProps) {
  const {
    environment,
    onEnvironmentChange,
    organizationId,
    onOrganizationIdChange,
    organizationIdValid,
    organizationLocked = false,
    onOpen,
    onSignOut,
    showOperatorTools = false,
  } = props;

  return (
    <div className="nf-page">
      <PageHeader
        eyebrow="Govern"
        title="Settings"
        lead="Workspace preferences, environment, and operator tools."
      />

      <Section
        title="Environment"
        lead="Which set of data this workspace is working against."
        aside={
          <StatusBadge tone={environment === "demo" ? "info" : "positive"}>
            {environment === "demo" ? "Demo environment" : "Live organization"}
          </StatusBadge>
        }
      >
        <p className="nf-note">
          Demo data is separate from live organization data at the database level, not by a filter
          in the application. Switching here changes which one every page reads.
        </p>
        <div className="nf-card-actions">
          <button
            type="button"
            className="nf-btn nf-btn-secondary"
            onClick={() => onEnvironmentChange(environment === "demo" ? "live" : "demo")}
          >
            Switch to {environment === "demo" ? "live organization" : "demo environment"}
          </button>
        </div>
      </Section>

      <Section
        title="Organization context"
        lead="The organization this browser is working on behalf of."
      >
        <div className="nf-field">
          <label htmlFor="set-org">Organization identifier</label>
          <input
            id="set-org"
            className="nf-input"
            value={organizationId}
            onChange={(e) => onOrganizationIdChange(e.target.value)}
            spellCheck={false}
            readOnly={organizationLocked}
            disabled={organizationLocked}
          />
          {organizationLocked ? (
            <p className="nf-field-help">
              This comes from your sign-in session. It cannot be changed from the browser.
            </p>
          ) : !organizationIdValid ? (
            <p className="nf-field-help nf-field-help--warn">
              This does not look like a valid organization identifier, so requests will be refused.
            </p>
          ) : (
            <p className="nf-field-help">
              Once you sign in, this comes from your session and stops being editable.
            </p>
          )}
        </div>
      </Section>

      {showOperatorTools ? (
      <Section
        title="Operator tools"
        lead="Internal surfaces. Not part of the customer workspace."
      >
        <ul className="nf-source-list">
          {OPERATOR_SURFACES.map((s) => (
            <li key={s.view} className="nf-source">
              <div>
                <p className="nf-source-name">{s.label}</p>
                <p className="nf-source-detail">{s.detail}</p>
              </div>
              <button
                type="button"
                className="nf-btn nf-btn-secondary nf-btn-sm"
                onClick={() => onOpen(s.view)}
              >
                Open
              </button>
            </li>
          ))}
        </ul>
      </Section>
      ) : null}

      {onSignOut ? (
        <Section title="Session" lead="This device only.">
          <div className="nf-card-actions">
            <button type="button" className="nf-btn nf-btn-secondary" onClick={onSignOut}>
              Sign out
            </button>
          </div>
        </Section>
      ) : null}
    </div>
  );
}
