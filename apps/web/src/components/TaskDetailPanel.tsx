import {
  useEffect,
  useMemo,
  useRef,
  useState,
  type PointerEvent as ReactPointerEvent,
} from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  createLabel,
  createProject,
  createTask,
  createTaskReminder,
  deleteReminder,
  deleteTask,
  deleteTaskRecurrence,
  fetchEpics,
  fetchFocusWindows,
  fetchLabels,
  fetchPlans,
  fetchProjects,
  fetchSections,
  fetchTaskReminders,
  fetchTasks,
  promoteTaskToProject,
  putTaskRecurrence,
  updateTask,
  type Epic,
  type FocusWindow,
  type Label,
  type Plan,
  type Project,
  type ReminderChannel,
  type ScheduleStyle,
  type Task,
  type TaskPriority,
  type TaskUpdate,
} from "../api";
import { DEFAULT_EPIC_COLOR, DEFAULT_PROJECT_COLOR } from "../colors";
import { NARROW_QUERY } from "../hooks/useMediaQuery";
import { collectDeleteTree, useUndoStack } from "../undoStack";
import { ConfirmDialog } from "./ConfirmDialog";
import { emitToast } from "./ToastHost";
import { TaskDetailAdvanced } from "./TaskDetailAdvanced";
import { TaskDetailCreateProject } from "./TaskDetailCreateProject";
import { TaskDetailDeps } from "./TaskDetailDeps";
import { TaskDetailLabels } from "./TaskDetailLabels";
import { TaskDetailPromote } from "./TaskDetailPromote";
import { TaskDetailRecurrence } from "./TaskDetailRecurrence";
import { TaskDetailScheduling } from "./TaskDetailScheduling";
import type { DetailSectionId } from "./TaskDetailSection";

interface TaskDetailPanelProps {
  task: Task | null;
  allTasks: Task[];
  onClose: () => void;
}

const PRIORITIES: TaskPriority[] = ["p1", "p2", "p3", "p4"];

const SECTION_STORAGE_KEY = "theplan.taskDetail.sections";
const WIDTH_STORAGE_KEY = "theplan.taskDetail.width";
const DEFAULT_PANEL_WIDTH = 340;
const MIN_PANEL_WIDTH = 280;
const MAX_PANEL_WIDTH = 720;
const MOBILE_LAYOUT_MQ = NARROW_QUERY;

const DEFAULT_SECTION_OPEN: Record<DetailSectionId, boolean> = {
  scheduling: false,
  recurrence: false,
  dependencies: false,
  labels: false,
  advanced: false,
};

function readSectionOpenState(): Record<DetailSectionId, boolean> {
  try {
    const raw = localStorage.getItem(SECTION_STORAGE_KEY);
    if (!raw) return { ...DEFAULT_SECTION_OPEN };
    const parsed = JSON.parse(raw) as Partial<Record<DetailSectionId, boolean>>;
    return { ...DEFAULT_SECTION_OPEN, ...parsed };
  } catch {
    return { ...DEFAULT_SECTION_OPEN };
  }
}

function writeSectionOpenState(state: Record<DetailSectionId, boolean>) {
  try {
    localStorage.setItem(SECTION_STORAGE_KEY, JSON.stringify(state));
  } catch {
    /* ignore quota / private mode */
  }
}

function clampPanelWidth(value: number): number {
  return Math.min(MAX_PANEL_WIDTH, Math.max(MIN_PANEL_WIDTH, Math.round(value)));
}

function readStoredPanelWidth(): number {
  try {
    const raw = localStorage.getItem(WIDTH_STORAGE_KEY);
    if (!raw) return DEFAULT_PANEL_WIDTH;
    const parsed = Number(raw);
    if (!Number.isFinite(parsed)) return DEFAULT_PANEL_WIDTH;
    return clampPanelWidth(parsed);
  } catch {
    return DEFAULT_PANEL_WIDTH;
  }
}

function writeStoredPanelWidth(width: number) {
  try {
    localStorage.setItem(WIDTH_STORAGE_KEY, String(clampPanelWidth(width)));
  } catch {
    /* ignore quota / private mode */
  }
}

function applyPanelWidthCssVar(width: number) {
  document.documentElement.style.setProperty("--task-detail-width", `${clampPanelWidth(width)}px`);
}

function isMobileTaskDetailLayout(): boolean {
  return typeof window !== "undefined" && window.matchMedia(MOBILE_LAYOUT_MQ).matches;
}

function toDatetimeLocal(iso: string | null): string {
  if (!iso) return "";
  const d = new Date(iso);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function fromDatetimeLocal(value: string): string | null {
  if (!value) return null;
  return new Date(value).toISOString();
}

function isDescendantOf(candidate: Task, ancestorId: string, byId: Map<string, Task>): boolean {
  let current: Task | undefined = candidate;
  const seen = new Set<string>();
  while (current?.parent_task_id) {
    if (current.parent_task_id === ancestorId) return true;
    if (seen.has(current.parent_task_id)) break;
    seen.add(current.parent_task_id);
    current = byId.get(current.parent_task_id);
  }
  return false;
}

function applyTaskUpdate(task: Task, body: TaskUpdate): Task {
  return {
    ...task,
    title: body.title ?? task.title,
    description: body.description !== undefined ? body.description : task.description,
    project_id: body.project_id !== undefined ? body.project_id : task.project_id,
    section_id: body.section_id !== undefined ? body.section_id : task.section_id,
    parent_task_id:
      body.parent_task_id !== undefined ? body.parent_task_id : task.parent_task_id,
    priority: body.priority ?? task.priority,
    due_at: body.due_at !== undefined ? body.due_at : task.due_at,
    deadline_at: body.deadline_at !== undefined ? body.deadline_at : task.deadline_at,
    soft_target_at:
      body.soft_target_at !== undefined ? body.soft_target_at : task.soft_target_at,
    plan_id: body.plan_id !== undefined ? body.plan_id : task.plan_id,
    estimated_duration_minutes:
      body.estimated_duration_minutes ?? task.estimated_duration_minutes,
    preferred_time_window_id:
      body.preferred_time_window_id !== undefined
        ? body.preferred_time_window_id
        : task.preferred_time_window_id,
    schedule_style:
      body.schedule_style !== undefined ? body.schedule_style : task.schedule_style,
    label_ids: body.label_ids ?? task.label_ids,
  };
}

export function TaskDetailPanel({ task, allTasks, onClose }: TaskDetailPanelProps) {
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [priority, setPriority] = useState<TaskPriority>("p4");
  const [dueAtLocal, setDueAtLocal] = useState("");
  const [softTargetAtLocal, setSoftTargetAtLocal] = useState("");
  const [deadlineAtLocal, setDeadlineAtLocal] = useState("");
  const [duration, setDuration] = useState("");
  const [projectId, setProjectId] = useState<string>("");
  const [sectionId, setSectionId] = useState<string>("");
  const [parentTaskId, setParentTaskId] = useState<string>("");
  const [labelIds, setLabelIds] = useState<string[]>([]);
  const [preferredTimeWindowId, setPreferredTimeWindowId] = useState<string>("");
  const [scheduleStyle, setScheduleStyle] = useState<"" | ScheduleStyle>("");
  const [planId, setPlanId] = useState<string>("");
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [confirmPromote, setConfirmPromote] = useState(false);
  const [recurrenceText, setRecurrenceText] = useState("");
  const [startsOn, setStartsOn] = useState("");
  const [endsOn, setEndsOn] = useState("");
  const [reminderAtLocal, setReminderAtLocal] = useState("");
  const [reminderChannel, setReminderChannel] = useState<ReminderChannel>("in_app");
  const [notifPermission, setNotifPermission] = useState<NotificationPermission | "unsupported">(
    typeof Notification === "undefined" ? "unsupported" : Notification.permission,
  );
  const [sectionOpen, setSectionOpen] = useState<Record<DetailSectionId, boolean>>(readSectionOpenState);
  const [labelFilter, setLabelFilter] = useState("");
  const [panelWidth, setPanelWidth] = useState(readStoredPanelWidth);
  const [childTitle, setChildTitle] = useState("");
  const [createProjectOpen, setCreateProjectOpen] = useState(false);
  const [newProjectTitle, setNewProjectTitle] = useState("");
  const [newProjectEpicId, setNewProjectEpicId] = useState("");
  const resizeDragRef = useRef<{ startX: number; startWidth: number } | null>(null);
  const queryClient = useQueryClient();
  const { push } = useUndoStack();

  useEffect(() => {
    applyPanelWidthCssVar(panelWidth);
  }, [panelWidth]);

  const toggleSection = (id: DetailSectionId) => {
    setSectionOpen((prev) => {
      const next = { ...prev, [id]: !prev[id] };
      writeSectionOpenState(next);
      return next;
    });
  };

  const handleResizePointerDown = (e: ReactPointerEvent<HTMLDivElement>) => {
    if (isMobileTaskDetailLayout()) return;
    e.preventDefault();
    e.stopPropagation();
    const handle = e.currentTarget;
    resizeDragRef.current = { startX: e.clientX, startWidth: panelWidth };
    handle.setPointerCapture(e.pointerId);
    document.body.classList.add("is-resizing-task-detail");

    const onMove = (ev: PointerEvent) => {
      const drag = resizeDragRef.current;
      if (!drag) return;
      // Left edge: drag left → wider panel
      const next = clampPanelWidth(drag.startWidth + (drag.startX - ev.clientX));
      setPanelWidth(next);
    };

    const onUp = (ev: PointerEvent) => {
      resizeDragRef.current = null;
      document.body.classList.remove("is-resizing-task-detail");
      try {
        handle.releasePointerCapture(ev.pointerId);
      } catch {
        /* already released */
      }
      handle.removeEventListener("pointermove", onMove);
      handle.removeEventListener("pointerup", onUp);
      handle.removeEventListener("pointercancel", onUp);
      setPanelWidth((w) => {
        writeStoredPanelWidth(w);
        applyPanelWidthCssVar(w);
        return w;
      });
    };

    handle.addEventListener("pointermove", onMove);
    handle.addEventListener("pointerup", onUp);
    handle.addEventListener("pointercancel", onUp);
  };

  const projectsQuery = useQuery({ queryKey: ["projects"], queryFn: () => fetchProjects() });
  const projects: Project[] = projectsQuery.data?.items ?? [];

  const epicsQuery = useQuery({
    queryKey: ["epics"],
    queryFn: () => fetchEpics(),
    enabled: task !== null,
  });
  const epics: Epic[] = epicsQuery.data?.items ?? [];

  const labelsQuery = useQuery({ queryKey: ["labels"], queryFn: () => fetchLabels({ limit: 200 }) });
  const allLabels: Label[] = labelsQuery.data?.items ?? [];

  const focusWindowsQuery = useQuery({
    queryKey: ["focus-windows"],
    queryFn: fetchFocusWindows,
    enabled: task !== null,
  });
  const focusWindows: FocusWindow[] = focusWindowsQuery.data ?? [];

  const plansQuery = useQuery({
    queryKey: ["plans"],
    queryFn: fetchPlans,
    enabled: task !== null,
  });
  const plans: Plan[] = plansQuery.data ?? [];

  const effectiveProjectId = projectId || null;

  const sectionsQuery = useQuery({
    queryKey: ["sections", effectiveProjectId],
    queryFn: () => fetchSections(effectiveProjectId!),
    enabled: effectiveProjectId !== null,
  });
  const sections = sectionsQuery.data?.items ?? [];

  const parentCandidatesQuery = useQuery({
    queryKey: ["tasks", "parents", effectiveProjectId],
    queryFn: () =>
      effectiveProjectId
        ? fetchTasks({ project_id: effectiveProjectId, limit: 200, is_completed: false })
        : fetchTasks({ inbox: true, limit: 200, is_completed: false }),
    enabled: task !== null,
  });
  const parentCandidates = parentCandidatesQuery.data?.items ?? [];

  useEffect(() => {
    if (!task) return;
    setTitle(task.title);
    setDescription(task.description ?? "");
    setPriority(task.priority);
    setDueAtLocal(toDatetimeLocal(task.due_at));
    setSoftTargetAtLocal(toDatetimeLocal(task.soft_target_at));
    setDeadlineAtLocal(toDatetimeLocal(task.deadline_at));
    setDuration(task.estimated_duration_minutes > 0 ? String(task.estimated_duration_minutes) : "");
    setProjectId(task.project_id ?? "");
    setSectionId(task.section_id ?? "");
    setParentTaskId(task.parent_task_id ?? "");
    setLabelIds(task.label_ids);
    setPreferredTimeWindowId(task.preferred_time_window_id ?? "");
    setScheduleStyle(task.schedule_style ?? "");
    setPlanId(task.plan_id ?? "");
    setRecurrenceText("");
    setStartsOn(task.recurrence?.starts_on ?? "");
    setEndsOn(task.recurrence?.ends_on ?? "");
    setReminderAtLocal("");
    setReminderChannel("in_app");
    setLabelFilter("");
    setChildTitle("");
    setCreateProjectOpen(false);
    setNewProjectTitle("");
    setNewProjectEpicId("");
  }, [task]);

  const remindersQuery = useQuery({
    queryKey: ["reminders", task?.id],
    queryFn: () => fetchTaskReminders(task!.id),
    enabled: task != null,
  });
  const reminders = remindersQuery.data ?? [];
  const upcomingReminders = reminders.filter((r) => !r.is_fired);

  const byId = useMemo(() => new Map(allTasks.map((t) => [t.id, t])), [allTasks]);

  const parentOptions = useMemo(() => {
    if (!task) return [];
    return parentCandidates.filter(
      (t) =>
        t.id !== task.id &&
        !isDescendantOf(t, task.id, byId) &&
        t.nesting_level < 2,
    );
  }, [parentCandidates, task, byId]);

  const inheritTimeMapHint = useMemo(() => {
    if (preferredTimeWindowId) return null;
    if (!projectId) return null;
    const selectedProject = projects.find((p) => p.id === projectId);
    if (!selectedProject) return null;
    if (selectedProject.preferred_time_window_id) {
      return `from project ${selectedProject.title}`;
    }
    if (selectedProject.epic_id) {
      const epic = epics.find((e) => e.id === selectedProject.epic_id);
      if (epic?.preferred_time_window_id) {
        return `from epic ${epic.title}`;
      }
    }
    return null;
  }, [preferredTimeWindowId, projectId, projects, epics]);

  const inheritScheduleStyleHint = useMemo(() => {
    if (scheduleStyle !== "") return null;
    if (!projectId) return null;
    const selectedProject = projects.find((p) => p.id === projectId);
    if (!selectedProject) return null;
    if (selectedProject.schedule_style) {
      return `from project ${selectedProject.title}`;
    }
    if (selectedProject.epic_id) {
      const epic = epics.find((e) => e.id === selectedProject.epic_id);
      if (epic?.schedule_style) {
        return `from epic ${epic.title}`;
      }
    }
    return null;
  }, [scheduleStyle, projectId, projects, epics]);

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ["tasks"] });
  const invalidateScheduleExplanation = (taskId: string) => {
    queryClient.invalidateQueries({ queryKey: ["schedule-explanation", taskId] });
  };

  const updateMutation = useMutation({
    mutationFn: (body: TaskUpdate) => updateTask(task!.id, body),
    onMutate: async (body) => {
      const taskKey = ["task", task!.id];
      await queryClient.cancelQueries({ queryKey: taskKey });
      const previousTask = queryClient.getQueryData<Task>(taskKey);
      const previousTasksEntries = queryClient
        .getQueriesData<{ items: Task[]; total: number }>({ queryKey: ["tasks"] })
        .map(([key, data]) => ({ key, data }));

      if (previousTask) {
        queryClient.setQueryData(taskKey, applyTaskUpdate(previousTask, body));
      }

      for (const { key, data } of previousTasksEntries) {
        if (!data) continue;
        queryClient.setQueryData(key, {
          ...data,
          items: data.items.map((t) =>
            t.id === task!.id ? applyTaskUpdate(t, body) : t,
          ),
        });
      }

      return { previousTask, previousTasksEntries, taskKey };
    },
    onError: (_err, _vars, context) => {
      if (context?.previousTask) {
        queryClient.setQueryData(context.taskKey, context.previousTask);
      }
      for (const { key, data } of context?.previousTasksEntries ?? []) {
        queryClient.setQueryData(key, data);
      }
      emitToast("Couldn't save — reverted");
    },
    onSuccess: () => {
      invalidate();
      queryClient.invalidateQueries({ queryKey: ["task", task!.id] });
      // Duration/deadline/map/style (and inheritance via project) are W1 fingerprint
      // inputs — drop the cached explanation so stale badges refresh on reopen.
      invalidateScheduleExplanation(task!.id);
      onClose();
    },
  });

  const deleteMutation = useMutation({
    mutationFn: async () => {
      const tree = await collectDeleteTree(task!);
      await deleteTask(task!.id);
      return tree;
    },
    onSuccess: (tree) => {
      push({ type: "delete_tree", nodes: tree });
      invalidate();
      queryClient.invalidateQueries({ queryKey: ["search"] });
      queryClient.invalidateQueries({ queryKey: ["task"] });
      setConfirmDelete(false);
      onClose();
    },
  });

  const promoteMutation = useMutation({
    mutationFn: () =>
      promoteTaskToProject(task!.id, { include_descendants: true }),
    onSuccess: (result) => {
      setConfirmPromote(false);
      queryClient.invalidateQueries({ queryKey: ["projects"] });
      queryClient.invalidateQueries({ queryKey: ["epics"] });
      invalidate();
      queryClient.invalidateQueries({ queryKey: ["task", task!.id] });
      emitToast(`Promoted to project “${result.project.title}”`);
    },
    onError: (err: Error) => emitToast(err.message || "Couldn't promote to project"),
  });

  const recurrenceMutation = useMutation({
    mutationFn: async () => {
      const trimmed = recurrenceText.trim();
      if (!trimmed) {
        await deleteTaskRecurrence(task!.id);
        return;
      }
      await putTaskRecurrence(task!.id, {
        text: trimmed.toLowerCase().startsWith("every") ? trimmed : `every ${trimmed}`,
        starts_on: startsOn || null,
        ends_on: endsOn || null,
      });
    },
    onSuccess: () => {
      invalidate();
      queryClient.invalidateQueries({ queryKey: ["task", task!.id] });
      emitToast("Recurrence saved");
    },
    onError: (err: Error) => emitToast(err.message || "Couldn't save recurrence"),
  });

  const clearRecurrenceMutation = useMutation({
    mutationFn: () => deleteTaskRecurrence(task!.id),
    onSuccess: () => {
      setRecurrenceText("");
      setStartsOn("");
      setEndsOn("");
      invalidate();
      queryClient.invalidateQueries({ queryKey: ["task", task!.id] });
      emitToast("Recurrence cleared");
    },
  });

  const createReminderMutation = useMutation({
    mutationFn: async () => {
      const fireAt = fromDatetimeLocal(reminderAtLocal);
      if (!fireAt) throw new Error("Pick a reminder time");
      return createTaskReminder(task!.id, { fire_at: fireAt, channel: reminderChannel });
    },
    onSuccess: () => {
      setReminderAtLocal("");
      queryClient.invalidateQueries({ queryKey: ["reminders", task!.id] });
      emitToast("Reminder added");
    },
    onError: (err: Error) => emitToast(err.message || "Couldn't add reminder"),
  });

  const deleteReminderMutation = useMutation({
    mutationFn: (reminderId: string) => deleteReminder(reminderId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["reminders", task!.id] });
    },
    onError: (err: Error) => emitToast(err.message || "Couldn't delete reminder"),
  });

  const createLabelMutation = useMutation({
    mutationFn: (name: string) =>
      createLabel({ name: name.trim().toLowerCase(), color_hex: DEFAULT_EPIC_COLOR }),
    onSuccess: (label) => {
      setLabelIds((prev) => (prev.includes(label.id) ? prev : [...prev, label.id]));
      setLabelFilter("");
      queryClient.invalidateQueries({ queryKey: ["labels"] });
      emitToast(`Created label “${label.name}”`);
    },
    onError: (err: Error) => emitToast(err.message || "Couldn't create label"),
  });

  const canCreateChild = task != null && task.nesting_level < 2;

  const createChildMutation = useMutation({
    mutationFn: (title: string) =>
      createTask({
        title: title.trim(),
        parent_task_id: task!.id,
        project_id: task!.project_id,
        section_id: task!.section_id,
        priority: task!.priority,
      }),
    onSuccess: (created) => {
      setChildTitle("");
      invalidate();
      queryClient.invalidateQueries({ queryKey: ["tasks", "parents"] });
      emitToast(`Created subtask “${created.title}”`);
    },
    onError: (err: Error) => emitToast(err.message || "Couldn't create subtask"),
  });

  const createProjectMutation = useMutation({
    mutationFn: (vars: { title: string; epic_id: string | null }) =>
      createProject({
        title: vars.title.trim(),
        epic_id: vars.epic_id,
        color_hex: DEFAULT_PROJECT_COLOR,
      }),
    onSuccess: (project) => {
      setProjectId(project.id);
      setSectionId("");
      setCreateProjectOpen(false);
      setNewProjectTitle("");
      setNewProjectEpicId("");
      queryClient.invalidateQueries({ queryKey: ["projects"] });
      emitToast(`Created project “${project.title}” — selected`);
    },
    onError: (err: Error) => emitToast(err.message || "Couldn't create project"),
  });

  const openCreateProject = () => {
    const currentProject = projects.find((p) => p.id === projectId);
    setNewProjectEpicId(currentProject?.epic_id ?? "");
    setNewProjectTitle("");
    setCreateProjectOpen(true);
  };

  const handleCreateChild = () => {
    const trimmed = childTitle.trim();
    if (!trimmed || !canCreateChild || createChildMutation.isPending) return;
    createChildMutation.mutate(trimmed);
  };

  const handleCreateProjectSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = newProjectTitle.trim();
    if (!trimmed || createProjectMutation.isPending) return;
    createProjectMutation.mutate({
      title: trimmed,
      epic_id: newProjectEpicId || null,
    });
  };

  const requestBrowserNotifications = async () => {
    if (typeof Notification === "undefined") {
      setNotifPermission("unsupported");
      return;
    }
    const permission = await Notification.requestPermission();
    setNotifPermission(permission);
    if (permission === "granted") emitToast("Browser notifications enabled");
    else if (permission === "denied") emitToast("Browser notifications blocked");
  };

  const handleProjectChange = (value: string) => {
    setProjectId(value);
    setSectionId("");
    if (value) {
      const stillValid = sections.some((s) => s.id === sectionId);
      if (!stillValid) setSectionId("");
    }
  };

  const toggleLabel = (labelId: string) => {
    setLabelIds((prev) =>
      prev.includes(labelId) ? prev.filter((id) => id !== labelId) : [...prev, labelId],
    );
  };

  const handlePlanChange = (value: string) => {
    setPlanId(value);
    if (value) {
      const plan = plans.find((p) => p.id === value);
      if (plan?.soft_target_at) {
        setSoftTargetAtLocal(toDatetimeLocal(plan.soft_target_at));
      }
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!task) return;
    const trimmed = title.trim();
    if (!trimmed) return;
    const parsedDuration = duration.trim() ? parseInt(duration, 10) : 0;
    updateMutation.mutate({
      title: trimmed,
      description: description.trim() || null,
      priority,
      due_at: fromDatetimeLocal(dueAtLocal),
      soft_target_at: fromDatetimeLocal(softTargetAtLocal),
      deadline_at: fromDatetimeLocal(deadlineAtLocal),
      estimated_duration_minutes: Number.isFinite(parsedDuration) ? parsedDuration : 0,
      project_id: projectId || null,
      section_id: projectId && sectionId ? sectionId : null,
      parent_task_id: parentTaskId || null,
      label_ids: labelIds,
      preferred_time_window_id: preferredTimeWindowId || null,
      schedule_style: scheduleStyle || null,
      plan_id: planId || null,
    });
  };

  if (!task) return null;

  return (
    <>
      <aside
        className="task-detail-panel task-detail-sheet"
        aria-label="Task details"
        style={{ ["--task-detail-width" as string]: `${panelWidth}px` }}
      >
        <div
          className="task-detail-resize-handle"
          role="separator"
          aria-orientation="vertical"
          aria-label="Resize task detail panel"
          aria-valuemin={MIN_PANEL_WIDTH}
          aria-valuemax={MAX_PANEL_WIDTH}
          aria-valuenow={panelWidth}
          tabIndex={0}
          onPointerDown={handleResizePointerDown}
          onKeyDown={(e) => {
            if (isMobileTaskDetailLayout()) return;
            const step = e.shiftKey ? 40 : 16;
            if (e.key === "ArrowLeft") {
              e.preventDefault();
              setPanelWidth((w) => {
                const next = clampPanelWidth(w + step);
                writeStoredPanelWidth(next);
                return next;
              });
            } else if (e.key === "ArrowRight") {
              e.preventDefault();
              setPanelWidth((w) => {
                const next = clampPanelWidth(w - step);
                writeStoredPanelWidth(next);
                return next;
              });
            } else if (e.key === "Home") {
              e.preventDefault();
              setPanelWidth(MIN_PANEL_WIDTH);
              writeStoredPanelWidth(MIN_PANEL_WIDTH);
            } else if (e.key === "End") {
              e.preventDefault();
              setPanelWidth(MAX_PANEL_WIDTH);
              writeStoredPanelWidth(MAX_PANEL_WIDTH);
            }
          }}
        />
        <header className="detail-header">
          <h2>Task details</h2>
          <div className="detail-header-actions">
            <button
              type="submit"
              form="task-detail-form"
              className="btn primary small"
              disabled={updateMutation.isPending}
            >
              {updateMutation.isPending ? "Saving…" : "Save"}
            </button>
            <button type="button" className="icon-btn" onClick={onClose} aria-label="Close panel">
              ×
            </button>
          </div>
        </header>
        <form id="task-detail-form" className="entity-form detail-form" onSubmit={handleSubmit}>
          <div className="detail-form-body">
          <label className="field">
            <span>Title</span>
            <input type="text" value={title} onChange={(e) => setTitle(e.target.value)} autoFocus />
          </label>
          <label className="field">
            <span>Description</span>
            <textarea
              className="field-textarea"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={4}
              placeholder="Notes, links, context…"
            />
          </label>
          <label className="field">
            <span>Priority</span>
            <select
              className="field-select"
              value={priority}
              onChange={(e) => setPriority(e.target.value as TaskPriority)}
            >
              {PRIORITIES.map((p) => (
                <option key={p} value={p}>
                  {p.toUpperCase()}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            <span>Due</span>
            <input
              type="datetime-local"
              className="field-datetime"
              value={dueAtLocal}
              onChange={(e) => setDueAtLocal(e.target.value)}
            />
          </label>
          <label className="field">
            <span>Soft target</span>
            <input
              type="datetime-local"
              className="field-datetime"
              value={softTargetAtLocal}
              onChange={(e) => setSoftTargetAtLocal(e.target.value)}
            />
            <span className="field-hint muted small">
              Flexible plan target — scheduler may slide
            </span>
          </label>
          <label className="field">
            <span>Deadline</span>
            <input
              type="datetime-local"
              className="field-datetime"
              value={deadlineAtLocal}
              onChange={(e) => setDeadlineAtLocal(e.target.value)}
            />
            <span className="field-hint muted small">
              Hard commit — scheduler must not miss
            </span>
          </label>

          <TaskDetailScheduling
            taskId={task.id}
            open={sectionOpen.scheduling}
            onToggle={toggleSection}
            planId={planId}
            plans={plans}
            onPlanChange={handlePlanChange}
            duration={duration}
            onDurationChange={setDuration}
            preferredTimeWindowId={preferredTimeWindowId}
            onPreferredTimeWindowIdChange={setPreferredTimeWindowId}
            focusWindows={focusWindows}
            inheritTimeMapHint={inheritTimeMapHint}
            scheduleStyle={scheduleStyle}
            onScheduleStyleChange={setScheduleStyle}
            inheritScheduleStyleHint={inheritScheduleStyleHint}
            scheduleStatus={task.status}
          />

          <TaskDetailRecurrence
            open={sectionOpen.recurrence}
            onToggle={toggleSection}
            task={task}
            recurrenceText={recurrenceText}
            onRecurrenceTextChange={setRecurrenceText}
            startsOn={startsOn}
            onStartsOnChange={setStartsOn}
            endsOn={endsOn}
            onEndsOnChange={setEndsOn}
            savePending={recurrenceMutation.isPending}
            clearPending={clearRecurrenceMutation.isPending}
            onSave={() => recurrenceMutation.mutate()}
            onClear={() => clearRecurrenceMutation.mutate()}
          />

          <TaskDetailDeps
            open={sectionOpen.dependencies}
            onToggle={toggleSection}
            projectId={projectId}
            projects={projects}
            onProjectChange={handleProjectChange}
            onOpenCreateProject={openCreateProject}
            sectionId={sectionId}
            sections={sections}
            onSectionChange={setSectionId}
            parentTaskId={parentTaskId}
            parentOptions={parentOptions}
            onParentTaskIdChange={setParentTaskId}
            canCreateChild={canCreateChild}
            childTitle={childTitle}
            onChildTitleChange={setChildTitle}
            createChildPending={createChildMutation.isPending}
            onCreateChild={handleCreateChild}
          />

          <TaskDetailLabels
            open={sectionOpen.labels}
            onToggle={toggleSection}
            allLabels={allLabels}
            labelIds={labelIds}
            onToggleLabel={toggleLabel}
            labelFilter={labelFilter}
            onLabelFilterChange={setLabelFilter}
            createPending={createLabelMutation.isPending}
            onCreateLabel={(name) => createLabelMutation.mutate(name)}
          />

          <TaskDetailAdvanced
            open={sectionOpen.advanced}
            onToggle={toggleSection}
            upcomingReminders={upcomingReminders}
            reminderAtLocal={reminderAtLocal}
            onReminderAtLocalChange={setReminderAtLocal}
            reminderChannel={reminderChannel}
            onReminderChannelChange={setReminderChannel}
            notifPermission={notifPermission}
            onRequestBrowserNotifications={() => void requestBrowserNotifications()}
            createPending={createReminderMutation.isPending}
            deletePending={deleteReminderMutation.isPending}
            onAddReminder={() => createReminderMutation.mutate()}
            onDeleteReminder={(id) => deleteReminderMutation.mutate(id)}
            sourceRefs={task?.source_refs}
          />

          {updateMutation.isError && (
            <p className="form-error">{(updateMutation.error as Error).message}</p>
          )}
          <div className="form-actions destructive-row">
            <TaskDetailPromote
              promotePending={promoteMutation.isPending}
              onRequestPromote={() => setConfirmPromote(true)}
            />
            <button
              type="button"
              className="btn ghost danger-text"
              onClick={() => setConfirmDelete(true)}
            >
              Delete task
            </button>
          </div>
          </div>
          <div className="form-actions detail-form-footer">
            <button type="button" className="btn secondary" onClick={onClose}>
              Cancel
            </button>
            <button type="submit" className="btn primary" disabled={updateMutation.isPending}>
              {updateMutation.isPending ? "Saving…" : "Save"}
            </button>
          </div>
        </form>
      </aside>

      <ConfirmDialog
        open={confirmPromote}
        title="Promote to project?"
        message={`Create a new project from “${task.title}” and move this task (and its subtasks) into it?`}
        confirmLabel="Promote"
        pending={promoteMutation.isPending}
        onClose={() => setConfirmPromote(false)}
        onConfirm={() => promoteMutation.mutate()}
      />

      <ConfirmDialog
        open={confirmDelete}
        title="Delete task?"
        message={`Permanently delete "${task.title}"? Subtasks may be affected.`}
        confirmLabel="Delete"
        destructive
        pending={deleteMutation.isPending}
        onClose={() => setConfirmDelete(false)}
        onConfirm={() => {
          deleteMutation.mutate();
        }}
      />

      <TaskDetailCreateProject
        open={createProjectOpen}
        epics={epics}
        title={newProjectTitle}
        onTitleChange={setNewProjectTitle}
        epicId={newProjectEpicId}
        onEpicIdChange={setNewProjectEpicId}
        pending={createProjectMutation.isPending}
        errorMessage={
          createProjectMutation.isError
            ? (createProjectMutation.error as Error).message
            : null
        }
        onClose={() => setCreateProjectOpen(false)}
        onSubmit={handleCreateProjectSubmit}
      />
    </>
  );
}
