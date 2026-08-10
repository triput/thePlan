import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  createLabel,
  createLabelsBatch,
  fetchLabels,
  fetchTasks,
  type Label,
} from "../api";
import { DEFAULT_EPIC_COLOR } from "../colors";
import { ColorPicker } from "./ColorPicker";
import { EditLabelForm } from "./EditLabelForm";

export function LabelsManagement() {
  const queryClient = useQueryClient();
  const [singleName, setSingleName] = useState("");
  const [singleColor, setSingleColor] = useState(DEFAULT_EPIC_COLOR);
  const [batchText, setBatchText] = useState("");
  const [batchColor, setBatchColor] = useState(DEFAULT_EPIC_COLOR);
  const [editingLabel, setEditingLabel] = useState<Label | null>(null);

  const labelsQuery = useQuery({
    queryKey: ["labels"],
    queryFn: () => fetchLabels({ limit: 200 }),
  });

  const tasksQuery = useQuery({
    queryKey: ["tasks", "all-for-label-counts"],
    queryFn: () => fetchTasks({ limit: 200 }),
  });

  const taskCountByLabel = useMemo(() => {
    const counts = new Map<string, number>();
    for (const task of tasksQuery.data?.items ?? []) {
      for (const labelId of task.label_ids) {
        counts.set(labelId, (counts.get(labelId) ?? 0) + 1);
      }
    }
    return counts;
  }, [tasksQuery.data]);

  const labels = useMemo(() => {
    const items = labelsQuery.data?.items ?? [];
    return [...items].sort((a, b) => a.name.localeCompare(b.name));
  }, [labelsQuery.data]);

  const getTaskCount = (label: Label) =>
    label.task_count ?? taskCountByLabel.get(label.id) ?? 0;

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ["labels"] });
    queryClient.invalidateQueries({ queryKey: ["tasks"] });
  };

  const createSingleMutation = useMutation({
    mutationFn: () =>
      createLabel({ name: singleName.trim().toLowerCase(), color_hex: singleColor }),
    onSuccess: () => {
      invalidate();
      setSingleName("");
      setSingleColor(DEFAULT_EPIC_COLOR);
    },
  });

  const createBatchMutation = useMutation({
    mutationFn: async () => {
      const names = batchText
        .split("\n")
        .map((line) => line.trim().toLowerCase())
        .filter(Boolean);
      const bodies = names.map((name) => ({ name, color_hex: batchColor }));
      return createLabelsBatch(bodies);
    },
    onSuccess: () => {
      invalidate();
      setBatchText("");
      setBatchColor(DEFAULT_EPIC_COLOR);
    },
  });

  const handleCreateSingle = (e: React.FormEvent) => {
    e.preventDefault();
    if (!singleName.trim()) return;
    createSingleMutation.mutate();
  };

  const handleCreateBatch = (e: React.FormEvent) => {
    e.preventDefault();
    if (!batchText.trim()) return;
    createBatchMutation.mutate();
  };

  return (
    <div className="labels-management">
      <header className="pane-header">
        <h1>Labels</h1>
      </header>

      <section className="labels-section">
        <h2 className="labels-section-title">Create label</h2>
        <form className="entity-form labels-create-form" onSubmit={handleCreateSingle}>
          <label className="field">
            <span>Name</span>
            <input
              type="text"
              value={singleName}
              onChange={(e) => setSingleName(e.target.value)}
              placeholder="waiting"
            />
          </label>
          <fieldset className="field">
            <legend>Color</legend>
            <ColorPicker value={singleColor} onChange={setSingleColor} />
          </fieldset>
          {createSingleMutation.isError && (
            <p className="form-error">{(createSingleMutation.error as Error).message}</p>
          )}
          <div className="form-actions">
            <button
              type="submit"
              className="btn primary"
              disabled={createSingleMutation.isPending || !singleName.trim()}
            >
              {createSingleMutation.isPending ? "Creating…" : "Create label"}
            </button>
          </div>
        </form>
      </section>

      <section className="labels-section">
        <h2 className="labels-section-title">Create several</h2>
        <form className="entity-form labels-create-form" onSubmit={handleCreateBatch}>
          <label className="field">
            <span>Names (one per line)</span>
            <textarea
              className="field-textarea"
              value={batchText}
              onChange={(e) => setBatchText(e.target.value)}
              rows={4}
              placeholder={"waiting\nfocus\nblocked"}
            />
          </label>
          <fieldset className="field">
            <legend>Color for all</legend>
            <ColorPicker value={batchColor} onChange={setBatchColor} />
          </fieldset>
          {createBatchMutation.isError && (
            <p className="form-error">{(createBatchMutation.error as Error).message}</p>
          )}
          <div className="form-actions">
            <button
              type="submit"
              className="btn primary"
              disabled={createBatchMutation.isPending || !batchText.trim()}
            >
              {createBatchMutation.isPending ? "Creating…" : "Create labels"}
            </button>
          </div>
        </form>
      </section>

      <section className="labels-section">
        <h2 className="labels-section-title">All labels</h2>
        {labelsQuery.isLoading && <p className="muted">Loading labels…</p>}
        {labelsQuery.isError && (
          <p className="form-error">{(labelsQuery.error as Error).message}</p>
        )}
        {labels.length === 0 && !labelsQuery.isLoading && (
          <p className="empty-state">No labels yet. Create one above.</p>
        )}
        <ul className="labels-list" aria-label="All labels">
          {labels.map((label) => {
            const count = getTaskCount(label);
            return (
              <li key={label.id} className="label-row">
                <span
                  className="label-swatch"
                  style={{ backgroundColor: label.color_hex }}
                  aria-hidden
                />
                <span className="label-name">{label.name}</span>
                <span className="label-count muted">
                  {count} task{count === 1 ? "" : "s"}
                </span>
                <button
                  type="button"
                  className="icon-btn tiny"
                  title={`Edit ${label.name}`}
                  aria-label={`Edit ${label.name}`}
                  onClick={() => setEditingLabel(label)}
                >
                  ✎
                </button>
              </li>
            );
          })}
        </ul>
      </section>

      <EditLabelForm
        label={editingLabel}
        taskCount={editingLabel ? getTaskCount(editingLabel) : 0}
        onClose={() => setEditingLabel(null)}
      />
    </div>
  );
}
