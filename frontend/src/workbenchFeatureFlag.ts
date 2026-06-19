/** Stage 11 operator workbench feature flag — query param or localStorage. */

const LS_KEY = "nf-workbench-enabled";

export function readWorkbenchFlag(): boolean {
  try {
    const q = new URLSearchParams(window.location.search).get("nf_workbench");
    if (q === "1" || q === "true") {
      return true;
    }
    if (q === "0" || q === "false") {
      return false;
    }
    return localStorage.getItem(LS_KEY) === "1";
  } catch {
    return false;
  }
}

export function setWorkbenchFlag(enabled: boolean): void {
  try {
    localStorage.setItem(LS_KEY, enabled ? "1" : "0");
  } catch {
    /* ignore */
  }
}

export function workbenchQueryParam(): string {
  return readWorkbenchFlag() ? "true" : "false";
}
