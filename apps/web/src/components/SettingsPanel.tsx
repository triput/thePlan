import { useEffect, useState } from "react";
import {
  getThemePreset,
  isValidHex,
  loadOverrides,
  loadTheme,
  normalizeHex,
  OVERRIDE_FIELDS,
  resetOverrides,
  setOverride,
  setTheme,
  THEME_PRESETS,
  type ThemeId,
  type ThemeOverrideKey,
  type ThemeOverrides,
} from "../theme";
import { Modal } from "./Modal";

interface SettingsPanelProps {
  open: boolean;
  onClose: () => void;
}

function effectiveColor(
  themeId: ThemeId,
  key: ThemeOverrideKey,
  overrides: ThemeOverrides,
): string {
  const override = overrides[key];
  if (override) return override;
  const preset = getThemePreset(themeId);
  if (key === "textMuted") return preset.tokens.textMuted;
  return preset.tokens[key];
}

export function SettingsPanel({ open, onClose }: SettingsPanelProps) {
  const [themeId, setThemeId] = useState<ThemeId>(() => loadTheme());
  const [overrides, setOverrides] = useState<ThemeOverrides>(() => loadOverrides());
  const [draftHex, setDraftHex] = useState<Record<ThemeOverrideKey, string>>(() =>
    buildDraftHex(loadOverrides()),
  );

  useEffect(() => {
    if (!open) return;
    const currentTheme = loadTheme();
    const currentOverrides = loadOverrides();
    setThemeId(currentTheme);
    setOverrides(currentOverrides);
    setDraftHex(buildDraftHex(currentOverrides));
  }, [open]);

  const handleThemeChange = (id: ThemeId) => {
    setThemeId(id);
    setTheme(id);
    setDraftHex(buildDraftHex(overrides));
  };

  const handleOverrideInput = (key: ThemeOverrideKey, raw: string) => {
    setDraftHex((prev) => ({ ...prev, [key]: raw }));
    if (isValidHex(raw)) {
      const normalized = normalizeHex(raw);
      const next = setOverride(key, normalized);
      setOverrides(next);
    } else if (raw.trim() === "") {
      const next = setOverride(key, undefined);
      setOverrides(next);
      setDraftHex(buildDraftHex(next));
    }
  };

  const handleResetOverrides = () => {
    const next = resetOverrides();
    setOverrides(next);
    setDraftHex(buildDraftHex(next));
  };

  return (
    <Modal open={open} title="Settings" onClose={onClose}>
      <section className="settings-section">
        <h3 className="settings-section-title">Theme</h3>
        <div className="theme-preset-list" role="radiogroup" aria-label="Theme preset">
          {THEME_PRESETS.map((preset) => (
            <label key={preset.id} className="theme-preset-option">
              <input
                type="radio"
                name="theme-preset"
                value={preset.id}
                checked={themeId === preset.id}
                onChange={() => handleThemeChange(preset.id)}
              />
              <span className="theme-preset-swatch" aria-hidden>
                <span style={{ backgroundColor: preset.tokens.bg }} />
                <span style={{ backgroundColor: preset.tokens.panel }} />
                <span style={{ backgroundColor: preset.tokens.accent }} />
              </span>
              <span className="theme-preset-label">{preset.label}</span>
            </label>
          ))}
        </div>
      </section>

      <section className="settings-section">
        <div className="settings-section-header">
          <h3 className="settings-section-title">Custom colors</h3>
          <button
            type="button"
            className="link-btn"
            onClick={handleResetOverrides}
            disabled={Object.keys(overrides).length === 0}
          >
            Reset overrides
          </button>
        </div>
        <p className="settings-help muted small">
          Optional hex overrides for the selected preset. Leave blank to use preset values.
        </p>
        <div className="theme-override-list">
          {OVERRIDE_FIELDS.map((field) => {
            const value = draftHex[field.key];
            const preset = getThemePreset(themeId);
            const presetValue =
              field.key === "textMuted" ? preset.tokens.textMuted : preset.tokens[field.key];
            const resolved = effectiveColor(themeId, field.key, overrides);
            const invalid = value.trim() !== "" && !isValidHex(value);
            return (
              <label key={field.key} className="theme-override-row">
                <span className="theme-override-label">{field.label}</span>
                <span
                  className="theme-override-swatch"
                  style={{ backgroundColor: resolved }}
                  aria-hidden
                />
                <input
                  type="text"
                  className="theme-override-input"
                  value={value}
                  onChange={(e) => handleOverrideInput(field.key, e.target.value)}
                  placeholder={presetValue}
                  spellCheck={false}
                  autoComplete="off"
                  aria-invalid={invalid}
                />
              </label>
            );
          })}
        </div>
      </section>
    </Modal>
  );
}

function buildDraftHex(overrides: ThemeOverrides): Record<ThemeOverrideKey, string> {
  return OVERRIDE_FIELDS.reduce(
    (acc, field) => {
      acc[field.key] = overrides[field.key] ?? "";
      return acc;
    },
    {} as Record<ThemeOverrideKey, string>,
  );
}
