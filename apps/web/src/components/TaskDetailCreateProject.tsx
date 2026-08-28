import type { FormEvent } from "react";
import type { Epic } from "../api";
import { Modal } from "./Modal";

interface TaskDetailCreateProjectProps {
  open: boolean;
  epics: Epic[];
  title: string;
  onTitleChange: (value: string) => void;
  epicId: string;
  onEpicIdChange: (value: string) => void;
  pending: boolean;
  errorMessage: string | null;
  onClose: () => void;
  onSubmit: (e: FormEvent) => void;
}

export function TaskDetailCreateProject({
  open,
  epics,
  title,
  onTitleChange,
  epicId,
  onEpicIdChange,
  pending,
  errorMessage,
  onClose,
  onSubmit,
}: TaskDetailCreateProjectProps) {
  return (
    <Modal
      open={open}
      title="New project"
      onClose={() => {
        if (pending) return;
        onClose();
      }}
    >
      <form className="entity-form" onSubmit={onSubmit}>
        <label className="field">
          <span>Title</span>
          <input
            type="text"
            value={title}
            onChange={(e) => onTitleChange(e.target.value)}
            placeholder="Project title"
            autoFocus
          />
        </label>
        <label className="field">
          <span>Epic</span>
          <select
            className="field-select"
            value={epicId}
            onChange={(e) => onEpicIdChange(e.target.value)}
          >
            <option value="">Standalone (no epic)</option>
            {epics.map((epic) => (
              <option key={epic.id} value={epic.id}>
                {epic.title}
              </option>
            ))}
          </select>
        </label>
        {errorMessage && <p className="form-error">{errorMessage}</p>}
        <div className="form-actions">
          <button type="button" className="btn secondary" onClick={onClose} disabled={pending}>
            Cancel
          </button>
          <button
            type="submit"
            className="btn primary"
            disabled={!title.trim() || pending}
          >
            {pending ? "Creating…" : "Create & select"}
          </button>
        </div>
      </form>
    </Modal>
  );
}
