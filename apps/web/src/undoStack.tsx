import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { useQueryClient } from "@tanstack/react-query";
import {
  completeTask,
  createTask,
  fetchTasks,
  uncompleteTask,
  updateTask,
  type Task,
  type TaskCreate,
} from "./api";

const MAX_DEPTH = 15;

export interface DeleteTreeNode {
  /** Original id before delete (for remapping parent links). */
  originalId: string;
  /** Original parent id (may be outside the deleted tree). */
  originalParentId: string | null;
  snapshot: TaskCreate;
}

export type UndoEntry =
  | { type: "complete"; taskId: string }
  | { type: "uncomplete"; taskId: string }
  | { type: "delete_tree"; nodes: DeleteTreeNode[] }
  | { type: "bulk_complete"; taskIds: string[] }
  | { type: "recurrence_advance"; taskId: string; previousDueAt: string | null };

type ToastListener = (message: string) => void;

interface UndoStackContextValue {
  push: (entry: UndoEntry) => void;
  undo: () => Promise<void>;
  canUndo: boolean;
}

const UndoStackContext = createContext<UndoStackContextValue | null>(null);

const TOAST_MESSAGES: Record<UndoEntry["type"], string> = {
  complete: "Undid complete",
  uncomplete: "Undid uncomplete",
  delete_tree: "Undid delete",
  bulk_complete: "Undid bulk complete",
  recurrence_advance: "Undid recurrence advance",
};

async function invalidateAfterUndo(queryClient: ReturnType<typeof useQueryClient>) {
  await Promise.all([
    queryClient.invalidateQueries({ queryKey: ["tasks"] }),
    queryClient.invalidateQueries({ queryKey: ["search"] }),
    queryClient.invalidateQueries({ queryKey: ["task"] }),
  ]);
}

export function UndoStackProvider({
  children,
  onToast,
}: {
  children: ReactNode;
  onToast?: ToastListener;
}) {
  const queryClient = useQueryClient();
  const stackRef = useRef<UndoEntry[]>([]);
  const [canUndo, setCanUndo] = useState(false);
  const onToastRef = useRef(onToast);
  onToastRef.current = onToast;

  const syncCanUndo = useCallback(() => {
    setCanUndo(stackRef.current.length > 0);
  }, []);

  const push = useCallback(
    (entry: UndoEntry) => {
      stackRef.current = [...stackRef.current, entry].slice(-MAX_DEPTH);
      syncCanUndo();
    },
    [syncCanUndo],
  );

  const undo = useCallback(async () => {
    const entry = stackRef.current.pop();
    if (!entry) return;
    syncCanUndo();

    try {
      switch (entry.type) {
        case "complete":
          await uncompleteTask(entry.taskId);
          break;
        case "uncomplete":
          await completeTask(entry.taskId, {});
          break;
        case "recurrence_advance":
          await updateTask(entry.taskId, { due_at: entry.previousDueAt });
          break;
        case "delete_tree": {
          const idMap = new Map<string, string>();
          for (const node of entry.nodes) {
            const parentRemapped =
              node.originalParentId === null
                ? null
                : (idMap.get(node.originalParentId) ?? node.originalParentId);
            const created = await createTask({
              ...node.snapshot,
              parent_task_id: parentRemapped,
            });
            idMap.set(node.originalId, created.id);
          }
          break;
        }
        case "bulk_complete":
          for (const taskId of entry.taskIds) {
            await uncompleteTask(taskId);
          }
          break;
      }
      await invalidateAfterUndo(queryClient);
      onToastRef.current?.(TOAST_MESSAGES[entry.type]);
    } catch {
      stackRef.current = [...stackRef.current, entry];
      syncCanUndo();
      onToastRef.current?.("Undo failed");
    }
  }, [queryClient, syncCanUndo]);

  const value = useMemo(
    () => ({ push, undo, canUndo }),
    [push, undo, canUndo],
  );

  return <UndoStackContext.Provider value={value}>{children}</UndoStackContext.Provider>;
}

export function useUndoStack(): UndoStackContextValue {
  const ctx = useContext(UndoStackContext);
  if (!ctx) {
    throw new Error("useUndoStack must be used within UndoStackProvider");
  }
  return ctx;
}

export function taskToCreateSnapshot(task: {
  title: string;
  description: string | null;
  project_id: string | null;
  section_id: string | null;
  parent_task_id: string | null;
  priority: TaskCreate["priority"];
  due_at: string | null;
  deadline_at?: string | null;
  soft_target_at?: string | null;
  estimated_duration_minutes: number;
  label_ids: string[];
}): TaskCreate {
  return {
    title: task.title,
    description: task.description,
    project_id: task.project_id,
    section_id: task.section_id,
    parent_task_id: task.parent_task_id,
    priority: task.priority,
    due_at: task.due_at,
    deadline_at: task.deadline_at ?? null,
    soft_target_at: task.soft_target_at ?? null,
    estimated_duration_minutes: task.estimated_duration_minutes,
    label_ids: task.label_ids,
  };
}

/** Parent-first BFS of task + descendants for delete undo recreate. */
export async function collectDeleteTree(root: Task): Promise<DeleteTreeNode[]> {
  const nodes: DeleteTreeNode[] = [];
  const queue: Task[] = [root];
  while (queue.length > 0) {
    const current = queue.shift()!;
    nodes.push({
      originalId: current.id,
      originalParentId: current.parent_task_id,
      snapshot: taskToCreateSnapshot(current),
    });
    const children = await fetchTasks({ parent_task_id: current.id, limit: 200 });
    queue.push(...children.items);
  }
  return nodes;
}

/** Open (incomplete) descendants of parentId present in `tasks` (any depth). */
export function collectOpenDescendantIds(tasks: Task[], parentId: string): string[] {
  const byParent = new Map<string, Task[]>();
  for (const task of tasks) {
    if (!task.parent_task_id) continue;
    const list = byParent.get(task.parent_task_id) ?? [];
    list.push(task);
    byParent.set(task.parent_task_id, list);
  }
  const ids: string[] = [];
  const stack = [parentId];
  while (stack.length > 0) {
    const id = stack.pop()!;
    for (const child of byParent.get(id) ?? []) {
      if (!child.is_completed) {
        ids.push(child.id);
        stack.push(child.id);
      }
    }
  }
  return ids;
}

/** Fetch incomplete descendants via API (accurate when list cache is partial). */
export async function fetchOpenDescendantIds(parentId: string): Promise<string[]> {
  const ids: string[] = [];
  const queue = [parentId];
  while (queue.length > 0) {
    const id = queue.shift()!;
    const children = await fetchTasks({
      parent_task_id: id,
      limit: 200,
      is_completed: false,
    });
    for (const child of children.items) {
      ids.push(child.id);
      queue.push(child.id);
    }
  }
  return ids;
}
