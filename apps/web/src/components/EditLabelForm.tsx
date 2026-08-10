import { useEffect, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { deleteLabel, updateLabel, type Label } from "../api";
import { ColorPicker } from "./ColorPicker";
import { ConfirmDialog } from "./ConfirmDialog";
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
  const queryClient = useQueryClient();

  useEffect(() => {
    if (label) {
      setName(label.name);
      setColorHex(label.color_hex);
    }
  }, [label]);

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
    mutationFn: () => deleteLabel(label!.id),
    onSuccess: () => {
      invalidate();
      setConfirmDelete(false);
      onClose();
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = name.trim();
    if (!trimmed || !label) return;
    updateMutation.mutate({ name: trimmed.toLowerCase(), color_hex: colorHex });
  };

  const error = updateMutation.error ?? deleteMutation.error;
  const count = label?.task_count ?? taskCount;

  return (
    <>
      <Modal open={label !== null} title="Edit label" onClose={onClose}>
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
          {error && <p className="form-error">{(error as Error).message}</p>}
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

      <ConfirmDialog
        open={confirmDelete}
        title="Delete label?"
        message={`Permanently delete "${label?.name}"? Used on ${count} task${count === 1 ? "" : "s"}.`}
        confirmLabel="Delete"
        destructive
        pending={deleteMutation.isPending}
        onClose={() => setConfirmDelete(false)}
        onConfirm={() => deleteMutation.mutate()}
      />
    </>
  );
}
