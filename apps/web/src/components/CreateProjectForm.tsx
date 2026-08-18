import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createProject, fetchFocusWindows, type FocusWindow, type ScheduleStyle } from "../api";
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
  const [preferredTimeWindowId, setPreferredTimeWindowId] = useState("");
  const [scheduleStyle, setScheduleStyle] = useState<"" | ScheduleStyle>("");
  const queryClient = useQueryClient();

  const focusWindowsQuery = useQuery({
    queryKey: ["focus-windows"],
    queryFn: fetchFocusWindows,
    enabled: open,
  });
  const focusWindows: FocusWindow[] = focusWindowsQuery.data ?? [];

  const mutation = useMutation({
    mutationFn: createProject,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["projects"] });
      setTitle("");
      setColorHex(DEFAULT_PROJECT_COLOR);
      setPreferredTimeWindowId("");
      setScheduleStyle("");
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
      preferred_time_window_id: preferredTimeWindowId || null,
      schedule_style: scheduleStyle || null,
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
        <label className="field">
          <span>Schedule style</span>
          <select
            className="field-select"
            value={scheduleStyle}
            onChange={(e) => setScheduleStyle(e.target.value as "" | ScheduleStyle)}
          >
            <option value="">Inherit</option>
            <option value="standalone">Standalone</option>
            <option value="time_block">Time block</option>
            <option value="bundle">Bundle</option>
            <option value="manual">Manual / backlog</option>
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
            {mutation.isPending ? "Creating…" : "Create project"}
          </button>
        </div>
      </form>
    </Modal>
  );
}
