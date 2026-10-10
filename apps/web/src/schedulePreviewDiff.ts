import type {
  SchedulePreviewBlockRow,
  SchedulePreviewProposedBlock,
} from "./api";

export type ScheduleBlockChangeKind = "added" | "removed" | "moved" | "unchanged";

export interface ScheduleBlockChangeRow {
  taskId: string;
  kind: ScheduleBlockChangeKind;
  beforeStart: string | null;
  beforeEnd: string | null;
  afterStart: string | null;
  afterEnd: string | null;
}

function blockKey(taskId: string, start: string, end: string): string {
  return `${taskId}|${start}|${end}`;
}

/** Unpinned before rows vs proposed blocks — for readable before/after lists. */
export function listScheduleBlockChanges(
  beforeBlocks: SchedulePreviewBlockRow[],
  proposedBlocks: SchedulePreviewProposedBlock[],
  limit = 40,
): { rows: ScheduleBlockChangeRow[]; truncated: boolean } {
  const beforeUnpinned = beforeBlocks.filter((row) => !row.is_pinned);
  const beforeByTask = new Map<string, SchedulePreviewBlockRow[]>();
  for (const row of beforeUnpinned) {
    const list = beforeByTask.get(row.task_id) ?? [];
    list.push(row);
    beforeByTask.set(row.task_id, list);
  }

  const afterByTask = new Map<string, SchedulePreviewProposedBlock[]>();
  for (const row of proposedBlocks) {
    const list = afterByTask.get(row.task_id) ?? [];
    list.push(row);
    afterByTask.set(row.task_id, list);
  }

  const beforeSet = new Set(
    beforeUnpinned.map((row) => blockKey(row.task_id, row.start_time, row.end_time)),
  );
  const afterSet = new Set(
    proposedBlocks.map((row) => blockKey(row.task_id, row.start_time, row.end_time)),
  );

  const rows: ScheduleBlockChangeRow[] = [];

  for (const [taskId, afterRows] of afterByTask) {
    for (const after of afterRows) {
      const key = blockKey(taskId, after.start_time, after.end_time);
      if (beforeSet.has(key)) {
        rows.push({
          taskId,
          kind: "unchanged",
          beforeStart: after.start_time,
          beforeEnd: after.end_time,
          afterStart: after.start_time,
          afterEnd: after.end_time,
        });
        continue;
      }
      const beforeForTask = beforeByTask.get(taskId) ?? [];
      const matched = beforeForTask.find(
        (b) => !afterSet.has(blockKey(taskId, b.start_time, b.end_time)),
      );
      if (matched) {
        rows.push({
          taskId,
          kind: "moved",
          beforeStart: matched.start_time,
          beforeEnd: matched.end_time,
          afterStart: after.start_time,
          afterEnd: after.end_time,
        });
        beforeByTask.set(
          taskId,
          beforeForTask.filter((b) => b !== matched),
        );
      } else {
        rows.push({
          taskId,
          kind: "added",
          beforeStart: null,
          beforeEnd: null,
          afterStart: after.start_time,
          afterEnd: after.end_time,
        });
      }
    }
  }

  for (const row of beforeUnpinned) {
    const key = blockKey(row.task_id, row.start_time, row.end_time);
    if (!afterSet.has(key)) {
      const alreadyMoved = rows.some(
        (r) =>
          r.kind === "moved" &&
          r.taskId === row.task_id &&
          r.beforeStart === row.start_time &&
          r.beforeEnd === row.end_time,
      );
      if (!alreadyMoved) {
        rows.push({
          taskId: row.task_id,
          kind: "removed",
          beforeStart: row.start_time,
          beforeEnd: row.end_time,
          afterStart: null,
          afterEnd: null,
        });
      }
    }
  }

  const priority: Record<ScheduleBlockChangeKind, number> = {
    moved: 0,
    added: 1,
    removed: 2,
    unchanged: 3,
  };
  rows.sort((a, b) => priority[a.kind] - priority[b.kind]);

  const visible = rows.filter((r) => r.kind !== "unchanged");
  const truncated = visible.length > limit;
  return { rows: visible.slice(0, limit), truncated };
}

export function countPinnedBefore(beforeBlocks: SchedulePreviewBlockRow[]): number {
  return beforeBlocks.filter((row) => row.is_pinned).length;
}
