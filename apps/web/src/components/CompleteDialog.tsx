import { Modal } from "./Modal";

interface CompleteDialogProps {
  open: boolean;
  taskTitle: string;
  openCount: number;
  onClose: () => void;
  onParentOnly: () => void;
  onBulkChildren: () => void;
  pending?: boolean;
}

export function CompleteDialog({
  open,
  taskTitle,
  openCount,
  onClose,
  onParentOnly,
  onBulkChildren,
  pending,
}: CompleteDialogProps) {
  return (
    <Modal open={open} title="Complete with open subtasks?" onClose={onClose}>
      <p className="dialog-text">
        <strong>{taskTitle}</strong> has {openCount} open subtask
        {openCount === 1 ? "" : "s"}. How should they be handled?
      </p>
      <div className="form-actions stacked">
        <button
          type="button"
          className="btn primary"
          onClick={onParentOnly}
          disabled={pending}
        >
          Complete parent only
        </button>
        <button
          type="button"
          className="btn secondary"
          onClick={onBulkChildren}
          disabled={pending}
        >
          Complete all children too
        </button>
        <button type="button" className="btn ghost" onClick={onClose} disabled={pending}>
          Cancel
        </button>
      </div>
    </Modal>
  );
}
