/** URL/query helpers for Workspace vs Workbench vs Activation vs NM/WA demo. */

export type AppSurface =
  | "workspace"
  | "workbench"
  | "activation"
  | "nm_wa_operator_demo";

export function readSurface(): AppSurface {
  try {
    const q = new URLSearchParams(window.location.search).get("view");
    if (q === "workbench") return "workbench";
    if (q === "activation") return "activation";
    if (q === "nm_wa_operator_demo") return "nm_wa_operator_demo";
    return "workspace";
  } catch {
    return "workspace";
  }
}
