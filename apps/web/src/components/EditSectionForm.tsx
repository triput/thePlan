import { useEffect, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { deleteSection, updateSection, type Section } from "../api";
import { ConfirmDialog } from "./ConfirmDialog";
import { Modal } from "./Modal";

interface EditSectionFormProps {
  section: Section | null;
  onClose: () => void;
}

export function EditSectionForm({ section, onClose }: EditSectionFormProps) {
  const [title, setTitle] = useState("");
  const [confirmDelete, setConfirmDelete] = useState(false);
  const queryClient = useQueryClient();

  useEffect(() => {
    if (section) setTitle(section.title);
  }, [section]);

  const invalidate = () => {
    if (section) {
      queryClient.invalidateQueries({ queryKey: ["sections", section.project_id] });
    }
    queryClient.invalidateQueries({ queryKey: ["tasks"] });
  };

  const updateMutation = useMutation({
    mutationFn: (newTitle: string) => updateSection(section!.id, { title: newTitle }),
    onSuccess: () => {
      invalidate();
      onClose();
    },
  });

  const deleteMutation = useMutation({
    mutationFn: () => deleteSection(section!.id),
    onSuccess: () => {
      invalidate();
      setConfirmDelete(false);
      onClose();
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = title.trim();
    if (!trimmed || !section) return;
    updateMutation.mutate(trimmed);
  };

  return (
    <>
      <Modal open={section !== null} title="Edit section" onClose={onClose}>
        <form className="entity-form" onSubmit={handleSubmit}>
          <label className="field">
            <span>Name</span>
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              autoFocus
            />
          </label>
          {updateMutation.isError && (
            <p className="form-error">{(updateMutation.error as Error).message}</p>
          )}
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
              Delete section
            </button>
          </div>
        </form>
      </Modal>

      <ConfirmDialog
        open={confirmDelete}
        title="Delete section?"
        message={`Delete "${section?.title}"? Tasks in this section keep their other fields.`}
        confirmLabel="Delete"
        destructive
        pending={deleteMutation.isPending}
        onClose={() => setConfirmDelete(false)}
        onConfirm={() => deleteMutation.mutate()}
      />
    </>
  );
}
