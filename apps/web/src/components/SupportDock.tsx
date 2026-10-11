// ==============================================================================
//  File: apps/web/src/components/SupportDock.tsx
//  Description: R3 shared support dock — calendar context, preview, task details.
//  Component: Shell
//  Version: 1.0
//  Created: 2026-10-11
//  Last Update: 2026-10-11
// ==============================================================================

import type { UseQueryResult } from "@tanstack/react-query";
import type { RefObject } from "react";
import type { Task } from "../api";
import { resolveSupportDockMode, type SupportDockMode } from "../supportDockState";
import { useSupportDock } from "../supportDockContext";
import { CalendarSupportIdle } from "./CalendarSupportIdle";
import { SchedulePreviewPanelContent } from "./SchedulePreviewPanelContent";
import { TaskDetailPanel, type TaskDetailPanelHandle } from "./TaskDetailPanel";

export interface SupportDockProps {
  isCalendarView: boolean;
  isNarrow: boolean;
  dockCollapsed: boolean;
  onToggleCollapse: () => void;
  selectedTaskId: string | null;
  selectedTaskQuery: UseQueryResult<Task, Error>;
  taskDetailRef: RefObject<TaskDetailPanelHandle | null>;
  onCloseTask: () => void;
  onSelectTask: (taskId: string) => void;
}

export function SupportDock({
  isCalendarView,
  isNarrow,
  dockCollapsed,
  onToggleCollapse,
  selectedTaskId,
  selectedTaskQuery,
  taskDetailRef,
  onCloseTask,
  onSelectTask,
}: SupportDockProps) {
  const {
    calendarSupport,
    previewOpen,
    previewPolling,
    previewData,
    previewApplying,
    previewApplyError,
    runSchedulePreview,
    refreshSchedulePreview,
    closeSchedulePreview,
    applySchedulePreview,
  } = useSupportDock();

  const mode: SupportDockMode = resolveSupportDockMode({
    isCalendarView,
    dockCollapsed: isNarrow ? false : dockCollapsed,
    selectedTaskId,
    previewOpen,
  });

  if (mode === "hidden") {
    if (isCalendarView && !isNarrow && dockCollapsed && !selectedTaskId) {
      return (
        <button
          type="button"
          className="support-dock-expand-tab"
          aria-label="Open calendar support panel"
          onClick={onToggleCollapse}
        >
          Support
        </button>
      );
    }
    return null;
  }

  if (mode === "task") {
    if (selectedTaskQuery.isLoading) {
      return (
        <aside className="support-dock task-detail-panel task-detail-sheet" aria-busy="true">
          <header className="detail-header support-dock-header">
            <h2>Task details</h2>
            <button type="button" className="icon-btn" onClick={onCloseTask} aria-label="Close panel">
              ×
            </button>
          </header>
          <div className="detail-shell-body support-dock-scroll">
            <p className="muted">Loading task…</p>
          </div>
        </aside>
      );
    }
    if (selectedTaskQuery.isError) {
      return (
        <aside className="support-dock task-detail-panel task-detail-sheet">
          <header className="detail-header support-dock-header">
            <h2>Task details</h2>
            <button type="button" className="icon-btn" onClick={onCloseTask} aria-label="Close panel">
              ×
            </button>
          </header>
          <div className="detail-shell-body support-dock-scroll">
            <p className="form-error">
              Failed to load task: {(selectedTaskQuery.error as Error).message}
            </p>
            <button type="button" className="btn secondary" onClick={onCloseTask}>
              Close
            </button>
          </div>
        </aside>
      );
    }
    return (
      <TaskDetailPanel
        ref={taskDetailRef}
        task={selectedTaskQuery.data ?? null}
        allTasks={selectedTaskQuery.data ? [selectedTaskQuery.data] : []}
        onClose={onCloseTask}
        showDockCollapse={isCalendarView && !isNarrow}
        onCollapseDock={onToggleCollapse}
      />
    );
  }

  const dockTitle =
    mode === "preview" ? "Preview schedule changes" : "Calendar support";

  return (
    <aside
      className={`support-dock task-detail-panel${isNarrow ? " task-detail-sheet" : ""}`}
      aria-label={dockTitle}
    >
      <header className="detail-header support-dock-header">
        <h2>{dockTitle}</h2>
        <div className="detail-header-actions">
          {!isNarrow && (
            <button
              type="button"
              className="btn ghost small support-dock-collapse-btn"
              onClick={onToggleCollapse}
              aria-label="Collapse support panel"
            >
              Collapse
            </button>
          )}
          {mode === "preview" && (
            <button
              type="button"
              className="icon-btn"
              onClick={closeSchedulePreview}
              aria-label="Close preview"
              disabled={previewApplying}
            >
              ×
            </button>
          )}
        </div>
      </header>

      {mode === "preview" && (
        <SchedulePreviewPanelContent
          preview={previewData}
          loading={previewPolling}
          applying={previewApplying}
          applyError={previewApplyError}
          tasksById={calendarSupport?.tasksById ?? new Map()}
          onClose={closeSchedulePreview}
          onRefresh={() => void refreshSchedulePreview()}
          onApply={() => void applySchedulePreview()}
          layout="dock"
        />
      )}

      {mode === "calendar-idle" && calendarSupport && (
        <div className="support-dock-scroll">
          <CalendarSupportIdle
            snapshot={calendarSupport}
            onOpenPreview={() => void runSchedulePreview()}
            previewReady={previewOpen && Boolean(previewData)}
            previewPolling={previewPolling}
            onSelectTask={onSelectTask}
          />
        </div>
      )}
    </aside>
  );
}
