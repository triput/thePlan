export type ViewSelection =
  | { type: "inbox" }
  | { type: "today" }
  | { type: "upcoming" }
  | { type: "project"; projectId: string };

export function viewKey(view: ViewSelection): string {
  switch (view.type) {
    case "inbox":
      return "inbox";
    case "today":
      return "today";
    case "upcoming":
      return "upcoming";
    case "project":
      return `project:${view.projectId}`;
  }
}

export function viewTitle(view: ViewSelection, projectTitle?: string): string {
  switch (view.type) {
    case "inbox":
      return "Inbox";
    case "today":
      return "Today";
    case "upcoming":
      return "Upcoming";
    case "project":
      return projectTitle ?? "Project";
  }
}

export function isToday(iso: string | null): boolean {
  if (!iso) return false;
  const due = new Date(iso);
  const now = new Date();
  return (
    due.getFullYear() === now.getFullYear() &&
    due.getMonth() === now.getMonth() &&
    due.getDate() === now.getDate()
  );
}

export function isUpcoming(iso: string | null): boolean {
  if (!iso) return false;
  const due = new Date(iso);
  const endOfToday = new Date();
  endOfToday.setHours(23, 59, 59, 999);
  return due > endOfToday;
}

export function formatDue(iso: string | null): string {
  if (!iso) return "";
  const due = new Date(iso);
  const now = new Date();
  const sameDay =
    due.getFullYear() === now.getFullYear() &&
    due.getMonth() === now.getMonth() &&
    due.getDate() === now.getDate();
  if (sameDay) {
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
