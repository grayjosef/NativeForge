/** URL/query helpers for switching Workspace vs Operator Workbench (Sprint 21+). */

export type AppSurface = "workspace" | "workbench";

export function readSurface(): AppSurface {
  try {
    const q = new URLSearchParams(window.location.search).get("view");
    return q === "workbench" ? "workbench" : "workspace";
  } catch {
    return "workspace";
  }
}
