import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  archiveProject,
  deleteProject,
  fetchEpics,
  fetchFocusWindows,
  promoteProjectToEpic,
  updateProject,
  type FocusWindow,
  type Project,
  type ScheduleStyle,
} from "../api";
import { ColorPicker } from "./ColorPicker";
import { ConfirmDialog } from "./ConfirmDialog";
import { Modal } from "./Modal";
import type { ViewSelection } from "../view";

interface EditProjectFormProps {
  project: Project | null;
  onClose: () => void;
  view: ViewSelection;
  onSelectView: (view: ViewSelection) => void;
}

export function EditProjectForm({ project, onClose, view, onSelectView }: EditProjectFormProps) {
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [colorHex, setColorHex] = useState("");
  const [epicId, setEpicId] = useState<string | "">("");
  const [preferredTimeWindowId, setPreferredTimeWindowId] = useState("");
  const [scheduleStyle, setScheduleStyle] = useState<"" | ScheduleStyle>("");
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [confirmArchive, setConfirmArchive] = useState(false);
  const [confirmPromote, setConfirmPromote] = useState(false);
  const queryClient = useQueryClient();

  const epicsQuery = useQuery({ queryKey: ["epics"], queryFn: () => fetchEpics() });
  const epics = epicsQuery.data?.items ?? [];

  const focusWindowsQuery = useQuery({
    queryKey: ["focus-windows"],
    queryFn: fetchFocusWindows,
    enabled: project !== null,
  });
  const focusWindows: FocusWindow[] = focusWindowsQuery.data ?? [];

  useEffect(() => {
    if (project) {
      setTitle(project.title);
      setDescription(project.description ?? "");
      setColorHex(project.color_hex);
      setEpicId(project.epic_id ?? "");
      setPreferredTimeWindowId(project.preferred_time_window_id ?? "");
      setScheduleStyle(project.schedule_style ?? "");
    }
  }, [project]);

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ["projects"] });
    queryClient.invalidateQueries({ queryKey: ["epics"] });
    queryClient.invalidateQueries({ queryKey: ["tasks"] });
  };

  const updateMutation = useMutation({
    mutationFn: (body: {
      title: string;
      description: string | null;
      color_hex: string;
      epic_id: string | null;
      preferred_time_window_id: string | null;
      schedule_style: ScheduleStyle | null;
    }) => updateProject(project!.id, body),
    onSuccess: () => {
      invalidate();
      onClose();
    },
  });

  const archiveMutation = useMutation({
    mutationFn: () => archiveProject(project!.id),
    onSuccess: () => {
      invalidate();
      if (view.type === "project" && view.projectId === project?.id) {
        onSelectView({ type: "inbox" });
      }
      setConfirmArchive(false);
      onClose();
    },
  });

  const deleteMutation = useMutation({
    mutationFn: () => deleteProject(project!.id),
    onSuccess: () => {
      invalidate();
      if (view.type === "project" && view.projectId === project?.id) {
        onSelectView({ type: "inbox" });
      }
      setConfirmDelete(false);
      onClose();
    },
  });

  const promoteMutation = useMutation({
    mutationFn: () => promoteProjectToEpic(project!.id),
    onSuccess: (result) => {
      invalidate();
      onSelectView({ type: "epic", epicId: result.epic.id });
      setConfirmPromote(false);
      onClose();
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = title.trim();
    if (!trimmed || !project) return;
    updateMutation.mutate({
      title: trimmed,
      description: description.trim() || null,
      color_hex: colorHex,
      epic_id: epicId || null,
      preferred_time_window_id: preferredTimeWindowId || null,
      schedule_style: scheduleStyle || null,
    });
  };

  const error =
    updateMutation.error ??
    archiveMutation.error ??
    deleteMutation.error ??
    promoteMutation.error;

  return (
    <>
      <Modal open={project !== null} title="Edit project" onClose={onClose}>
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
          <label className="field">
            <span>Description</span>
            <textarea
              className="field-textarea"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={3}
              placeholder="Optional notes"
            />
          </label>
          <label className="field">
            <span>Epic</span>
            <select
              className="field-select"
              value={epicId}
              onChange={(e) => setEpicId(e.target.value)}
            >
              <option value="">None (standalone)</option>
              {epics.map((e) => (
                <option key={e.id} value={e.id}>
                  {e.title}
                </option>
              ))}
            </select>
          </label>
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
          <fieldset className="field">
            <legend>Color</legend>
            <ColorPicker value={colorHex} onChange={setColorHex} />
          </fieldset>
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
              className="btn ghost"
              onClick={() => setConfirmPromote(true)}
            >
              Promote to epic
            </button>
            <button
              type="button"
              className="btn ghost danger-text"
              onClick={() => setConfirmArchive(true)}
            >
              Archive project
            </button>
            <button
              type="button"
              className="btn ghost danger-text"
              onClick={() => setConfirmDelete(true)}
            >
              Delete project
            </button>
          </div>
        </form>
      </Modal>

      <ConfirmDialog
        open={confirmPromote}
        title="Promote to epic?"
        message={`Create an epic from "${project?.title}" and keep this project (same id, all tasks) as its child. You can rename the project afterward if you want a "General" bucket.`}
        confirmLabel="Promote"
        pending={promoteMutation.isPending}
        onClose={() => setConfirmPromote(false)}
        onConfirm={() => promoteMutation.mutate()}
      />

      <ConfirmDialog
        open={confirmArchive}
        title="Archive project?"
        message={`Archive "${project?.title}"? Tasks remain but the project hides from the sidebar.`}
        confirmLabel="Archive"
        pending={archiveMutation.isPending}
        onClose={() => setConfirmArchive(false)}
        onConfirm={() => archiveMutation.mutate()}
      />

      <ConfirmDialog
        open={confirmDelete}
        title="Delete project?"
        message={`Permanently delete "${project?.title}" and its sections? Tasks may be orphaned.`}
        confirmLabel="Delete"
        destructive
        pending={deleteMutation.isPending}
        onClose={() => setConfirmDelete(false)}
        onConfirm={() => deleteMutation.mutate()}
      />
    </>
  );
}
