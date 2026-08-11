import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { deleteLabel, fetchLabels, updateLabel, type Label } from "../api";
import { ColorPicker } from "./ColorPicker";
import { Modal } from "./Modal";

interface EditLabelFormProps {
  label: Label | null;
  taskCount?: number;
  onClose: () => void;
}

export function EditLabelForm({ label, taskCount = 0, onClose }: EditLabelFormProps) {
  const [name, setName] = useState("");
  const [colorHex, setColorHex] = useState("");
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [reassignTo, setReassignTo] = useState<string[]>([]);
  const queryClient = useQueryClient();

  useEffect(() => {
    if (label) {
      setName(label.name);
      setColorHex(label.color_hex);
      setConfirmDelete(false);
      setReassignTo([]);
    }
  }, [label]);

  const labelsQuery = useQuery({
    queryKey: ["labels"],
    queryFn: () => fetchLabels({ limit: 200 }),
    enabled: confirmDelete && label != null,
  });

  const otherLabels = useMemo(() => {
    if (!label) return [];
    return (labelsQuery.data?.items ?? [])
      .filter((item) => item.id !== label.id)
      .sort((a, b) => a.name.localeCompare(b.name));
  }, [labelsQuery.data, label]);

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ["labels"] });
    queryClient.invalidateQueries({ queryKey: ["tasks"] });
  };

  const updateMutation = useMutation({
    mutationFn: (body: { name: string; color_hex: string }) =>
      updateLabel(label!.id, body),
    onSuccess: () => {
      invalidate();
      onClose();
    },
  });

  const deleteMutation = useMutation({
    mutationFn: () =>
      deleteLabel(label!.id, reassignTo.length > 0 ? { reassign_to: reassignTo } : {}),
    onSuccess: () => {
      invalidate();
      setConfirmDelete(false);
      setReassignTo([]);
      onClose();
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = name.trim();
    if (!trimmed || !label) return;
    updateMutation.mutate({ name: trimmed.toLowerCase(), color_hex: colorHex });
  };

  const toggleReassign = (id: string) => {
    setReassignTo((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id],
    );
  };

  const error = updateMutation.error ?? deleteMutation.error;
  const count = label?.task_count ?? taskCount;

  return (
    <>
      <Modal open={label !== null && !confirmDelete} title="Edit label" onClose={onClose}>
        <form className="entity-form" onSubmit={handleSubmit}>
          <label className="field">
            <span>Name</span>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              autoFocus
            />
          </label>
          <fieldset className="field">
            <legend>Color</legend>
            <ColorPicker value={colorHex} onChange={setColorHex} />
          </fieldset>
          {error && !confirmDelete && <p className="form-error">{(error as Error).message}</p>}
          <div className="form-actions">
            <button type="button" className="btn secondary" onClick={onClose}>
              Cancel
            </button>
            <button type="submit" className="btn primary" disabled={updateMutation.isPending}>
              {updateMutation.isPending ? "Saving…" : "Save"}
            </button>
          </div>
          <div className="form-actions destructive-row">
            <button
              type="button"
              className="btn ghost danger-text"
              onClick={() => setConfirmDelete(true)}
            >
              Delete label
            </button>
          </div>
        </form>
      </Modal>

      <Modal
        open={confirmDelete && label !== null}
        title="Delete label?"
        onClose={() => {
          if (deleteMutation.isPending) return;
          setConfirmDelete(false);
          setReassignTo([]);
        }}
      >
        <p className="dialog-text">
          Permanently delete &ldquo;{label?.name}&rdquo;? Used on {count} task
          {count === 1 ? "" : "s"}.
        </p>
        {count > 0 && (
          <fieldset className="field label-reassign-fieldset">
            <legend>Also apply to affected tasks (optional)</legend>
            {otherLabels.length === 0 ? (
              <p className="muted small">No other labels to reassign to.</p>
            ) : (
              <ul className="label-reassign-list">
                {otherLabels.map((item) => (
                  <li key={item.id}>
                    <label className="label-reassign-option">
                      <input
                        type="checkbox"
                        checked={reassignTo.includes(item.id)}
                        onChange={() => toggleReassign(item.id)}
                      />
                      <span
                        className="label-swatch"
                        style={{ backgroundColor: item.color_hex }}
                        aria-hidden
                      />
                      <span>{item.name}</span>
                    </label>
                  </li>
                ))}
              </ul>
            )}
          </fieldset>
        )}
        {deleteMutation.error && (
          <p className="form-error">{(deleteMutation.error as Error).message}</p>
        )}
        <div className="form-actions">
          <button
            type="button"
            className="btn secondary"
            disabled={deleteMutation.isPending}
            onClick={() => {
              setConfirmDelete(false);
              setReassignTo([]);
            }}
          >
            Cancel
          </button>
          <button
            type="button"
            className="btn danger"
            disabled={deleteMutation.isPending}
            onClick={() => deleteMutation.mutate()}
          >
            {deleteMutation.isPending ? "Working…" : "Delete"}
          </button>
        </div>
      </Modal>
    </>
  );
}
