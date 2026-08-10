export type ViewSelection =
  | { type: "inbox" }
  | { type: "today" }
  | { type: "upcoming" }
  | { type: "calendar" }
  | { type: "project"; projectId: string }
  | { type: "labels" }
  | { type: "label"; labelId: string };

export function viewKey(view: ViewSelection): string {
  switch (view.type) {
    case "inbox":
      return "inbox";
    case "today":
      return "today";
    case "upcoming":
      return "upcoming";
    case "calendar":
      return "calendar";
    case "project":
      return `project:${view.projectId}`;
    case "labels":
      return "labels";
    case "label":
      return `label:${view.labelId}`;
  }
}

export function viewTitle(
  view: ViewSelection,
  options?: { projectTitle?: string; labelName?: string },
): string {
  switch (view.type) {
    case "inbox":
      return "Inbox";
    case "today":
      return "Today";
    case "upcoming":
      return "Upcoming";
    case "calendar":
      return "Calendar";
    case "project":
      return options?.projectTitle ?? "Project";
    case "labels":
      return "Labels";
    case "label":
      return options?.labelName ?? "Label";
  }
}

export function isToday(iso: string | null): boolean {
  if (!iso) return false;
  return isSameLocalDay(new Date(iso), new Date());
}

export function isUpcoming(iso: string | null, horizonDays = 7): boolean {
  if (!iso) return false;
  const due = new Date(iso);
  const start = startOfLocalDay(new Date());
  start.setDate(start.getDate() + 1);
  const end = startOfLocalDay(new Date());
  end.setDate(end.getDate() + 1 + horizonDays);
  return due >= start && due < end;
}

export function startOfLocalDay(d: Date): Date {
  const x = new Date(d);
  x.setHours(0, 0, 0, 0);
  return x;
}

export function endOfLocalDay(d: Date): Date {
  const x = startOfLocalDay(d);
  x.setDate(x.getDate() + 1);
  return x;
}

export function isSameLocalDay(a: Date, b: Date): boolean {
  return (
    a.getFullYear() === b.getFullYear() &&
    a.getMonth() === b.getMonth() &&
    a.getDate() === b.getDate()
  );
}

/** True if [start, end) overlaps the local calendar day of `day`. */
export function rangeOverlapsLocalDay(startIso: string, endIso: string, day: Date): boolean {
  const start = new Date(startIso);
  const end = new Date(endIso);
  const dayStart = startOfLocalDay(day);
  const dayEnd = endOfLocalDay(day);
  return start < dayEnd && end > dayStart;
}

export function formatDue(iso: string | null): string {
  if (!iso) return "";
  const due = new Date(iso);
  if (isToday(iso)) {
    return due.toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" });
  }
  return due.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

export function formatDuration(minutes: number | null | undefined): string {
  if (!minutes) return "";
  if (minutes < 60) return `${minutes}m`;
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  return m > 0 ? `${h}h ${m}m` : `${h}h`;
}
