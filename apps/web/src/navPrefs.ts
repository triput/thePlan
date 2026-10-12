export const NAV_COLLAPSED_STORAGE_KEY = "theplan.nav.collapsed";
export const NAV_SECTIONS_STORAGE_KEY = "theplan.nav.sections";

export type NavSectionId = "labels" | "epics" | "projects";

export type NavSectionCollapsed = Record<NavSectionId, boolean>;

const DEFAULT_NAV_SECTIONS: NavSectionCollapsed = {
  labels: false,
  epics: false,
  projects: false,
};

export function loadNavCollapsed(): boolean {
  try {
    return localStorage.getItem(NAV_COLLAPSED_STORAGE_KEY) === "1";
  } catch {
    return false;
  }
}

export function saveNavCollapsed(collapsed: boolean): void {
  try {
    localStorage.setItem(NAV_COLLAPSED_STORAGE_KEY, collapsed ? "1" : "0");
  } catch {
    /* ignore quota / private mode */
  }
}

export function loadNavSectionCollapsed(): NavSectionCollapsed {
  try {
    const raw = localStorage.getItem(NAV_SECTIONS_STORAGE_KEY);
    if (!raw) return { ...DEFAULT_NAV_SECTIONS };
    const parsed = JSON.parse(raw) as Partial<NavSectionCollapsed>;
    return {
      labels: Boolean(parsed.labels),
      epics: Boolean(parsed.epics),
      projects: Boolean(parsed.projects),
    };
  } catch {
    return { ...DEFAULT_NAV_SECTIONS };
  }
}

export function saveNavSectionCollapsed(state: NavSectionCollapsed): void {
  try {
    localStorage.setItem(NAV_SECTIONS_STORAGE_KEY, JSON.stringify(state));
  } catch {
    /* ignore quota / private mode */
  }
}
