import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { MissionControl, type MissionControlPayload } from "./MissionControl";

function payload(over: Partial<MissionControlPayload> = {}): MissionControlPayload {
  return {
    schema_version: "nf_mission_control_v1",
    viewer_membership_id: "m1",
    metrics: {
      active_pursuits: 1,
      open_work: 1,
      blocked: 1,
      overdue: 0,
      due_this_week: 0,
      awaiting_response: 0,
      needs_review: 0,
    },
    next: {
      id: "w1",
      kind: "task",
      attention: "blocked",
      title: "Get chairman signature",
      detail: null,
      explanation: "Blocked — application due in 5 days",
      pursuit_id: "p1",
      grant_spark_id: "s1",
      opportunity_title: "ICDBG",
      funder: "HUD",
      stage_id: "forms",
      status: "blocked",
      due_at: "2026-10-03T00:00:00+00:00",
      days: 5,
      owner_membership_id: null,
      owner_label: null,
      view: "pursuits",
    },
    open_work: [
      {
        id: "w1",
        kind: "task",
        attention: "blocked",
        title: "Get chairman signature",
        detail: null,
        explanation: "Blocked — application due in 5 days",
        pursuit_id: "p1",
        grant_spark_id: "s1",
        opportunity_title: "ICDBG",
        funder: "HUD",
        stage_id: "forms",
        status: "blocked",
        due_at: "2026-10-03T00:00:00+00:00",
        days: 5,
        owner_membership_id: null,
        owner_label: null,
        view: "pursuits",
      },
    ],
    active_pursuits: [
      {
        pursuit_id: "p1",
        grant_spark_id: "s1",
        title: "ICDBG",
        funder: "HUD",
        deadline: "2026-10-15T00:00:00+00:00",
        current_stage_id: "forms",
        next_action: {
          headline: "A task is blocked",
          detail: "Get chairman signature",
          view: "pursuits",
        },
        open_count: 1,
        blocked_count: 1,
        overdue_count: 0,
        stalled: false,
        stalled_reason: null,
      },
    ],
    blockers: [],
    waiting: [],
    reviews: [],
    deadlines: [],
    recently_completed: [],
    empty: false,
    caught_up: false,
    next_deadline: null,
    ...over,
  };
}

describe("MissionControl", () => {
  it("renders empty state without inventing urgency", () => {
    render(
      <MissionControl
        data={payload({
          empty: true,
          caught_up: false,
          metrics: {
            active_pursuits: 0,
            open_work: 0,
            blocked: 0,
            overdue: 0,
            due_this_week: 0,
            awaiting_response: 0,
            needs_review: 0,
          },
          next: null,
          open_work: [],
          active_pursuits: [],
        })}
        onGoTo={vi.fn()}
        onOpenOpportunity={vi.fn()}
      />,
    );
    expect(screen.getByText("No active pursuits yet.")).toBeInTheDocument();
    expect(screen.queryByText("What you should do next")).not.toBeInTheDocument();
  });

  it("says caught up when the queue is empty", () => {
    render(
      <MissionControl
        data={payload({
          empty: false,
          caught_up: true,
          next: null,
          open_work: [],
          next_deadline: {
            label: "Application deadline",
            occurs_at: "2026-11-01T00:00:00+00:00",
          },
        })}
        onGoTo={vi.fn()}
        onOpenOpportunity={vi.fn()}
      />,
    );
    expect(screen.getByText(/You're caught up/)).toBeInTheDocument();
    expect(screen.getByText(/Application deadline/)).toBeInTheDocument();
  });

  it("opens the real destination for the next action", () => {
    const onGoTo = vi.fn();
    const onOpenOpportunity = vi.fn();
    render(
      <MissionControl
        data={payload()}
        onGoTo={onGoTo}
        onOpenOpportunity={onOpenOpportunity}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: "Open that work" }));
    expect(onOpenOpportunity).toHaveBeenCalledWith("s1");
    expect(onGoTo).toHaveBeenCalledWith("pursuits");
  });

  it("filters blocked work from the metrics", () => {
    render(
      <MissionControl
        data={payload({
          open_work: [
            payload().open_work[0],
            {
              ...payload().open_work[0],
              id: "w2",
              attention: "ready",
              title: "Call program officer",
              explanation: "Ready to begin",
            },
          ],
        })}
        onGoTo={vi.fn()}
        onOpenOpportunity={vi.fn()}
      />,
    );
    expect(screen.getAllByText("Get chairman signature").length).toBeGreaterThan(0);
    expect(screen.getByText("Call program officer")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Blocked" }));
    expect(screen.getAllByText("Get chairman signature").length).toBeGreaterThan(0);
    expect(screen.queryByText("Call program officer")).not.toBeInTheDocument();
  });
});
