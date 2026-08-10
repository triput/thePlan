import { ENTITY_PRESETS } from "../colors";

interface ColorPickerProps {
  value: string;
  onChange: (hex: string) => void;
}

export function ColorPicker({ value, onChange }: ColorPickerProps) {
  return (
    <div className="color-picker" role="radiogroup" aria-label="Color">
      {ENTITY_PRESETS.map((preset) => (
        <button
          key={preset.id}
          type="button"
          role="radio"
          aria-checked={value === preset.hex}
          aria-label={preset.name}
          className={`color-swatch${value === preset.hex ? " selected" : ""}`}
          style={{ backgroundColor: preset.hex }}
          onClick={() => onChange(preset.hex)}
        />
      ))}
    </div>
  );
}
