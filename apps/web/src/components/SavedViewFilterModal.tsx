import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ApiError,
  createView,
  deleteView,
  fetchEpics,
  fetchLabels,
  fetchProjects,
  patchView,
  type SavedView,
  type SavedViewInvalidReference,
  type SavedViewPredicateV1,
  type SavedViewPresentation,
  type ScheduleStyle,
  type TaskPriority,
  type TaskWorkflowState,
} from "../api";
import {
  defaultSavedViewFilterDraft,
  draftFromPredicate,
  predicateFromDraft,
  stripInvalidRefsFromDraft,
  type SavedViewFilterDraft,
} from "../savedViewPredicate";
import type { TaskPresentation } from "../taskPresentation";
import { ConfirmDialog } from "./ConfirmDialog";
import { Modal } from "./Modal";
import { emitToast } from "./ToastHost";

const PRIORITIES: TaskPriority[] = ["p1", "p2", "p3", "p4"];
const WORKFLOW: TaskWorkflowState[] = ["ready", "in_progress", "waiting"];
const SCHEDULE_STATUSES = [
  "unscheduled",
  "scheduled",
  "pinned",
  "completed",
  "cancelled",
  "overbooked",
] as const;
const SCHEDULE_STYLES: ScheduleStyle[] = ["standalone", "time_block", "manual", "bundle"];

function toggleInList<T>(list: T[], value: T): T[] {
  return list.includes(value) ? list.filter((x) => x !== value) : [...list, value];
}

export interface SavedViewFilterModalProps {
  open: boolean;
  onClose: () => void;
  /** create = new view; edit = patch existing */
  mode: "create" | "edit";
  viewId?: string;
  initialName?: string;
  initialPredicate?: SavedViewPredicateV1 | Record<string, unknown>;
  presentationMode?: TaskPresentation;
  invalidReferences?: SavedViewInvalidReference[];
  onSaved?: (view: SavedView) => void;
  onDeleted?: () => void;
}

export function SavedViewFilterModal({
  open,
  onClose,
  mode,
  viewId,
  initialName = "",
  initialPredicate,
  presentationMode = "list",
  invalidReferences = [],
  onSaved,
  onDeleted,
}: SavedViewFilterModalProps) {
  const queryClient = useQueryClient();
  const [name, setName] = useState(initialName);
  const [draft, setDraft] = useState<SavedViewFilterDraft>(() =>
    initialPredicate ? draftFromPredicate(initialPredicate) : defaultSavedViewFilterDraft(),
  );
  const [formError, setFormError] = useState<string | null>(null);
  const [confirmDelete, setConfirmDelete] = useState(false);

  const projectsQuery = useQuery({
    queryKey: ["projects"],
    queryFn: () => fetchProjects({ limit: 200 }),
    enabled: open,
  });
  const epicsQuery = useQuery({
    queryKey: ["epics"],
    queryFn: () => fetchEpics({ limit: 200 }),
    enabled: open,
  });
  const labelsQuery = useQuery({
    queryKey: ["labels"],
    queryFn: () => fetchLabels({ limit: 200 }),
    enabled: open,
  });

  const projects = projectsQuery.data?.items ?? [];
  const epics = epicsQuery.data?.items ?? [];
  const labels = useMemo(
    () => [...(labelsQuery.data?.items ?? [])].sort((a, b) => a.name.localeCompare(b.name)),
    [labelsQuery.data],
  );

  useEffect(() => {
    if (!open) return;
    setName(initialName);
    setDraft(
      initialPredicate ? draftFromPredicate(initialPredicate) : defaultSavedViewFilterDraft(),
    );
    setFormError(null);
  }, [open, initialName, initialPredicate]);

  const saveMutation = useMutation({
    mutationFn: async () => {
      const trimmed = name.trim();
      if (!trimmed) throw new Error("Name is required");
      const predicate = predicateFromDraft(draft) as SavedViewPredicateV1;
      const presentation_json: SavedViewPresentation = { mode: presentationMode };
      if (mode === "create") {
        return createView({
          name: trimmed,
          predicate_json: predicate,
          presentation_json,
        });
      }
      if (!viewId) throw new Error("Missing view id");
      return patchView(viewId, {
        name: trimmed,
        predicate_json: predicate,
        presentation_json,
      });
    },
    onSuccess: (view) => {
      queryClient.invalidateQueries({ queryKey: ["views"] });
      emitToast(mode === "create" ? "View saved" : "View updated");
      onSaved?.(view);
      onClose();
    },
    onError: (err) => {
      if (err instanceof ApiError) {
        setFormError(err.message);
        return;
      }
      setFormError(err instanceof Error ? err.message : "Could not save view");
    },
  });

  const deleteMutation = useMutation({
    mutationFn: async () => {
      if (!viewId) throw new Error("Missing view id");
      await deleteView(viewId);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["views"] });
      emitToast("View deleted");
      onDeleted?.();
      setConfirmDelete(false);
      onClose();
    },
    onError: (err) => {
      emitToast(err instanceof Error ? err.message : "Could not delete view");
    },
  });

  const handleRepairStrip = () => {
    setDraft((prev) => stripInvalidRefsFromDraft(prev, invalidReferences));
    emitToast("Removed missing references from draft — save to apply");
  };

  const dueKind = draft.dueKind;

  return (
    <>
      <Modal
        open={open}
        title={mode === "create" ? "Save view" : "Edit saved view"}
        onClose={onClose}
        className="saved-view-modal"
      >
        {invalidReferences.length > 0 && (
          <div className="saved-view-repair-banner" role="status">
            <p>
              This view references {invalidReferences.length} missing{" "}
              {invalidReferences.length === 1 ? "item" : "items"}. Tasks stay empty until you
              repair the filter.
            </p>
            <button type="button" className="btn secondary small" onClick={handleRepairStrip}>
              Remove missing refs
            </button>
          </div>
        )}

        <label className="field-label">
          Name
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="My filter"
            maxLength={100}
            autoFocus
          />
        </label>

        <fieldset className="saved-view-fieldset">
          <legend>Project scope</legend>
          <label className="checkbox-row">
            <input
              type="checkbox"
              checked={draft.inbox}
              onChange={(e) => setDraft((d) => ({ ...d, inbox: e.target.checked }))}
              disabled={draft.projectIds.length > 0}
            />
            Inbox only (no project)
          </label>
          <p className="muted small">Pick projects or inbox — not both.</p>
          <div className="saved-view-checkbox-grid">
            {projects.map((p) => (
              <label key={p.id} className="checkbox-row">
                <input
                  type="checkbox"
                  checked={draft.projectIds.includes(p.id)}
                  disabled={draft.inbox}
                  onChange={() =>
                    setDraft((d) => ({
                      ...d,
                      projectIds: toggleInList(d.projectIds, p.id),
                    }))
                  }
                />
                {p.title}
              </label>
            ))}
          </div>
        </fieldset>

        {epics.length > 0 && (
          <fieldset className="saved-view-fieldset">
            <legend>Epics</legend>
            <div className="saved-view-checkbox-grid">
              {epics.map((epic) => (
                <label key={epic.id} className="checkbox-row">
                  <input
                    type="checkbox"
                    checked={draft.epicIds.includes(epic.id)}
                    onChange={() =>
                      setDraft((d) => ({
                        ...d,
                        epicIds: toggleInList(d.epicIds, epic.id),
                      }))
                    }
                  />
                  {epic.title}
                </label>
              ))}
            </div>
          </fieldset>
        )}

        {labels.length > 0 && (
          <fieldset className="saved-view-fieldset">
            <legend>Labels</legend>
            <div className="saved-view-label-match" role="radiogroup" aria-label="Label match">
              <label className="checkbox-row">
                <input
                  type="radio"
                  name="labelMatch"
                  checked={draft.labelMatch === "any"}
                  onChange={() => setDraft((d) => ({ ...d, labelMatch: "any" }))}
                />
                Match any selected
              </label>
              <label className="checkbox-row">
                <input
                  type="radio"
                  name="labelMatch"
                  checked={draft.labelMatch === "all"}
                  onChange={() => setDraft((d) => ({ ...d, labelMatch: "all" }))}
                />
                Match all selected
              </label>
            </div>
            <div className="saved-view-checkbox-grid">
              {labels.map((label) => (
                <label key={label.id} className="checkbox-row">
                  <input
                    type="checkbox"
                    checked={draft.labelIds.includes(label.id)}
                    onChange={() =>
                      setDraft((d) => ({
                        ...d,
                        labelIds: toggleInList(d.labelIds, label.id),
                      }))
                    }
                  />
                  {label.name}
                </label>
              ))}
            </div>
          </fieldset>
        )}

        <fieldset className="saved-view-fieldset">
          <legend>Priority</legend>
          <div className="saved-view-inline-checks">
            {PRIORITIES.map((p) => (
              <label key={p} className="checkbox-row">
                <input
                  type="checkbox"
                  checked={draft.priorities.includes(p)}
                  onChange={() =>
                    setDraft((d) => ({
                      ...d,
                      priorities: toggleInList(d.priorities, p),
                    }))
                  }
                />
                {p.toUpperCase()}
              </label>
            ))}
          </div>
        </fieldset>

        <fieldset className="saved-view-fieldset">
          <legend>Workflow</legend>
          <div className="saved-view-inline-checks">
            {WORKFLOW.map((w) => (
              <label key={w} className="checkbox-row">
                <input
                  type="checkbox"
                  checked={draft.workflowStates.includes(w)}
                  onChange={() =>
                    setDraft((d) => ({
                      ...d,
                      workflowStates: toggleInList(d.workflowStates, w),
                    }))
                  }
                />
                {w.replace("_", " ")}
              </label>
            ))}
          </div>
        </fieldset>

        <label className="field-label">
          Completion
          <select
            value={draft.completion}
            onChange={(e) =>
              setDraft((d) => ({
                ...d,
                completion: e.target.value as SavedViewFilterDraft["completion"],
              }))
            }
          >
            <option value="open">Open tasks</option>
            <option value="done">Completed only</option>
            <option value="any">Open and completed</option>
          </select>
        </label>

        <fieldset className="saved-view-fieldset">
          <legend>Schedule status</legend>
          <div className="saved-view-checkbox-grid">
            {SCHEDULE_STATUSES.map((s) => (
              <label key={s} className="checkbox-row">
                <input
                  type="checkbox"
                  checked={draft.scheduleStatuses.includes(s)}
                  onChange={() =>
                    setDraft((d) => ({
                      ...d,
                      scheduleStatuses: toggleInList(d.scheduleStatuses, s),
                    }))
                  }
                />
                {s}
              </label>
            ))}
          </div>
        </fieldset>

        <fieldset className="saved-view-fieldset">
          <legend>Schedule style</legend>
          <div className="saved-view-inline-checks">
            {SCHEDULE_STYLES.map((s) => (
              <label key={s} className="checkbox-row">
                <input
                  type="checkbox"
                  checked={draft.scheduleStyles.includes(s)}
                  onChange={() =>
                    setDraft((d) => ({
                      ...d,
                      scheduleStyles: toggleInList(d.scheduleStyles, s),
                    }))
                  }
                />
                {s.replace("_", " ")}
              </label>
            ))}
          </div>
        </fieldset>

        <fieldset className="saved-view-fieldset">
          <legend>Due date</legend>
          <label className="checkbox-row">
            <input
              type="radio"
              name="dueKind"
              checked={dueKind === null}
              onChange={() => setDraft((d) => ({ ...d, dueKind: null }))}
            />
            Any due date
          </label>
          <label className="checkbox-row">
            <input
              type="radio"
              name="dueKind"
              checked={dueKind === "none"}
              onChange={() => setDraft((d) => ({ ...d, dueKind: "none" }))}
            />
            No due date
          </label>
          <label className="checkbox-row">
            <input
              type="radio"
              name="dueKind"
              checked={dueKind === "rolling"}
              onChange={() =>
                setDraft((d) => ({
                  ...d,
                  dueKind: "rolling",
                  dueRolling: d.dueRolling ?? "today",
                }))
              }
            />
            Rolling (server timezone)
          </label>
          {dueKind === "rolling" && (
            <div className="saved-view-due-rolling">
              <select
                value={draft.dueRolling ?? "today"}
                onChange={(e) =>
                  setDraft((d) => ({
                    ...d,
                    dueRolling: e.target.value as SavedViewFilterDraft["dueRolling"],
                  }))
                }
              >
                <option value="today">Today</option>
                <option value="next_7_days">Next 7 days</option>
                <option value="this_calendar_week">This calendar week</option>
                <option value="within_days">Within N days (Upcoming-style)</option>
              </select>
              {draft.dueRolling === "within_days" && (
                <label className="field-label inline">
                  Days
                  <input
                    type="number"
                    min={1}
                    max={366}
                    value={draft.dueWithinDays}
                    onChange={(e) =>
                      setDraft((d) => ({
                        ...d,
                        dueWithinDays: Number(e.target.value) || 7,
                      }))
                    }
                  />
                </label>
              )}
            </div>
          )}
          <label className="checkbox-row">
            <input
              type="radio"
              name="dueKind"
              checked={dueKind === "fixed"}
              onChange={() => setDraft((d) => ({ ...d, dueKind: "fixed" }))}
            />
            Fixed date range
          </label>
          {dueKind === "fixed" && (
            <div className="saved-view-due-fixed">
              <label className="field-label">
                From
                <input
                  type="date"
                  value={draft.dueFixedFrom}
                  onChange={(e) => setDraft((d) => ({ ...d, dueFixedFrom: e.target.value }))}
                />
              </label>
              <label className="field-label">
                To
                <input
                  type="date"
                  value={draft.dueFixedTo}
                  onChange={(e) => setDraft((d) => ({ ...d, dueFixedTo: e.target.value }))}
                />
              </label>
            </div>
          )}
        </fieldset>

        <p className="muted small">
          Presentation when saving: <strong>{presentationMode === "board" ? "Board" : "List"}</strong>{" "}
          (from the current view toggle).
        </p>

        {formError && <p className="form-error">{formError}</p>}

        <div className="form-actions saved-view-form-actions">
          {mode === "edit" && viewId && (
            <button
              type="button"
              className="btn danger"
              onClick={() => setConfirmDelete(true)}
              disabled={deleteMutation.isPending}
            >
              Delete view
            </button>
          )}
          <button type="button" className="btn secondary" onClick={onClose}>
            Cancel
          </button>
          <button
            type="button"
            className="btn primary"
            disabled={saveMutation.isPending}
            onClick={() => saveMutation.mutate()}
          >
            {mode === "create" ? "Save view" : "Update view"}
          </button>
        </div>
      </Modal>

      <ConfirmDialog
        open={confirmDelete}
        title="Delete saved view?"
        message="Tasks are not deleted — only this filter."
        confirmLabel="Delete"
        destructive
        pending={deleteMutation.isPending}
        onClose={() => setConfirmDelete(false)}
        onConfirm={() => deleteMutation.mutate()}
      />
    </>
  );
}
