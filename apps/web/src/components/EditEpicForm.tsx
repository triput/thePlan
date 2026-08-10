import { useEffect, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { archiveEpic, deleteEpic, updateEpic, type Epic } from "../api";
import { ColorPicker } from "./ColorPicker";
import { ConfirmDialog } from "./ConfirmDialog";
import { Modal } from "./Modal";

interface EditEpicFormProps {
  epic: Epic | null;
  onClose: () => void;
}

export function EditEpicForm({ epic, onClose }: EditEpicFormProps) {
  const [title, setTitle] = useState("");
  const [colorHex, setColorHex] = useState("");
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [confirmArchive, setConfirmArchive] = useState(false);
  const queryClient = useQueryClient();

  useEffect(() => {
    if (epic) {
      setTitle(epic.title);
      setColorHex(epic.color_hex);
    }
  }, [epic]);

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ["epics"] });

  const updateMutation = useMutation({
    mutationFn: (body: { title: string; color_hex: string }) =>
      updateEpic(epic!.id, body),
    onSuccess: () => {
      invalidate();
      onClose();
    },
  });

  const archiveMutation = useMutation({
    mutationFn: () => archiveEpic(epic!.id),
    onSuccess: () => {
      invalidate();
      setConfirmArchive(false);
      onClose();
    },
  });

  const deleteMutation = useMutation({
    mutationFn: () => deleteEpic(epic!.id),
    onSuccess: () => {
      invalidate();
      queryClient.invalidateQueries({ queryKey: ["projects"] });
      setConfirmDelete(false);
      onClose();
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = title.trim();
    if (!trimmed || !epic) return;
    updateMutation.mutate({ title: trimmed, color_hex: colorHex });
  };

  const error = updateMutation.error ?? archiveMutation.error ?? deleteMutation.error;

  return (
    <>
      <Modal open={epic !== null} title="Edit epic" onClose={onClose}>
        <form className="entity-form" onSubmit={handleSubmit}>
          <label className="field">
            <span>Title</span>
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
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
              onClick={() => setConfirmArchive(true)}
            >
              Archive epic
            </button>
            <button
              type="button"
              className="btn ghost danger-text"
              onClick={() => setConfirmDelete(true)}
            >
              Delete epic
            </button>
          </div>
        </form>
      </Modal>

      <ConfirmDialog
        open={confirmArchive}
        title="Archive epic?"
        message={`Archive "${epic?.title}"? Projects inside stay but the epic hides from the sidebar.`}
        confirmLabel="Archive"
        pending={archiveMutation.isPending}
        onClose={() => setConfirmArchive(false)}
        onConfirm={() => archiveMutation.mutate()}
      />

      <ConfirmDialog
        open={confirmDelete}
        title="Delete epic?"
        message={`Permanently delete "${epic?.title}"? This cannot be undone.`}
        confirmLabel="Delete"
        destructive
        pending={deleteMutation.isPending}
        onClose={() => setConfirmDelete(false)}
        onConfirm={() => deleteMutation.mutate()}
      />
    </>
  );
}
