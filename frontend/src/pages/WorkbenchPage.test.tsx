import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { WorkbenchPage } from "./WorkbenchPage";

describe("WorkbenchPage", () => {
  it("renders heading when org is invalid (no network)", () => {
    render(<WorkbenchPage plane="demo" orgId="" orgOk={false} />);
    expect(
      screen.getByRole("heading", { name: /operator workbench/i }),
    ).toBeInTheDocument();
  });
});
