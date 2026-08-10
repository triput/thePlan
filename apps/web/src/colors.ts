/** Entity color presets from docs/08-color-palette.md */
export const ENTITY_PRESETS = [
  { id: "teal", name: "Teal", hex: "#0A7A6E" },
  { id: "emerald", name: "Emerald", hex: "#0A8558" },
  { id: "mint", name: "Mint", hex: "#059669" },
  { id: "lime", name: "Lime", hex: "#4D7C0F" },
  { id: "azure", name: "Azure", hex: "#1668C4" },
  { id: "sky", name: "Sky", hex: "#0369A1" },
  { id: "indigo", name: "Indigo", hex: "#4556B8" },
  { id: "violet", name: "Violet", hex: "#6D3FC9" },
  { id: "grape", name: "Grape", hex: "#7C3AED" },
  { id: "orchid", name: "Orchid", hex: "#8E5FC0" },
  { id: "coral", name: "Coral", hex: "#C23144" },
  { id: "rose", name: "Rose", hex: "#BE185D" },
  { id: "amber", name: "Amber", hex: "#B45309" },
  { id: "terracotta", name: "Terracotta", hex: "#C2410C" },
  { id: "charcoal", name: "Charcoal", hex: "#635F75" },
  { id: "slate", name: "Slate", hex: "#64748B" },
] as const;

export const DEFAULT_EPIC_COLOR = "#6D3FC9";
export const DEFAULT_PROJECT_COLOR = "#0A8558";

/** Phronesis Hybrid Dark chrome */
export const CHROME = {
  bg: "#0B0F19",
  panel: "#121827",
  panelHover: "#1A2236",
  border: "#1E293B",
  text: "#E2E8F0",
  textMuted: "#94A3B8",
  accent: "#059669",
  accentHover: "#047857",
  error: "#F87171",
} as const;

export const PRIORITY_COLORS: Record<string, string> = {
  p1: "#C23144",
  p2: "#B45309",
  p3: "#1668C4",
  p4: "#635F75",
};
