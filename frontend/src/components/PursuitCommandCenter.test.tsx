import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import {
  PursuitCommandCenter,
  type CommandCenter,
} from "./PursuitCommandCenter";

function center(over: Partial<CommandCenter> = {}): CommandCenter {
  return {
    schema_version: "nf_pursuit_command_center_v1",
    mode: "discovered",
    opportunity: {
      id: "s1",
      title: "Indian CDBG",
      agency: "HUD",
      program_name: "ICDBG",
      source: "manual",
      pipeline_stage: "new",
      application_deadline: "2026-10-15T23:59:00+00:00",
      loi_deadline: null,
    },
    pursuit: null,
    workflow: {
      derived: true,
      shown: false,
      current_stage_id: null,
      stages: [
        {
          id: "profile",
          short_label: "Profile",
          label: "Organization profile",
          status: "complete",
          summary: "On file",
          view: "organization",
        },
        {
          id: "pursuit",
          short_label: "Pursuit",
          label: "Pursuit decision",
          status: "not_started",
          summary: "Open when ready",
          view: null,
        },
      ],
    },
    next_action: {
      headline: "Start this as a pursuit",
      detail: "Creates tasks for this grant.",
      action_id: "pursuit",
      view: "pursuits",
      owner_label: null,
    },
    open_work: {
      open_count: 0,
      blocked_count: 0,
      overdue_count: 0,
      tasks: [],
      blockers: [],
    },
    deadlines: [
      {
        kind: "application_deadline",
        label: "Application deadline",
        occurs_at: "2026-10-15T23:59:00+00:00",
        source: "opportunity record",
      },
    ],
    contacts: {
      items: [],
      extraction_performed: false,
      empty_message:
        "NativeForge has not yet read this notice for contacts. Absence here does not mean the notice names nobody.",
    },
    question_intelligence: { facts: [], found: false },
    interactions: [],
    institutional_memory: {
      funder_agency: "HUD",
      prior_pursuits: [],
      prior_contacts: [],
      prior_interactions: [],
    },
    ...over,
  };
}

describe("PursuitCommandCenter", () => {
  it("does not present chase progress for a discovered opportunity", () => {
    render(
      <PursuitCommandCenter
        center={center()}
        onGoTo={vi.fn()}
        onRecordInteraction={vi.fn(async () => undefined)}
      />,
    );
    expect(screen.getByText("Opportunity discovered")).toBeInTheDocument();
    expect(screen.queryByText("This pursuit")).not.toBeInTheDocument();
    expect(
      screen.getByText(/has not yet read this notice for contacts/i),
    ).toBeInTheDocument();
  });

  it("renders contacts, roles, and provenance when present", () => {
    render(
      <PursuitCommandCenter
        center={center({
          mode: "active_pursuit",
          pursuit: { id: "p1", status: "active" },
          workflow: {
            derived: true,
            shown: true,
            current_stage_id: "forms",
            stages: [
              {
                id: "profile",
                short_label: "Profile",
                label: "Organization profile",
                status: "complete",
                summary: "On file",
                view: "organization",
              },
              {
                id: "forms",
                short_label: "Package",
                label: "Application package",
                status: "current",
                summary: "Create when ready",
                view: "pursuits",
              },
            ],
          },
          contacts: {
            extraction_performed: true,
            empty_message: null,
            items: [
              {
                id: "c1",
                role: "program",
                name: "Jane Doe",
                title: "Program Officer",
                office: "ONAP",
                email: "jane.doe@hud.gov",
                phone: "202-555-0134",
                website: null,
                provenance_kind: "source_document",
                source_document: "NOFO.pdf",
                source_section: "Agency Contacts",
              },
            ],
          },
        })}
        onGoTo={vi.fn()}
        onRecordInteraction={vi.fn(async () => undefined)}
      />,
    );
    expect(screen.getByText("Active pursuit")).toBeInTheDocument();
    expect(screen.getAllByText("Jane Doe").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText(/Program questions/)).toBeInTheDocument();
    expect(screen.getByText("From the notice")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "jane.doe@hud.gov" })).toHaveAttribute(
      "href",
      "mailto:jane.doe@hud.gov",
    );
  });

  it("says so when the notice was read and named nobody", () => {
    render(
      <PursuitCommandCenter
        center={center({
          contacts: {
            items: [],
            extraction_performed: true,
            empty_message:
              "No grant contact information was identified in the available source materials.",
          },
        })}
        onGoTo={vi.fn()}
        onRecordInteraction={vi.fn(async () => undefined)}
      />,
    );
    expect(
      screen.getByText(/no grant contact information was identified/i),
    ).toBeInTheDocument();
  });

  it("surfaces prior funder knowledge from this tenant", () => {
    render(
      <PursuitCommandCenter
        center={center({
          institutional_memory: {
            funder_agency: "HUD",
            prior_pursuits: [
              {
                grant_spark_id: "old",
                title: "FY25 ICDBG",
                source: "grants_gov",
                pursuit_status: "closed",
              },
            ],
            prior_contacts: [
              {
                name: "Prior Officer",
                role: "program",
                email: "prior@hud.gov",
                from_opportunity: "FY25 ICDBG",
                provenance_kind: "customer_provided",
              },
            ],
            prior_interactions: [
              {
                id: "i1",
                interaction_type: "clarification_received",
                status: "answered",
                occurred_at: "2025-03-01T00:00:00+00:00",
                follow_up_at: null,
                subject: "Match waiver",
                notes: "In-kind counts.",
                owner_label: "Jordan",
                contact_id: null,
                funder_agency: "HUD",
              },
            ],
          },
        })}
        onGoTo={vi.fn()}
        onRecordInteraction={vi.fn(async () => undefined)}
      />,
    );
    expect(screen.getByText(/Prior pursuit: FY25 ICDBG/)).toBeInTheDocument();
    expect(screen.getByText(/prior@hud.gov/)).toBeInTheDocument();
    expect(screen.getByText(/Earlier Clarification received: Match waiver/)).toBeInTheDocument();
  });
});
