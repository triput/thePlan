import type {
  SavedViewCompletion,
  SavedViewDueRolling,
  SavedViewLabelMatch,
  SavedViewPredicateV1,
  TaskPriority,
  TaskWorkflowState,
} from "./api";

export interface SavedViewFilterDraft {
  inbox: boolean;
  projectIds: string[];
  epicIds: string[];
  labelIds: string[];
  labelMatch: SavedViewLabelMatch;
  priorities: TaskPriority[];
  workflowStates: TaskWorkflowState[];
  completion: SavedViewCompletion;
  scheduleStatuses: string[];
  scheduleStyles: string[];
  /** null = omit due dimension */
  dueKind: "none" | "unbounded" | "fixed" | "rolling" | null;
  dueRolling: SavedViewDueRolling | null;
  dueWithinDays: number;
  /** ISO date or datetime for fixed range (from inclusive) */
  dueFixedFrom: string;
  dueFixedTo: string;
}

export function defaultSavedViewFilterDraft(): SavedViewFilterDraft {
  return {
    inbox: false,
    projectIds: [],
    epicIds: [],
    labelIds: [],
    labelMatch: "any",
    priorities: [],
    workflowStates: [],
    completion: "open",
    scheduleStatuses: [],
    scheduleStyles: [],
    dueKind: null,
    dueRolling: null,
    dueWithinDays: 7,
    dueFixedFrom: "",
    dueFixedTo: "",
  };
}

function localDateToIsoStart(dateStr: string): string | null {
  if (!dateStr.trim()) return null;
  const d = new Date(`${dateStr}T00:00:00`);
  if (Number.isNaN(d.getTime())) return null;
  return d.toISOString();
}

function localDateToIsoEndExclusive(dateStr: string): string | null {
  if (!dateStr.trim()) return null;
  const d = new Date(`${dateStr}T00:00:00`);
  if (Number.isNaN(d.getTime())) return null;
  d.setDate(d.getDate() + 1);
  return d.toISOString();
}

export function predicateFromDraft(draft: SavedViewFilterDraft): SavedViewPredicateV1 {
  const dimensions: Record<string, unknown> = {};

  if (draft.inbox) dimensions.inbox = true;
  if (draft.projectIds.length > 0) dimensions.project_ids = [...draft.projectIds];
  if (draft.epicIds.length > 0) dimensions.epic_ids = [...draft.epicIds];
  if (draft.labelIds.length > 0) {
    dimensions.labels = { ids: [...draft.labelIds], match: draft.labelMatch };
  }
  if (draft.priorities.length > 0) dimensions.priorities = [...draft.priorities];
  if (draft.workflowStates.length > 0) dimensions.workflow_states = [...draft.workflowStates];
  if (draft.completion !== "open") dimensions.completion = draft.completion;
  else dimensions.completion = "open";
  if (draft.scheduleStatuses.length > 0) dimensions.schedule_statuses = [...draft.scheduleStatuses];
  if (draft.scheduleStyles.length > 0) dimensions.schedule_styles = [...draft.scheduleStyles];

  if (draft.dueKind === "none") {
    dimensions.due = { kind: "none" };
  } else if (draft.dueKind === "unbounded") {
    dimensions.due = { kind: "unbounded" };
  } else if (draft.dueKind === "rolling" && draft.dueRolling) {
    if (draft.dueRolling === "within_days") {
      dimensions.due = { kind: "rolling", rolling: "within_days", days: draft.dueWithinDays };
    } else {
      dimensions.due = { kind: "rolling", rolling: draft.dueRolling };
    }
  } else if (draft.dueKind === "fixed") {
    const from = localDateToIsoStart(draft.dueFixedFrom);
    const to = localDateToIsoEndExclusive(draft.dueFixedTo);
    if (from && to) {
      dimensions.due = { kind: "fixed", from, to };
    }
  }

  return { v: 1, dimensions };
}

export function draftFromPredicate(raw: unknown): SavedViewFilterDraft {
  const draft = defaultSavedViewFilterDraft();
  if (!raw || typeof raw !== "object") return draft;
  const pred = raw as SavedViewPredicateV1;
  const dims = pred.dimensions;
  if (!dims || typeof dims !== "object") return draft;

  if (dims.inbox === true) draft.inbox = true;
  if (Array.isArray(dims.project_ids)) {
    draft.projectIds = dims.project_ids.filter((x): x is string => typeof x === "string");
  }
  if (Array.isArray(dims.epic_ids)) {
    draft.epicIds = dims.epic_ids.filter((x): x is string => typeof x === "string");
  }
  if (dims.labels && typeof dims.labels === "object") {
    const labels = dims.labels as { ids?: unknown; match?: unknown };
    if (Array.isArray(labels.ids)) {
      draft.labelIds = labels.ids.filter((x): x is string => typeof x === "string");
    }
    if (labels.match === "all" || labels.match === "any") draft.labelMatch = labels.match;
  }
  if (Array.isArray(dims.priorities)) {
    draft.priorities = dims.priorities.filter((x): x is TaskPriority =>
      x === "p1" || x === "p2" || x === "p3" || x === "p4",
    );
  }
  if (Array.isArray(dims.workflow_states)) {
    draft.workflowStates = dims.workflow_states.filter(
      (x): x is TaskWorkflowState =>
        x === "ready" || x === "in_progress" || x === "waiting",
    );
  }
  if (dims.completion === "open" || dims.completion === "done" || dims.completion === "any") {
    draft.completion = dims.completion;
  }
  if (Array.isArray(dims.schedule_statuses)) {
    draft.scheduleStatuses = dims.schedule_statuses.filter((x) => typeof x === "string") as string[];
  }
  if (Array.isArray(dims.schedule_styles)) {
    draft.scheduleStyles = dims.schedule_styles.filter((x) => typeof x === "string") as string[];
  }
  if (dims.due && typeof dims.due === "object") {
    const due = dims.due as Record<string, unknown>;
    const kind = due.kind;
    if (kind === "none" || kind === "unbounded" || kind === "fixed" || kind === "rolling") {
      draft.dueKind = kind;
    }
    if (kind === "rolling" && typeof due.rolling === "string") {
      if (
        due.rolling === "today" ||
        due.rolling === "next_7_days" ||
        due.rolling === "this_calendar_week" ||
        due.rolling === "within_days"
      ) {
        draft.dueRolling = due.rolling;
      }
      if (typeof due.days === "number") draft.dueWithinDays = due.days;
    }
    if (kind === "fixed" && typeof due.from === "string" && typeof due.to === "string") {
      draft.dueFixedFrom = due.from.slice(0, 10);
      const toDate = new Date(due.to);
      if (!Number.isNaN(toDate.getTime())) {
        toDate.setDate(toDate.getDate() - 1);
        draft.dueFixedTo = toDate.toISOString().slice(0, 10);
      }
    }
  }

  return draft;
}

export function stripInvalidRefsFromDraft(
  draft: SavedViewFilterDraft,
  invalidRefs: { kind: string; id: string }[],
): SavedViewFilterDraft {
  if (invalidRefs.length === 0) return draft;
  const next = { ...draft, projectIds: [...draft.projectIds], epicIds: [...draft.epicIds], labelIds: [...draft.labelIds] };
  for (const ref of invalidRefs) {
    if (ref.kind === "project") {
      next.projectIds = next.projectIds.filter((id) => id !== ref.id);
    } else if (ref.kind === "epic") {
      next.epicIds = next.epicIds.filter((id) => id !== ref.id);
    } else if (ref.kind === "label") {
      next.labelIds = next.labelIds.filter((id) => id !== ref.id);
    }
  }
  return next;
}
