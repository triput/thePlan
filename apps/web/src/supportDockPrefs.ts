export const SUPPORT_DOCK_COLLAPSED_STORAGE_KEY = "theplan.support.collapsed";

export function loadSupportDockCollapsed(): boolean {
  try {
    return localStorage.getItem(SUPPORT_DOCK_COLLAPSED_STORAGE_KEY) === "1";
  } catch {
    return false;
  }
}

export function saveSupportDockCollapsed(collapsed: boolean): void {
  try {
    localStorage.setItem(SUPPORT_DOCK_COLLAPSED_STORAGE_KEY, collapsed ? "1" : "0");
  } catch {
    /* ignore quota / private mode */
  }
}
