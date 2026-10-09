import type { ViewSelection } from "./view";

const PRESENTATION_KEY = "theplan.taskPresentation";
const ROOTS_ONLY_KEY = "theplan.boardRootsOnly";

export type TaskPresentation = "list" | "board";

export function boardViewSupported(view: ViewSelection): boolean {
  return (
    view.type === "project" ||
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
