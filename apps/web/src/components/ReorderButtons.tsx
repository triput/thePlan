interface ReorderButtonsProps {
  label: string;
  canMoveUp: boolean;
  canMoveDown: boolean;
  onMoveUp: () => void;
  onMoveDown: () => void;
  pending?: boolean;
  className?: string;
}

export function ReorderButtons({
  label,
  canMoveUp,
  canMoveDown,
  onMoveUp,
  onMoveDown,
  pending = false,
  className = "",
}: ReorderButtonsProps) {
  if (!canMoveUp && !canMoveDown) return null;

  return (
    <span className={`reorder-btns${className ? ` ${className}` : ""}`}>
      <button
        type="button"
        className="icon-btn tiny reorder-btn"
        disabled={!canMoveUp || pending}
        aria-label={`Move ${label} up`}
        title="Move up"
        onClick={(e) => {
          e.stopPropagation();
          onMoveUp();
        }}
      >
        ↑
      </button>
      <button
        type="button"
        className="icon-btn tiny reorder-btn"
        disabled={!canMoveDown || pending}
        aria-label={`Move ${label} down`}
        title="Move down"
        onClick={(e) => {
          e.stopPropagation();
          onMoveDown();
        }}
      >
        ↓
      </button>
    </span>
  );
}
