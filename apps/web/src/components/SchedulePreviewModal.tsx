// ==============================================================================
//  File: apps/web/src/components/SchedulePreviewModal.tsx
//  Description: F6 replan preview modal — stale reasons, block diff, and apply (Calendar).
//  Component: Replan Preview
//  Version: 1.0
//  Created: 2026-10-09
//  Last Update: 2026-10-10
// ==============================================================================

import { useMemo } from "react";
import type { SchedulePreviewOut, StaleCategory, Task } from "../api";
import { formatScheduleReasonFact } from "../scheduleReasonFacts";
import {
  countPinnedBefore,
  listScheduleBlockChanges,
  type ScheduleBlockChangeKind,
} from "../schedulePreviewDiff";
import { Modal } from "./Modal";

const STALE_LABELS: Record<StaleCategory, string> = {
  duration: "duration changed",
  deadline: "deadline changed",
  map_style: "time map or style changed",
  deps: "dependencies changed",
  pins: "pins changed",
  project_daily_cap: "project daily cap changed",
  timezone_horizon_workweek: "timezone, horizon, or workweek changed",
  lifecycle: "completed, trash, or archive changed",
  busy_external: "busy time changed",
  prerequisite_state: "prerequisite state changed",
  due_at_soft_target: "due date or soft target changed",
  time_map_overrides: "time map overrides changed",
  provenance: "older snapshot",
};

const CHANGE_LABELS: Record<ScheduleBlockChangeKind, string> = {
  added: "New block",
  removed: "Removed",
  moved: "Moved",
  unchanged: "Unchanged",
};

function formatWhen(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString(undefined, {
    weekday: "short",
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

function taskTitle(taskId: string, tasksById: ReadonlyMap<string, Task>): string {
  const task = tasksById.get(taskId);
  return task?.title?.trim() || `Task ${taskId.slice(0, 8)}…`;
}

export interface SchedulePreviewModalProps {
  open: boolean;
  preview: SchedulePreviewOut | null;
  loading: boolean;
  applying: boolean;
  applyError: { message: string; code?: string; staleCategories?: StaleCategory[] } | null;
  tasksById: ReadonlyMap<string, Task>;
  onClose: () => void;
  onRefresh: () => void;
  onApply: () => void;
}

export function SchedulePreviewModal({
  open,
  preview,
  loading,
  applying,
  applyError,
  tasksById,
  onClose,
  onRefresh,
  onApply,
}: SchedulePreviewModalProps) {
  const proposal = preview?.proposal ?? null;
  const pinnedCount = proposal ? countPinnedBefore(proposal.before_blocks) : 0;

  const blockChanges = useMemo(() => {
    if (!proposal) return { rows: [], truncated: false };
    return listScheduleBlockChanges(proposal.before_blocks, proposal.proposed_blocks);
  }, [proposal]);

  const affectedOutcomes = useMemo(() => {
    if (!proposal?.outcomes?.length) return [];
    return proposal.outcomes.filter(
      (row) =>
        row.remaining_minutes > 0 ||
        row.placed_minutes !== row.requested_minutes - row.pinned_minutes ||
        row.primary_reason_code !== "placed",
    );
  }, [proposal]);

  const canApply = preview?.status === "ready" && !loading && !applying;
  const statusBanner = preview ? previewStatusMessage(preview) : null;

  return (
    <Modal
      open={open}
      title="Preview schedule changes"
      onClose={onClose}
      className="schedule-preview-modal"
    >
      {loading && !preview && (
        <p className="muted small" role="status">
          Calculating preview…
        </p>
      )}

      {preview?.status === "running" && (
        <p className="muted small" role="status">
          Still calculating…
        </p>
      )}

      {preview?.status === "failed" && (
        <p className="schedule-preview-error" role="alert">
          {preview.error_message || "Preview calculation failed."}
        </p>
      )}

      {statusBanner && (
        <p
          className={`schedule-preview-status${preview?.status === "ready" ? " ready" : " warn"}`}
          role="status"
        >
          {statusBanner}
        </p>
      )}

      {applyError && (
        <div className="schedule-preview-apply-error" role="alert">
          <p>{applyError.message}</p>
          {applyError.code === "PREVIEW_STALE" && applyError.staleCategories?.length ? (
            <p className="muted small">
              Inputs changed:{" "}
              {applyError.staleCategories.map((c) => STALE_LABELS[c] ?? c).join(", ")}.
            </p>
          ) : null}
          {(applyError.code === "PREVIEW_STALE" ||
            applyError.code === "PREVIEW_EXPIRED" ||
            applyError.code === "PREVIEW_PAST_BLOCKS") && (
            <button type="button" className="btn small secondary" onClick={onRefresh}>
              Generate fresh preview
            </button>
          )}
        </div>
      )}

      {proposal && preview && preview.status !== "failed" && (
        <>
          <section className="schedule-preview-section" aria-labelledby="preview-summary-heading">
            <h3 id="preview-summary-heading" className="schedule-preview-heading">
              Summary
            </h3>
            <dl className="schedule-preview-stats">
              <div>
                <dt>Blocks in proposal</dt>
                <dd>{proposal.blocks_created}</dd>
              </div>
              <div>
                <dt>Tasks scheduled</dt>
                <dd>{proposal.tasks_scheduled}</dd>
              </div>
              <div>
                <dt>Overbooked</dt>
                <dd>{proposal.overbooked_count}</dd>
              </div>
            </dl>
            <dl className="schedule-preview-diff-counts">
              <div>
                <dt>Added</dt>
                <dd>{preview.diff_counts.blocks_added}</dd>
              </div>
              <div>
                <dt>Removed</dt>
                <dd>{preview.diff_counts.blocks_removed}</dd>
              </div>
              <div>
                <dt>Moved</dt>
                <dd>{preview.diff_counts.blocks_moved}</dd>
              </div>
              <div>
                <dt>Unchanged (unpinned)</dt>
                <dd>{preview.diff_counts.blocks_unchanged}</dd>
              </div>
            </dl>
            {pinnedCount > 0 && (
              <p className="field-hint muted small">
                {pinnedCount} pinned block{pinnedCount === 1 ? "" : "s"} in the horizon — pinned
                times are not moved by replan; only unpinned blocks appear in the diff above.
              </p>
            )}
          </section>

          {blockChanges.rows.length > 0 && (
            <section className="schedule-preview-section" aria-labelledby="preview-blocks-heading">
              <h3 id="preview-blocks-heading" className="schedule-preview-heading">
                Block changes
              </h3>
              <ul className="schedule-preview-block-list">
                {blockChanges.rows.map((row, index) => (
                  <li key={`${row.taskId}-${row.kind}-${index}`}>
                    <span className="schedule-preview-change-kind">{CHANGE_LABELS[row.kind]}</span>
                    <span className="schedule-preview-change-task">
                      {taskTitle(row.taskId, tasksById)}
                    </span>
                    <span className="schedule-preview-change-times muted small">
                      {row.kind === "removed"
                        ? formatWhen(row.beforeStart)
                        : row.kind === "added"
                          ? formatWhen(row.afterStart)
                          : `${formatWhen(row.beforeStart)} → ${formatWhen(row.afterStart)}`}
                    </span>
                  </li>
                ))}
              </ul>
              {blockChanges.truncated && (
                <p className="muted small">Showing first changes only — run apply to see full calendar.</p>
              )}
            </section>
          )}

          {blockChanges.rows.length === 0 &&
            preview.diff_counts.blocks_added === 0 &&
            preview.diff_counts.blocks_removed === 0 &&
            preview.diff_counts.blocks_moved === 0 && (
              <p className="muted small" role="status">
                No unpinned block time changes in this horizon.
              </p>
            )}

          {affectedOutcomes.length > 0 && (
            <section className="schedule-preview-section" aria-labelledby="preview-tasks-heading">
              <h3 id="preview-tasks-heading" className="schedule-preview-heading">
                Affected tasks
              </h3>
              <ul className="schedule-preview-outcomes">
                {affectedOutcomes.slice(0, 25).map((row) => (
                  <li key={row.task_id}>
                    <strong>{taskTitle(row.task_id, tasksById)}</strong>
                    <span className="muted small">
                      {" "}
                      — {row.placed_minutes}/{row.requested_minutes} min placed
                      {row.remaining_minutes > 0 ? `, ${row.remaining_minutes} remaining` : ""}
                    </span>
                    {row.reason_facts.length > 0 && (
                      <ul className="schedule-preview-facts muted small">
                        {row.reason_facts.map((fact, i) => (
                          <li key={`${fact.code}-${i}`}>
                            {formatScheduleReasonFact(fact.code, fact.params)}
                          </li>
                        ))}
                      </ul>
                    )}
                  </li>
                ))}
              </ul>
              {affectedOutcomes.length > 25 && (
                <p className="muted small">{affectedOutcomes.length - 25} more tasks evaluated.</p>
              )}
            </section>
          )}
        </>
      )}

      <footer className="schedule-preview-actions">
        <button type="button" className="btn ghost" onClick={onClose} disabled={applying}>
          Close
        </button>
        <button
          type="button"
          className="btn secondary"
          onClick={onRefresh}
          disabled={loading || applying}
        >
          {loading ? "Refreshing…" : "Refresh preview"}
        </button>
        <button
          type="button"
          className="btn primary"
          onClick={onApply}
          disabled={!canApply}
          title={
            preview?.status === "stale"
              ? "Inputs changed — refresh preview first"
              : preview?.status === "expired"
                ? "Preview expired — refresh first"
                : undefined
          }
        >
          {applying ? "Applying…" : "Apply whole proposal"}
        </button>
      </footer>
    </Modal>
  );
}

function previewStatusMessage(preview: SchedulePreviewOut): string | null {
  if (preview.status === "ready" && preview.expires_at) {
    return `Ready to apply until ${formatWhen(preview.expires_at)}.`;
  }
  if (preview.status === "stale") {
    return "Inputs changed since this preview was calculated. Generate a fresh preview before applying.";
  }
  if (preview.status === "expired") {
    return "This preview expired. Generate a fresh preview to continue.";
  }
  if (preview.status === "applied") {
    return "This preview was already applied.";
  }
  return null;
}
