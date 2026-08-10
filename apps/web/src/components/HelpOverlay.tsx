import { Modal } from "./Modal";

interface HelpOverlayProps {
  open: boolean;
  onClose: () => void;
}

const SHORTCUTS: { keys: string; action: string }[] = [
  { keys: "Q or Ctrl+K", action: "Focus quick-add" },
  { keys: "/", action: "Focus search" },
  { keys: "Ctrl+Z", action: "Undo last action" },
  { keys: "J / K or ↑ / ↓", action: "Navigate tasks" },
  { keys: "Enter", action: "Open focused task" },
  { keys: "X or Space", action: "Complete or uncomplete task" },
  { keys: "?", action: "Toggle this help" },
  { keys: "Esc", action: "Close modals" },
];

export function HelpOverlay({ open, onClose }: HelpOverlayProps) {
  return (
    <Modal open={open} title="Keyboard shortcuts" onClose={onClose}>
      <dl className="help-shortcuts">
        {SHORTCUTS.map(({ keys, action }) => (
          <div key={keys} className="help-shortcut-row">
            <dt>
              <kbd className="help-kbd">{keys}</kbd>
            </dt>
            <dd>{action}</dd>
          </div>
        ))}
      </dl>
    </Modal>
  );
}
