/**
 * Gate 129B: the operating shell — the product story in one panel.
 *
 * Nothing here decides anything. Every status and every truth label arrives
 * already computed from the capability matrix and the persistence spine, so a
 * label cannot drift from what the system actually reports. If auth goes live,
 * `AUTH NOT LIVE` disappears because the payload said so, not because someone
 * remembered to delete it.
 */

import type { ScCustomerDemoPayload } from "../demo/scCustomerDemoTypes";

type OperatingShell = NonNullable<ScCustomerDemoPayload["demo_operating_shell"]>;

export type DemoOperatingShellProps = {
  shell?: OperatingShell | null;
};

function statusLabel(section: OperatingShell["sections"][number]): string {
  if (section.operational) return "Operational";
  if (section.built) return "Built — not operational";
  return "Not built";
}

function statusKind(section: OperatingShell["sections"][number]): string {
  if (section.operational) return "operational";
  if (section.built) return "built";
  return "absent";
}

export function DemoOperatingShell({ shell }: DemoOperatingShellProps) {
  if (!shell) return null;

  const active = shell.truth_labels.filter((l) => l.active);

  return (
    <section
      className="nf-operating-shell"
      id="nf-operating-shell"
      data-testid="demo-operating-shell"
      aria-labelledby="nf-operating-shell-heading"
    >
      <h2 id="nf-operating-shell-heading" data-testid="demo-operating-shell-heading">
        What NativeForge does for a Tribal government
      </h2>

      <ul
        className="nf-operating-shell-labels"
        data-testid="demo-truth-labels"
        aria-label="Demo truth labels"
      >
        {active.map((l) => (
          <li
            key={l.label}
            className="nf-operating-shell-label"
            data-testid={`demo-truth-label-${l.label.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`}
            title={`Derived from ${l.derived_from}`}
          >
            {l.label}
          </li>
        ))}
      </ul>

      <p className="nf-operating-shell-note" data-testid="demo-operating-shell-note">
        Every status below is read from the same services the rest of the system
        answers with. Sections marked “Built — not operational” have a schema, a
        repository and a write path; they are not operational because customer
        authentication is not live, so no one owns the rows.
      </p>

      <ol className="nf-operating-shell-sections" data-testid="demo-shell-sections">
        {shell.sections.map((section, index) => (
          <li
            key={section.section_id}
            className={`nf-operating-shell-section nf-status-${statusKind(section)}`}
            data-testid={`demo-shell-section-${section.section_id}`}
            data-operational={String(section.operational)}
            data-built={String(section.built)}
          >
            <span className="nf-operating-shell-step">{index + 1}</span>
            <div className="nf-operating-shell-body">
              <h3 data-testid={`demo-shell-section-title-${section.section_id}`}>
                {section.title}
              </h3>
              <p className="nf-operating-shell-shows">{section.shows}</p>
              <p className="nf-operating-shell-status">
                <span
                  className="nf-operating-shell-status-chip"
                  data-testid={`demo-shell-status-${section.section_id}`}
                >
                  {statusLabel(section)}
                </span>
                {section.expected_table ? (
                  <span className="nf-operating-shell-table">
                    {section.expected_table}
                  </span>
                ) : null}
                <span className="nf-operating-shell-rows">
                  rows written: {section.rows_written}
                </span>
              </p>
              {section.blocked_reasons.length > 0 ? (
                <ul
                  className="nf-operating-shell-blockers"
                  data-testid={`demo-shell-blockers-${section.section_id}`}
                >
                  {section.blocked_reasons.map((reason) => (
                    <li key={reason}>{reason}</li>
                  ))}
                </ul>
              ) : null}
            </div>
          </li>
        ))}
      </ol>

      <p className="nf-operating-shell-footer" data-testid="demo-shell-footer">
        Operational sections: {shell.operational_section_count} of{" "}
        {shell.section_count}. Rows written to any customer table:{" "}
        {shell.rows_written}. Login live: {String(shell.login_live)}.
      </p>
    </section>
  );
}

export default DemoOperatingShell;
