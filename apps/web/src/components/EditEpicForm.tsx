import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  archiveEpic,
  deleteEpic,
  fetchFocusWindows,
  updateEpic,
  type Epic,
  type FocusWindow,
  type ScheduleStyle,
} from "../api";
import { ColorPicker } from "./ColorPicker";
import { ConfirmDialog } from "./ConfirmDialog";
import { Modal } from "./Modal";

interface EditEpicFormProps {
  epic: Epic | null;
  onClose: () => void;
}

export function EditEpicForm({ epic, onClose }: EditEpicFormProps) {
  const [title, setTitle] = useState("");
  const [colorHex, setColorHex] = useState("");
  const [preferredTimeWindowId, setPreferredTimeWindowId] = useState("");
  const [scheduleStyle, setScheduleStyle] = useState<"" | ScheduleStyle>("");
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [confirmArchive, setConfirmArchive] = useState(false);
  const queryClient = useQueryClient();

  const focusWindowsQuery = useQuery({
    queryKey: ["focus-windows"],
    queryFn: fetchFocusWindows,
    enabled: epic !== null,
  });
  const focusWindows: FocusWindow[] = focusWindowsQuery.data ?? [];

  useEffect(() => {
    if (epic) {
      setTitle(epic.title);
      setColorHex(epic.color_hex);
      setPreferredTimeWindowId(epic.preferred_time_window_id ?? "");
      setScheduleStyle(epic.schedule_style ?? "");
    }
  }, [epic]);

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ["epics"] });

  const updateMutation = useMutation({
    mutationFn: (body: {
      title: string;
      color_hex: string;
      preferred_time_window_id: string | null;
      schedule_style: ScheduleStyle | null;
    }) => updateEpic(epic!.id, body),
    onSuccess: () => {
      invalidate();
      onClose();
    },
  });

  const archiveMutation = useMutation({
    mutationFn: () => archiveEpic(epic!.id),
    onSuccess: () => {
      invalidate();
      setConfirmArchive(false);
      onClose();
    },
  });

  const deleteMutation = useMutation({
    mutationFn: () => deleteEpic(epic!.id),
    onSuccess: () => {
      invalidate();
      queryClient.invalidateQueries({ queryKey: ["projects"] });
      setConfirmDelete(false);
      onClose();
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = title.trim();
    if (!trimmed || !epic) return;
    updateMutation.mutate({
      title: trimmed,
      color_hex: colorHex,
      preferred_time_window_id: preferredTimeWindowId || null,
      schedule_style: scheduleStyle || null,
    });
  };

  const error = updateMutation.error ?? archiveMutation.error ?? deleteMutation.error;

  return (
    <>
      <Modal open={epic !== null} title="Edit epic" onClose={onClose}>
        <form className="entity-form" onSubmit={handleSubmit}>
          <label className="field">
            <span>Title</span>
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
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
          {error && <p className="form-error">{(error as Error).message}</p>}
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
              onClick={() => setConfirmArchive(true)}
            >
              Archive epic
            </button>
            <button
              type="button"
              className="btn ghost danger-text"
              onClick={() => setConfirmDelete(true)}
            >
              Delete epic
            </button>
          </div>
        </form>
      </Modal>

      <ConfirmDialog
        open={confirmArchive}
        title="Archive epic?"
        message={`Archive "${epic?.title}"? Projects inside stay but the epic hides from the sidebar.`}
        confirmLabel="Archive"
        pending={archiveMutation.isPending}
        onClose={() => setConfirmArchive(false)}
        onConfirm={() => archiveMutation.mutate()}
      />

      <ConfirmDialog
        open={confirmDelete}
        title="Delete epic?"
        message={`Permanently delete "${epic?.title}"? This cannot be undone.`}
        confirmLabel="Delete"
        destructive
        pending={deleteMutation.isPending}
        onClose={() => setConfirmDelete(false)}
        onConfirm={() => deleteMutation.mutate()}
      />
    </>
  );
}
