export type ThemeId =
  | "dark"
  | "solarized-dark"
  | "light"
  | "solarized-light"
  | "black";

export type ThemeTokenKey =
  | "bg"
  | "panel"
  | "panelHover"
  | "border"
  | "text"
  | "textMuted"
  | "accent"
  | "accentHover"
  | "error"
  | "sidebar"
  | "danger";

export type ThemeTokens = Record<ThemeTokenKey, string>;

export type ThemeOverrideKey = "bg" | "panel" | "text" | "textMuted" | "accent";

export type ThemeOverrides = Partial<Record<ThemeOverrideKey, string>>;

export interface ThemePreset {
  id: ThemeId;
  label: string;
  tokens: ThemeTokens;
  colorScheme: "dark" | "light";
}

const CSS_VAR_MAP: Record<ThemeTokenKey, string> = {
  bg: "--bg",
  panel: "--panel",
  panelHover: "--panel-hover",
  border: "--border",
  text: "--text",
  textMuted: "--text-muted",
  accent: "--accent",
  accentHover: "--accent-hover",
  error: "--error",
  sidebar: "--sidebar",
  danger: "--danger",
};

const OVERRIDE_CSS_VAR_MAP: Record<ThemeOverrideKey, string> = {
  bg: "--bg",
  panel: "--panel",
  text: "--text",
  textMuted: "--text-muted",
  accent: "--accent",
};

export const THEME_STORAGE_KEY = "theplan.theme";
export const OVERRIDES_STORAGE_KEY = "theplan.theme.overrides";
export const DEFAULT_THEME_ID: ThemeId = "dark";

export const THEME_PRESETS: ThemePreset[] = [
  {
    id: "dark",
    label: "Dark",
    colorScheme: "dark",
    tokens: {
      bg: "#0B0F19",
      panel: "#121827",
      panelHover: "#1A2236",
      border: "#2A3247",
      text: "#E6EAF2",
      textMuted: "#9AA4B2",
      accent: "#059669",
      accentHover: "#047857",
      error: "#F87171",
      sidebar: "#121827",
      danger: "#F87171",
    },
  },
  {
    id: "solarized-dark",
    label: "Solarized Dark",
    colorScheme: "dark",
    tokens: {
      bg: "#002B36",
      panel: "#073642",
      panelHover: "#0E4A57",
      border: "#2E5B66",
      text: "#DDE5D8",
      textMuted: "#93A1A1",
      accent: "#A57BD5",
      accentHover: "#8B5FC4",
      error: "#E34E80",
      sidebar: "#073642",
      danger: "#E34E80",
    },
  },
  {
    id: "light",
    label: "Light",
    colorScheme: "light",
    tokens: {
      bg: "#F5F7FB",
      panel: "#FFFFFF",
      panelHover: "#EDECF5",
      border: "#D8DEE9",
      text: "#1B2430",
      textMuted: "#5B6472",
      accent: "#8E5FC0",
      accentHover: "#6D3FA3",
      error: "#C90F56",
      sidebar: "#FFFFFF",
      danger: "#C90F56",
    },
  },
  {
    id: "solarized-light",
    label: "Solarized Light",
    colorScheme: "light",
    tokens: {
      bg: "#FDF6E3",
      panel: "#EEE8D5",
      panelHover: "#E5D9C0",
      border: "#D6CBB4",
      text: "#334155",
      textMuted: "#657B83",
      accent: "#7F53B3",
      accentHover: "#5B3A8C",
      error: "#B2185B",
      sidebar: "#EEE8D5",
      danger: "#B2185B",
    },
  },
  {
    id: "black",
    label: "Black",
    colorScheme: "dark",
    tokens: {
      bg: "#0A0A0C",
      panel: "#121214",
      panelHover: "#1A1A1E",
      border: "#28282C",
      text: "#E8E8EC",
      textMuted: "#888890",
      accent: "#C084FC",
      accentHover: "#A855F7",
      error: "#FB7185",
      sidebar: "#121214",
      danger: "#FB7185",
    },
  },
];

export const OVERRIDE_FIELDS: { key: ThemeOverrideKey; label: string }[] = [
  { key: "bg", label: "Background" },
  { key: "panel", label: "Panel" },
  { key: "text", label: "Text" },
  { key: "textMuted", label: "Muted text" },
  { key: "accent", label: "Accent" },
];

const presetById = new Map(THEME_PRESETS.map((preset) => [preset.id, preset]));

export function isThemeId(value: string | null): value is ThemeId {
  return value !== null && presetById.has(value as ThemeId);
}

export function getThemePreset(id: ThemeId): ThemePreset {
  return presetById.get(id)!;
}

export function loadTheme(): ThemeId {
  try {
    const stored = localStorage.getItem(THEME_STORAGE_KEY);
    if (isThemeId(stored)) return stored;
  } catch {
    /* ignore storage errors */
  }
  return DEFAULT_THEME_ID;
}

export function saveTheme(id: ThemeId): void {
  localStorage.setItem(THEME_STORAGE_KEY, id);
}

export function loadOverrides(): ThemeOverrides {
  try {
    const raw = localStorage.getItem(OVERRIDES_STORAGE_KEY);
    if (!raw) return {};
    const parsed = JSON.parse(raw) as unknown;
    if (!parsed || typeof parsed !== "object") return {};
    const result: ThemeOverrides = {};
    for (const field of OVERRIDE_FIELDS) {
      const value = (parsed as Record<string, unknown>)[field.key];
      if (typeof value === "string" && isValidHex(value)) {
        result[field.key] = normalizeHex(value);
      }
    }
    return result;
  } catch {
    return {};
  }
}

export function saveOverrides(overrides: ThemeOverrides): void {
  const cleaned: ThemeOverrides = {};
  for (const field of OVERRIDE_FIELDS) {
    const value = overrides[field.key];
    if (value && isValidHex(value)) {
      cleaned[field.key] = normalizeHex(value);
    }
  }
  if (Object.keys(cleaned).length === 0) {
    localStorage.removeItem(OVERRIDES_STORAGE_KEY);
    return;
  }
  localStorage.setItem(OVERRIDES_STORAGE_KEY, JSON.stringify(cleaned));
}

export function isValidHex(value: string): boolean {
  return /^#[0-9A-Fa-f]{6}$/.test(value.trim());
}

export function normalizeHex(value: string): string {
  return value.trim().toUpperCase();
}

function clearInlineThemeVars(): void {
  const root = document.documentElement.style;
  for (const cssVar of Object.values(CSS_VAR_MAP)) {
    root.removeProperty(cssVar);
  }
}

export function applyOverrides(overrides: ThemeOverrides = loadOverrides()): void {
  const root = document.documentElement.style;
  for (const field of OVERRIDE_FIELDS) {
    const cssVar = OVERRIDE_CSS_VAR_MAP[field.key];
    const value = overrides[field.key];
    if (value && isValidHex(value)) {
      root.setProperty(cssVar, normalizeHex(value));
    } else {
      root.removeProperty(cssVar);
    }
  }
}

export function applyTheme(id: ThemeId = loadTheme()): void {
  document.documentElement.setAttribute("data-theme", id);
  clearInlineThemeVars();
  applyOverrides();
}

export function resetOverrides(): ThemeOverrides {
  localStorage.removeItem(OVERRIDES_STORAGE_KEY);
  applyOverrides({});
  return {};
}

export function setTheme(id: ThemeId): void {
  saveTheme(id);
  applyTheme(id);
}

export function setOverride(key: ThemeOverrideKey, value: string | undefined): ThemeOverrides {
  const next = { ...loadOverrides() };
  if (value && isValidHex(value)) {
    next[key] = normalizeHex(value);
  } else {
    delete next[key];
  }
  saveOverrides(next);
  applyOverrides(next);
  return next;
}

export function initTheme(): void {
  applyTheme(loadTheme());
}

if (typeof document !== "undefined") {
  initTheme();
}
