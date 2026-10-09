import type { ViewSelection } from "./view";

const PRESENTATION_KEY = "theplan.taskPresentation";
const ROOTS_ONLY_KEY = "theplan.boardRootsOnly";
const WORK_FILTERS_KEY = "theplan.boardWorkFilters";

export interface BoardWorkFilters {
  projectId: string | null;
  epicId: string | null;
}

export function ownerWideBoardView(view: ViewSelection): boolean {
  return (
    view.type === "work" ||
    view.type === "inbox" ||
    view.type === "today" ||
    view.type === "upcoming"
  );
}

export function readBoardWorkFilters(): BoardWorkFilters {
  try {
    const raw = localStorage.getItem(WORK_FILTERS_KEY);
    if (!raw) return { projectId: null, epicId: null };
    const parsed = JSON.parse(raw) as Partial<BoardWorkFilters>;
    return {
      projectId: parsed.projectId ?? null,
      epicId: parsed.epicId ?? null,
    };
  } catch {
    return { projectId: null, epicId: null };
  }
}

export function writeBoardWorkFilters(filters: BoardWorkFilters) {
  try {
    localStorage.setItem(WORK_FILTERS_KEY, JSON.stringify(filters));
  } catch {
    /* ignore */
  }
}

export type TaskPresentation = "list" | "board";

export function boardViewSupported(view: ViewSelection): boolean {
  return (
    view.type === "project" ||
    view.type === "work" ||
    view.type === "inbox" ||
    view.type === "today" ||
    view.type === "upcoming" ||
    view.type === "epic" ||
    view.type === "label"
  );
}

export function readTaskPresentation(viewKey: string): TaskPresentation {
  try {
    const raw = localStorage.getItem(PRESENTATION_KEY);
    if (!raw) return "list";
    const map = JSON.parse(raw) as Record<string, TaskPresentation>;
    return map[viewKey] === "board" ? "board" : "list";
  } catch {
    return "list";
  }
}

export function writeTaskPresentation(viewKey: string, mode: TaskPresentation) {
  try {
    const raw = localStorage.getItem(PRESENTATION_KEY);
    const map: Record<string, TaskPresentation> = raw ? JSON.parse(raw) : {};
    map[viewKey] = mode;
    localStorage.setItem(PRESENTATION_KEY, JSON.stringify(map));
  } catch {
    /* ignore */
  }
}

export function readBoardRootsOnly(): boolean {
  try {
    return localStorage.getItem(ROOTS_ONLY_KEY) === "1";
  } catch {
    return false;
  }
}

export function writeBoardRootsOnly(value: boolean) {
  try {
    localStorage.setItem(ROOTS_ONLY_KEY, value ? "1" : "0");
  } catch {
    /* ignore */
  }
}
