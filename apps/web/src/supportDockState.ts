export type SupportDockMode = "hidden" | "calendar-idle" | "preview" | "task";

export type DirtyNavigationKind =
  | "switch_task"
  | "close_task"
  | "return_to_calendar_support"
  | "close_preview"
  | "change_view"
  | "collapse_dock";

export interface DirtyPromptCopy {
  title: string;
  message: string;
  saveLabel: string;
  discardLabel: string;
}

export interface ResolveSupportDockModeInput {
  isCalendarView: boolean;
  dockCollapsed: boolean;
  selectedTaskId: string | null;
  previewOpen: boolean;
}

/**
 * Pure mode resolver for the shared support dock.
 * When collapsed, calendar preview/idle surfaces hide; callers should clear
 * `selectedTaskId` on collapse so an open task does not stay visible.
 */
export function resolveSupportDockMode(input: ResolveSupportDockModeInput): SupportDockMode {
  if (input.selectedTaskId) return "task";
  if (input.isCalendarView && input.previewOpen && !input.dockCollapsed) return "preview";
  if (input.isCalendarView && !input.dockCollapsed) return "calendar-idle";
  return "hidden";
}

export function dockPanelVisible(mode: SupportDockMode): boolean {
  return mode !== "hidden";
}

export function dirtyPromptFor(
  kind: DirtyNavigationKind,
  context?: { nextTaskTitle?: string; viewLabel?: string },
): DirtyPromptCopy {
  switch (kind) {
    case "switch_task":
      return {
        title: "Unsaved task changes",
        message: context?.nextTaskTitle
          ? `Save your edits before opening “${context.nextTaskTitle}”?`
          : "Save your edits before opening the other task?",
        saveLabel: "Save and open",
        discardLabel: "Discard",
      };
    case "close_task":
      return {
        title: "Unsaved task changes",
        message: "Save your edits before closing task details?",
        saveLabel: "Save and close",
        discardLabel: "Discard",
      };
    case "return_to_calendar_support":
      return {
        title: "Unsaved task changes",
        message: "Save your edits before returning to calendar support?",
        saveLabel: "Save and continue",
        discardLabel: "Discard",
      };
    case "close_preview":
      return {
        title: "Unsaved task changes",
        message: "Save your edits before closing task details and showing the schedule preview?",
        saveLabel: "Save and show preview",
        discardLabel: "Discard",
      };
    case "change_view":
      return {
        title: "Unsaved task changes",
        message: context?.viewLabel
          ? `Save your edits before switching to ${context.viewLabel}?`
          : "Save your edits before leaving this view?",
        saveLabel: "Save and switch",
        discardLabel: "Discard",
      };
    case "collapse_dock":
      return {
        title: "Unsaved task changes",
        message: "Save your edits before collapsing the support panel?",
        saveLabel: "Save and collapse",
        discardLabel: "Discard",
      };
    default: {
      const _exhaustive: never = kind;
      return _exhaustive;
    }
  }
}

export function shouldOfferDirtyPrompt(isDirty: boolean): boolean {
  return isDirty;
}
