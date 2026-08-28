interface TaskDetailPromoteProps {
  promotePending: boolean;
  onRequestPromote: () => void;
}

/** Promote button only — confirm dialog stays on TaskDetailPanel root (Modal is not portaled). */
export function TaskDetailPromote({
  promotePending,
  onRequestPromote,
}: TaskDetailPromoteProps) {
  return (
    <button
      type="button"
      className="btn secondary small"
      onClick={onRequestPromote}
      disabled={promotePending}
    >
      Promote to project
    </button>
  );
}
