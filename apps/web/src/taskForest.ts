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

/**
 * Order tasks as a forest DFS: each parent, then its children immediately under it.
 * Siblings: sort_order, then id (created_at is not on the client Task type).
 * Orphans (parent missing from the set) are treated as roots.
 * Cycles are broken; remaining nodes are visited after true roots.
 */
export function orderTasksForest<T extends ForestTask>(tasks: T[]): T[] {
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

  for (const group of children.values()) {
    group.sort(compareSiblings);
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
