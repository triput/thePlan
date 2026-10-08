import { useCallback, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import {
  batchUpdateTasks,
  createScheduledBlockBundle,
  deleteTask,
  type ScheduleStyle,
  type Task,
  type TaskPriority,
} from "../api";
import { toISO } from "../calendarUtils";
import { fromDatetimeLocalValue } from "../components/CalendarBlockMenu";
import { emitToast } from "../components/ToastHost";

export interface UseTaskBatchActionsOptions {
  selectedIds: Set<string>;
  tasks: Task[];
  clearSelection: () => void;
  invalidateTasks: () => void;
}

export function useTaskBatchActions({
  selectedIds,
  tasks,
  clearSelection,
  invalidateTasks,
}: UseTaskBatchActionsOptions) {
  const queryClient = useQueryClient();
  const [batchBusy, setBatchBusy] = useState(false);

  const runBatch = useCallback(
    async (action: () => Promise<void>, successMessage: string) => {
      setBatchBusy(true);
      try {
        await action();
        clearSelection();
        invalidateTasks();
        emitToast(successMessage);
      } catch (err) {
        emitToast(err instanceof Error ? err.message : "Batch action failed");
        invalidateTasks();
      } finally {
        setBatchBusy(false);
      }
    },
    [clearSelection, invalidateTasks],
  );

  const handleBatchScheduleStyle = useCallback(
    (style: ScheduleStyle) => {
      const ids = [...selectedIds];
      if (ids.length === 0) return;
      void runBatch(
        async () => {
          await batchUpdateTasks({
            task_ids: ids,
            patch: { schedule_style: style },
          });
        },
        `Set schedule style on ${ids.length} task${ids.length === 1 ? "" : "s"}`,
      );
    },
    [runBatch, selectedIds],
  );

  const handleBatchApplyLabel = useCallback(
    (labelId: string) => {
      const ids = [...selectedIds];
      if (ids.length === 0 || !labelId) return;
      void runBatch(
        async () => {
          await batchUpdateTasks({
            task_ids: ids,
            add_label_ids: [labelId],
          });
        },
        `Applied label to ${ids.length} task${ids.length === 1 ? "" : "s"}`,
      );
    },
    [runBatch, selectedIds],
  );

  const handleBatchDueDate = useCallback(
    (dateValue: string) => {
      const ids = [...selectedIds];
      if (ids.length === 0 || !dateValue) return;
      const [y, m, d] = dateValue.split("-").map(Number);
      if (!y || !m || !d) return;
      const localEnd = new Date(y, m - 1, d, 23, 59, 0, 0);
      const dueAt = localEnd.toISOString();
      void runBatch(
        async () => {
          await batchUpdateTasks({
            task_ids: ids,
            patch: { due_at: dueAt },
          });
        },
        `Set due date on ${ids.length} task${ids.length === 1 ? "" : "s"}`,
      );
    },
    [runBatch, selectedIds],
  );

  const handleBatchPriority = useCallback(
    (priority: TaskPriority) => {
      const ids = [...selectedIds];
      if (ids.length === 0) return;
      void runBatch(
        async () => {
          await batchUpdateTasks({
            task_ids: ids,
            patch: { priority },
          });
        },
        `Set priority on ${ids.length} task${ids.length === 1 ? "" : "s"}`,
      );
    },
    [runBatch, selectedIds],
  );

  const handleBatchClearDue = useCallback(() => {
    const ids = [...selectedIds];
    if (ids.length === 0) return;
    void runBatch(
      async () => {
        await batchUpdateTasks({
          task_ids: ids,
          patch: { due_at: null },
        });
      },
      `Cleared due date on ${ids.length} task${ids.length === 1 ? "" : "s"}`,
    );
  }, [runBatch, selectedIds]);

  const handleBatchMoveToProject = useCallback(
    (projectId: string | null) => {
      const ids = [...selectedIds];
      if (ids.length === 0) return;
      void runBatch(
        async () => {
          await batchUpdateTasks({
            task_ids: ids,
            patch: {
              project_id: projectId,
              section_id: null,
              parent_task_id: null,
            },
          });
        },
        projectId
          ? `Moved ${ids.length} task${ids.length === 1 ? "" : "s"} to project`
          : `Moved ${ids.length} task${ids.length === 1 ? "" : "s"} to Inbox`,
      );
    },
    [runBatch, selectedIds],
  );

  const handleBatchDelete = useCallback(() => {
    const ids = [...selectedIds];
    if (ids.length === 0) return;
    const ok = window.confirm(
      `Delete ${ids.length} selected task${ids.length === 1 ? "" : "s"}? This cannot be undone from here.`,
    );
    if (!ok) return;
    void runBatch(
      async () => {
        const results = await Promise.allSettled(ids.map((id) => deleteTask(id)));
        const failed = results.filter((r) => r.status === "rejected").length;
        if (failed > 0) {
          throw new Error(
            `Deleted ${ids.length - failed} of ${ids.length}; ${failed} failed`,
          );
        }
      },
      `Deleted ${ids.length} task${ids.length === 1 ? "" : "s"}`,
    );
  }, [runBatch, selectedIds]);

  const handleBlockAsBundle = useCallback(
    (startLocal: string, isPinned: boolean) => {
      const ids = [...selectedIds];
      if (ids.length === 0) return;
      if (!startLocal.trim()) {
        emitToast("Pick a bundle start time");
        return;
      }

      const byId = new Map(tasks.map((t) => [t.id, t]));
      const start_time = toISO(fromDatetimeLocalValue(startLocal));
      const pinFields = isPinned ? { is_pinned: true as const } : {};

      let body:
        | ({ member_task_ids: string[]; start_time: string } & typeof pinFields)
        | ({ parent_task_id: string; start_time: string } & typeof pinFields);

      if (ids.length === 1) {
        const task = byId.get(ids[0]);
        if (!task || task.open_subtask_count <= 0) {
          emitToast("Select 2+ tasks, or one parent with subtasks");
          return;
        }
        body = { parent_task_id: task.id, start_time, ...pinFields };
      } else {
        body = { member_task_ids: ids, start_time, ...pinFields };
      }

      void runBatch(async () => {
        await createScheduledBlockBundle(body);
        void queryClient.invalidateQueries({ queryKey: ["scheduled-blocks"] });
      }, "Blocked as bundle on calendar");
    },
    [queryClient, runBatch, selectedIds, tasks],
  );

  return {
    batchBusy,
    handleBatchScheduleStyle,
    handleBatchApplyLabel,
    handleBatchPriority,
    handleBatchDueDate,
    handleBatchClearDue,
    handleBatchMoveToProject,
    handleBatchDelete,
    handleBlockAsBundle,
  };
}
