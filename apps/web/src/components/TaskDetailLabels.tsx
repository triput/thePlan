import { useMemo } from "react";
import type { Label } from "../api";
import { TaskDetailSection, type DetailSectionId } from "./TaskDetailSection";

interface TaskDetailLabelsProps {
  open: boolean;
  onToggle: (id: DetailSectionId) => void;
  allLabels: Label[];
  labelIds: string[];
  onToggleLabel: (labelId: string) => void;
  labelFilter: string;
  onLabelFilterChange: (value: string) => void;
  createPending: boolean;
  onCreateLabel: (name: string) => void;
}

export function TaskDetailLabels({
  open,
  onToggle,
  allLabels,
  labelIds,
  onToggleLabel,
  labelFilter,
  onLabelFilterChange,
  createPending,
  onCreateLabel,
}: TaskDetailLabelsProps) {
  const labelFilterTrimmed = labelFilter.trim();
  const labelFilterLower = labelFilterTrimmed.toLowerCase();
  const filteredLabels = useMemo(() => {
    if (!labelFilterLower) return allLabels;
    return allLabels.filter((label) => label.name.toLowerCase().includes(labelFilterLower));
  }, [allLabels, labelFilterLower]);
  const exactLabelMatch = useMemo(
    () => allLabels.some((label) => label.name.toLowerCase() === labelFilterLower),
    [allLabels, labelFilterLower],
  );
  const canCreateLabel = labelFilterTrimmed.length > 0 && !exactLabelMatch;

  return (
    <TaskDetailSection id="labels" title="Labels" open={open} onToggle={onToggle}>
      <fieldset className="field">
        <legend className="sr-only">Labels</legend>
        <label className="field label-filter-field">
          <span className="sr-only">Filter or create labels</span>
          <input
            type="text"
            value={labelFilter}
            onChange={(e) => onLabelFilterChange(e.target.value)}
            onKeyDown={(e) => {
              if (e.key !== "Enter") return;
              e.preventDefault();
              if (!canCreateLabel || createPending) return;
              onCreateLabel(labelFilterTrimmed);
            }}
            placeholder="Filter or create…"
            autoComplete="off"
          />
        </label>
        {allLabels.length === 0 && !canCreateLabel && (
          <p className="muted small">No labels yet. Type a name above to create one.</p>
        )}
        {allLabels.length > 0 && filteredLabels.length === 0 && !canCreateLabel && (
          <p className="muted small">No labels match.</p>
        )}
        <div className="label-toggle-group" role="group" aria-label="Task labels">
          {filteredLabels.map((label) => {
            const selected = labelIds.includes(label.id);
            return (
              <button
                key={label.id}
                type="button"
                className={`label-toggle${selected ? " selected" : ""}`}
                style={
                  selected
                    ? {
                        backgroundColor: `color-mix(in srgb, ${label.color_hex} 22%, transparent)`,
                        borderColor: label.color_hex,
                        color: label.color_hex,
                      }
                    : { borderColor: label.color_hex, color: label.color_hex }
                }
                aria-pressed={selected}
                onClick={() => onToggleLabel(label.id)}
              >
                <span
                  className="label-swatch tiny"
                  style={{ backgroundColor: label.color_hex }}
                  aria-hidden
                />
                {label.name}
              </button>
            );
          })}
          {canCreateLabel && (
            <button
              type="button"
              className="label-toggle label-create-toggle"
              disabled={createPending}
              onClick={() => onCreateLabel(labelFilterTrimmed)}
            >
              {createPending ? "Creating…" : `+ Create “${labelFilterTrimmed}”`}
            </button>
          )}
        </div>
      </fieldset>
    </TaskDetailSection>
  );
}
