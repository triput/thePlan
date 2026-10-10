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
  /** null = omit completion dimension (matches open and done on the server). */
  completion: SavedViewCompletion | null;
  scheduleStatuses: string[];
  scheduleStyles: string[];
  /** null = omit due dimension */
  dueKind: "none" | "unbounded" | "fixed" | "rolling" | null;
  dueRolling: SavedViewDueRolling | null;
  dueWithinDays: number;
  /** Inclusive calendar dates (YYYY-MM-DD) for fixed range UI */
  dueFixedFrom: string;
  dueFixedTo: string;
  /** Absolute bounds from the server — preserved when display dates are unchanged. */
  dueFixedFromIso?: string;
  dueFixedToIso?: string;
  /** Display values at load time; used to detect rename-only / non-due edits. */
  dueFixedFromBaseline?: string;
  dueFixedToBaseline?: string;
}

export interface SavedViewPredicateAdapterOptions {
  /** Owner timezone for fixed due display and new date-only bounds. */
  userTimezone?: string;
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

function ymdInTimeZone(instant: Date, timeZone: string): string {
  return new Intl.DateTimeFormat("en-CA", {
    timeZone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(instant);
}

function getTimeZoneOffsetMs(utcMs: number, timeZone: string): number {
  const d = new Date(utcMs);
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone,
    hourCycle: "h23",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  }).formatToParts(d);
  const map: Record<string, number> = {};
  for (const part of parts) {
    if (part.type !== "literal") map[part.type] = Number(part.value);
  }
  const asUtc = Date.UTC(
    map.year,
    map.month - 1,
    map.day,
    map.hour,
    map.minute,
    map.second ?? 0,
  );
  return asUtc - utcMs;
}

/** Wall clock in IANA zone → UTC instant (mirrors scheduler / timeMapOverrides). */
function zonedDateTimeToUtc(ymd: string, hour: number, minute: number, timeZone: string): Date {
  const [y, mo, d] = ymd.split("-").map(Number);
  let ms = Date.UTC(y, mo - 1, d, hour, minute);
  for (let i = 0; i < 4; i++) {
    ms = Date.UTC(y, mo - 1, d, hour, minute) - getTimeZoneOffsetMs(ms, timeZone);
  }
  return new Date(ms);
}

function resolvedTimezone(options?: SavedViewPredicateAdapterOptions): string {
  const fromSettings = options?.userTimezone?.trim();
  if (fromSettings) return fromSettings;
  return Intl.DateTimeFormat().resolvedOptions().timeZone;
}

function addDaysToYmd(ymd: string, days: number): string {
  const [y, mo, d] = ymd.split("-").map(Number);
  const dt = new Date(Date.UTC(y, mo - 1, d + days));
  return dt.toISOString().slice(0, 10);
}

function fixedDueDisplayFromIso(
  fromIso: string,
  toExclusiveIso: string,
  timeZone: string,
): { from: string; to: string } {
  const fromYmd = ymdInTimeZone(new Date(fromIso), timeZone);
  const endInclusive = new Date(toExclusiveIso);
  endInclusive.setMilliseconds(endInclusive.getMilliseconds() - 1);
  const toYmd = ymdInTimeZone(endInclusive, timeZone);
  return { from: fromYmd, to: toYmd };
}

function fixedDueIsoFromDisplay(
  fromYmd: string,
  toInclusiveYmd: string,
  timeZone: string,
): { from: string; to: string } {
  const from = zonedDateTimeToUtc(fromYmd, 0, 0, timeZone).toISOString();
  const to = zonedDateTimeToUtc(addDaysToYmd(toInclusiveYmd, 1), 0, 0, timeZone).toISOString();
  return { from, to };
}

function isValidYmd(dateStr: string): boolean {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(dateStr.trim())) return false;
  const [y, mo, d] = dateStr.split("-").map(Number);
  const dt = new Date(Date.UTC(y, mo - 1, d));
  return (
    dt.getUTCFullYear() === y &&
    dt.getUTCMonth() === mo - 1 &&
    dt.getUTCDate() === d
  );
}

/** Client-side validation before save; returns a user-facing message or null. */
export function validateSavedViewFilterDraft(draft: SavedViewFilterDraft): string | null {
  if (draft.dueKind !== "fixed") return null;

  const from = draft.dueFixedFrom.trim();
  const to = draft.dueFixedTo.trim();
  if (!from || !to) {
    return "Fixed due range requires both From and To dates.";
  }
  if (!isValidYmd(from) || !isValidYmd(to)) {
    return "Fixed due dates must be valid calendar dates.";
  }
  if (from > to) {
    return "Fixed due From must be on or before To.";
  }
  return null;
}

export function predicateFromDraft(
  draft: SavedViewFilterDraft,
  options?: SavedViewPredicateAdapterOptions,
): SavedViewPredicateV1 {
  const dimensions: Record<string, unknown> = {};

  if (draft.inbox) dimensions.inbox = true;
  if (draft.projectIds.length > 0) dimensions.project_ids = [...draft.projectIds];
  if (draft.epicIds.length > 0) dimensions.epic_ids = [...draft.epicIds];
  if (draft.labelIds.length > 0) {
    dimensions.labels = { ids: [...draft.labelIds], match: draft.labelMatch };
  }
  if (draft.priorities.length > 0) dimensions.priorities = [...draft.priorities];
  if (draft.workflowStates.length > 0) dimensions.workflow_states = [...draft.workflowStates];
  if (draft.completion !== null) dimensions.completion = draft.completion;
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
    const validationError = validateSavedViewFilterDraft(draft);
    if (validationError) {
      throw new Error(validationError);
    }
    const fromDisplay = draft.dueFixedFrom.trim();
    const toDisplay = draft.dueFixedTo.trim();
    const unchangedFixed =
      draft.dueFixedFromIso &&
      draft.dueFixedToIso &&
      fromDisplay === (draft.dueFixedFromBaseline ?? "") &&
      toDisplay === (draft.dueFixedToBaseline ?? "");

    if (unchangedFixed) {
      dimensions.due = {
        kind: "fixed",
        from: draft.dueFixedFromIso,
        to: draft.dueFixedToIso,
      };
    } else {
      const tz = resolvedTimezone(options);
      const bounds = fixedDueIsoFromDisplay(fromDisplay, toDisplay, tz);
      dimensions.due = { kind: "fixed", from: bounds.from, to: bounds.to };
    }
  }

  return { v: 1, dimensions };
}

export function draftFromPredicate(
  raw: unknown,
  options?: SavedViewPredicateAdapterOptions,
): SavedViewFilterDraft {
  const draft = defaultSavedViewFilterDraft();
  draft.completion = null;
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
      draft.dueFixedFromIso = due.from;
      draft.dueFixedToIso = due.to;
      const tz = resolvedTimezone(options);
      const display = fixedDueDisplayFromIso(due.from, due.to, tz);
      draft.dueFixedFrom = display.from;
      draft.dueFixedTo = display.to;
      draft.dueFixedFromBaseline = display.from;
      draft.dueFixedToBaseline = display.to;
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
