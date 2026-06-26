/** URL/query helpers for Workspace vs Workbench vs Activation (M8). */

export type AppSurface = "workspace" | "workbench" | "activation";

export function readSurface(): AppSurface {
  try {
    const q = new URLSearchParams(window.location.search).get("view");
    if (q === "workbench") return "workbench";
    if (q === "activation") return "activation";
    return "workspace";
  } catch {
    return "workspace";
  }
}
