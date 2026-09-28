import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { WorkspacePage } from "./WorkspacePage";

/**
 * Production root (`/?` and `/?view=workspace`) mounts this page before any
 * session exists. Empty sparks + no next action is the first paint. Missing
 * EmptyState import crashed that path with a blank #root.
 */
const emptyProps = {
  organizationName: null,
  entityType: null,
  identityVerified: false,
  hasProfile: false,
  steps: [] as { id: string; label: string; shortLabel: string; state: "not_started"; lineSummary: string }[],
  sparks: [] as Record<string, unknown>[],
  selectedSparkId: "",
  onSelectSpark: vi.fn(),
  requirementsCount: 0,
  reviewSummary: null,
  score: null,
  pursuit: null,
  formPackage: null,
  trustVersion: null,
  auditCount: null,
  nextHeadline: "",
  nextDetail: "",
  nextActionLabel: null as string | null,
  onNextAction: vi.fn(),
  busy: false,
  workflow: null,
  aside: null,
  onGoTo: vi.fn(),
  missionControl: null,
};

describe("WorkspacePage", () => {
  it("renders the empty unauthenticated workspace without throwing", () => {
    render(<WorkspacePage {...emptyProps} />);
    expect(screen.getByText("Nothing is waiting on you.")).toBeInTheDocument();
    expect(screen.getByText("No dated opportunities yet.")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /your organization/i })).toBeInTheDocument();
  });
});
