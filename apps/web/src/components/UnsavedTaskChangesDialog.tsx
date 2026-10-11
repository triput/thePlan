import type { DirtyPromptCopy } from "../supportDockState";
import { Modal } from "./Modal";

interface UnsavedTaskChangesDialogProps {
  open: boolean;
  copy: DirtyPromptCopy;
  pending?: boolean;
  onCancel: () => void;
  onDiscard: () => void;
  onSave: () => void;
}

export function UnsavedTaskChangesDialog({
  open,
  copy,
  pending,
  onCancel,
  onDiscard,
  onSave,
}: UnsavedTaskChangesDialogProps) {
  return (
    <Modal open={open} title={copy.title} onClose={onCancel}>
      <p className="dialog-text">{copy.message}</p>
      <div className="form-actions unsaved-task-actions">
        <button type="button" className="btn secondary" onClick={onCancel} disabled={pending}>
          Cancel
        </button>
        <button type="button" className="btn ghost" onClick={onDiscard} disabled={pending}>
          {copy.discardLabel}
        </button>
        <button type="button" className="btn primary" onClick={onSave} disabled={pending}>
          {pending ? "Saving…" : copy.saveLabel}
        </button>
      </div>
    </Modal>
  );
}
