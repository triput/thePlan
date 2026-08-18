import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createEpic, fetchFocusWindows, type FocusWindow } from "../api";
import { DEFAULT_EPIC_COLOR } from "../colors";
import { ColorPicker } from "./ColorPicker";
import { Modal } from "./Modal";

interface CreateEpicFormProps {
  open: boolean;
  onClose: () => void;
}

export function CreateEpicForm({ open, onClose }: CreateEpicFormProps) {
  const [title, setTitle] = useState("");
  const [colorHex, setColorHex] = useState(DEFAULT_EPIC_COLOR);
  const [preferredTimeWindowId, setPreferredTimeWindowId] = useState("");
  const queryClient = useQueryClient();

  const focusWindowsQuery = useQuery({
    queryKey: ["focus-windows"],
    queryFn: fetchFocusWindows,
    enabled: open,
  });
  const focusWindows: FocusWindow[] = focusWindowsQuery.data ?? [];

  const mutation = useMutation({
    mutationFn: createEpic,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["epics"] });
      setTitle("");
      setColorHex(DEFAULT_EPIC_COLOR);
      setPreferredTimeWindowId("");
      onClose();
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = title.trim();
    if (!trimmed) return;
    mutation.mutate({
      title: trimmed,
      color_hex: colorHex,
      preferred_time_window_id: preferredTimeWindowId || null,
    });
  };

  return (
    <Modal open={open} title="New epic" onClose={onClose}>
      <form className="entity-form" onSubmit={handleSubmit}>
        <label className="field">
          <span>Title</span>
          <input
            type="text"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="Q3 Infrastructure"
            autoFocus
          />
        </label>
        <fieldset className="field">
          <legend>Color</legend>
          <ColorPicker value={colorHex} onChange={setColorHex} />
        </fieldset>
        <label className="field">
          <span>Time Map</span>
          <select
            className="field-select"
            value={preferredTimeWindowId}
            onChange={(e) => setPreferredTimeWindowId(e.target.value)}
          >
            <option value="">None</option>
            {focusWindows.map((window) => (
              <option key={window.id} value={window.id}>
                {window.name}
              </option>
            ))}
          </select>
        </label>
        {mutation.isError && (
          <p className="form-error">{(mutation.error as Error).message}</p>
        )}
        <div className="form-actions">
          <button type="button" className="btn secondary" onClick={onClose}>
            Cancel
          </button>
          <button type="submit" className="btn primary" disabled={mutation.isPending}>
            {mutation.isPending ? "Creating…" : "Create epic"}
          </button>
        </div>
      </form>
    </Modal>
  );
}