import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { createProject } from "../api";
import { DEFAULT_PROJECT_COLOR } from "../colors";
import { ColorPicker } from "./ColorPicker";
import { Modal } from "./Modal";

interface CreateProjectFormProps {
  open: boolean;
  epicId: string | null;
  onClose: () => void;
}

export function CreateProjectForm({ open, epicId, onClose }: CreateProjectFormProps) {
  const [title, setTitle] = useState("");
  const [colorHex, setColorHex] = useState(DEFAULT_PROJECT_COLOR);
  const queryClient = useQueryClient();

  const mutation = useMutation({
    mutationFn: createProject,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["projects"] });
      setTitle("");
      setColorHex(DEFAULT_PROJECT_COLOR);
      onClose();
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = title.trim();
    if (!trimmed) return;
    mutation.mutate({
      title: trimmed,
      epic_id: epicId,
      color_hex: colorHex,
    });
  };

  return (
    <Modal open={open} title={epicId ? "New project in epic" : "New standalone project"} onClose={onClose}>
      <form className="entity-form" onSubmit={handleSubmit}>
        <label className="field">
          <span>Title</span>
          <input
            type="text"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="Backend refactor"
            autoFocus
          />
        </label>
        <fieldset className="field">
          <legend>Color</legend>
          <ColorPicker value={colorHex} onChange={setColorHex} />
        </fieldset>
        {mutation.isError && (
          <p className="form-error">{(mutation.error as Error).message}</p>
        )}
        <div className="form-actions">
          <button type="button" className="btn secondary" onClick={onClose}>
            Cancel
          </button>
          <button type="submit" className="btn primary" disabled={mutation.isPending}>
            {mutation.isPending ? "Creating…" : "Create project"}
          </button>
        </div>
      </form>
    </Modal>
  );
}
