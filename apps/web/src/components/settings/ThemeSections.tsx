/**
 * Settings — theme preset + custom color override sections.
 * Local theme storage only; parent holds shared themeId/overrides across the
 * Scheduling defaults gap in the settings scroll order.
 */
import {
  getThemePreset,
  isValidHex,
  OVERRIDE_FIELDS,
  THEME_PRESETS,
  type ThemeId,
  type ThemeOverrideKey,
  type ThemeOverrides,
} from "../../theme";

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

export function buildDraftHex(overrides: ThemeOverrides): Record<ThemeOverrideKey, string> {
  return OVERRIDE_FIELDS.reduce(
    (acc, field) => {
      acc[field.key] = overrides[field.key] ?? "";
      return acc;
    },
    {} as Record<ThemeOverrideKey, string>,
  );
}

export function ThemePresetSection({
  themeId,
  onThemeChange,
}: {
  themeId: ThemeId;
  onThemeChange: (id: ThemeId) => void;
}) {
  return (
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
              onChange={() => onThemeChange(preset.id)}
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
  );
}

export function CustomColorsSection({
  themeId,
  overrides,
  draftHex,
  onOverrideInput,
  onResetOverrides,
}: {
  themeId: ThemeId;
  overrides: ThemeOverrides;
  draftHex: Record<ThemeOverrideKey, string>;
  onOverrideInput: (key: ThemeOverrideKey, raw: string) => void;
  onResetOverrides: () => void;
}) {
  return (
    <section className="settings-section">
      <div className="settings-section-header">
        <h3 className="settings-section-title">Custom colors</h3>
        <button
          type="button"
          className="link-btn"
          onClick={onResetOverrides}
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
                onChange={(e) => onOverrideInput(field.key, e.target.value)}
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
  );
}
