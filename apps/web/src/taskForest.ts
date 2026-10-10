// ==============================================================================
//  File: apps/web/src/taskForest.ts
//  Description: DFS forest ordering for task hierarchies (F7 board and list sibling order).
//  Component: Saved Views
//  Version: 1.0
//  Created: 2026-10-09
//  Last Update: 2026-10-10
// ==============================================================================

/** Minimal task shape for DFS forest ordering. */
export interface ForestTask {
  id: string;
  parent_task_id: string | null;
  sort_order: number;
}

function compareSiblings<T extends ForestTask>(a: T, b: T): number {
  if (a.sort_order !== b.sort_order) return a.sort_order - b.sort_order;
  return a.id.localeCompare(b.id);
}

export type ForestPeerOrder = "sort_order" | "stable";

/**
 * Order tasks as a forest DFS: each parent, then its children immediately under it.
 * Siblings default: sort_order, then id (created_at is not on the client Task type).
 * `peerOrder: "stable"` keeps sibling order as in the input array (server-sorted saved views).
 * Orphans (parent missing from the set) are treated as roots.
 * Cycles are broken; remaining nodes are visited after true roots.
 */
export function orderTasksForest<T extends ForestTask>(
  tasks: T[],
  options?: { peerOrder?: ForestPeerOrder },
): T[] {
  if (tasks.length <= 1) return tasks.slice();

  const byId = new Map<string, T>();
  for (const task of tasks) {
    byId.set(task.id, task);
  }

  const children = new Map<string | null, T[]>();
  for (const task of tasks) {
    const parentId = task.parent_task_id;
    const key = parentId && byId.has(parentId) ? parentId : null;
    const group = children.get(key);
    if (group) group.push(task);
    else children.set(key, [task]);
  }

  const peerOrder = options?.peerOrder ?? "sort_order";
  if (peerOrder === "stable") {
    const indexById = new Map(tasks.map((task, index) => [task.id, index]));
    for (const group of children.values()) {
      group.sort((a, b) => (indexById.get(a.id) ?? 0) - (indexById.get(b.id) ?? 0));
    }
  } else {
    for (const group of children.values()) {
      group.sort(compareSiblings);
    }
  }

  const result: T[] = [];
  const visiting = new Set<string>();
  const visited = new Set<string>();

  const visit = (task: T) => {
    if (visited.has(task.id) || visiting.has(task.id)) return;
    visiting.add(task.id);
    result.push(task);
    visited.add(task.id);
    for (const child of children.get(task.id) ?? []) {
      visit(child);
    }
    visiting.delete(task.id);
  };

  for (const root of children.get(null) ?? []) {
    visit(root);
  }

  // Cycle participants (or other stragglers) never reached from roots.
  for (const task of tasks) {
    if (!visited.has(task.id)) visit(task);
  }

  return result;
}

/** Parent id → direct children present in `tasks` (parent may be outside the set). */
export function buildChildrenByParent<T extends ForestTask>(
  tasks: T[],
): Map<string, T[]> {
  const byParent = new Map<string, T[]>();
  for (const task of tasks) {
    if (!task.parent_task_id) continue;
    const list = byParent.get(task.parent_task_id) ?? [];
    list.push(task);
    byParent.set(task.parent_task_id, list);
  }
  return byParent;
}

/** Descendant task ids reachable from `rootId` within the loaded `tasks` set. */
export function collectLoadedDescendantIds<T extends ForestTask>(
  tasks: T[],
  rootId: string,
): string[] {
  const byParent = buildChildrenByParent(tasks);
  const ids: string[] = [];
  const stack = [rootId];
  while (stack.length > 0) {
    const id = stack.pop()!;
    for (const child of byParent.get(id) ?? []) {
      ids.push(child.id);
      stack.push(child.id);
    }
  }
  return ids;
}

/** `rootId` plus all loaded descendants (empty when root is not in `tasks`). */
export function collectLoadedSubtreeIds<T extends ForestTask>(
  tasks: T[],
  rootId: string,
): string[] {
  if (!tasks.some((t) => t.id === rootId)) return [];
  return [rootId, ...collectLoadedDescendantIds(tasks, rootId)];
}

export function hasLoadedDescendants<T extends ForestTask>(
  tasks: T[],
  rootId: string,
): boolean {
  return collectLoadedDescendantIds(tasks, rootId).length > 0;
}
