import type { ReorderItem } from "./api";

export type ReorderComparable = { id: string; sort_order: number };

/** Match taskForest / list display: sort_order, then id. */
export function compareBySortOrderThenId<T extends ReorderComparable>(a: T, b: T): number {
  if (a.sort_order !== b.sort_order) return a.sort_order - b.sort_order;
  return a.id.localeCompare(b.id);
}

/** Match Sidebar saved-view display: sort_order, then name, then id. */
export function compareBySortOrderThenName<T extends ReorderComparable & { name: string }>(
  a: T,
  b: T,
): number {
  if (a.sort_order !== b.sort_order) return a.sort_order - b.sort_order;
  const byName = a.name.localeCompare(b.name);
  if (byName !== 0) return byName;
  return a.id.localeCompare(b.id);
}

function sortedByDisplayOrder<T extends ReorderComparable>(
  items: T[],
  compare: (a: T, b: T) => number = compareBySortOrderThenId,
): T[] {
  return [...items].sort(compare);
}

/**
 * Build PATCH items to move `itemId` one slot up/down among siblings.
 * When adjacent sort_orders differ, swaps those two values.
 * When they are equal (common for Inbox defaults of 0), renumbers the
 * whole sibling group 0..n-1 in the post-swap order so the move sticks.
 *
 * `compare` must match the rendered order (M2: saved views use name tie-break).
 */
export function buildReorderSwap<T extends ReorderComparable>(
  items: T[],
  itemId: string,
  direction: "up" | "down",
  compare: (a: T, b: T) => number = compareBySortOrderThenId,
): ReorderItem[] | null {
  const sorted = sortedByDisplayOrder(items, compare);
  const index = sorted.findIndex((item) => item.id === itemId);
  if (index === -1) return null;

  const swapIndex = direction === "up" ? index - 1 : index + 1;
  if (swapIndex < 0 || swapIndex >= sorted.length) return null;

  const current = sorted[index];
  const adjacent = sorted[swapIndex];

  if (current.sort_order !== adjacent.sort_order) {
    return [
      { id: current.id, sort_order: adjacent.sort_order },
      { id: adjacent.id, sort_order: current.sort_order },
    ];
  }

  const reordered = [...sorted];
  reordered[index] = adjacent;
  reordered[swapIndex] = current;

  const updates: ReorderItem[] = [];
  for (let i = 0; i < reordered.length; i++) {
    if (reordered[i].sort_order !== i) {
      updates.push({ id: reordered[i].id, sort_order: i });
    }
  }
  return updates.length > 0 ? updates : null;
}

export function canReorderUp<T extends ReorderComparable>(
  items: T[],
  itemId: string,
  compare: (a: T, b: T) => number = compareBySortOrderThenId,
): boolean {
  const sorted = sortedByDisplayOrder(items, compare);
  const index = sorted.findIndex((item) => item.id === itemId);
  return index > 0;
}

export function canReorderDown<T extends ReorderComparable>(
  items: T[],
  itemId: string,
  compare: (a: T, b: T) => number = compareBySortOrderThenId,
): boolean {
  const sorted = sortedByDisplayOrder(items, compare);
  const index = sorted.findIndex((item) => item.id === itemId);
  return index >= 0 && index < sorted.length - 1;
}
