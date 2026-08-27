import type { ReorderItem } from "./api";

/** Match taskForest / list display: sort_order, then id. */
function compareBySortOrderThenId<T extends { id: string; sort_order: number }>(
  a: T,
  b: T,
): number {
  if (a.sort_order !== b.sort_order) return a.sort_order - b.sort_order;
  return a.id.localeCompare(b.id);
}

function sortedByDisplayOrder<T extends { id: string; sort_order: number }>(items: T[]): T[] {
  return [...items].sort(compareBySortOrderThenId);
}

/**
 * Build PATCH items to move `itemId` one slot up/down among siblings.
 * When adjacent sort_orders differ, swaps those two values.
 * When they are equal (common for Inbox defaults of 0), renumbers the
 * whole sibling group 0..n-1 in the post-swap order so the move sticks.
 */
export function buildReorderSwap<T extends { id: string; sort_order: number }>(
  items: T[],
  itemId: string,
  direction: "up" | "down",
): ReorderItem[] | null {
  const sorted = sortedByDisplayOrder(items);
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

export function canReorderUp<T extends { id: string; sort_order: number }>(
  items: T[],
  itemId: string,
): boolean {
  const sorted = sortedByDisplayOrder(items);
  const index = sorted.findIndex((item) => item.id === itemId);
  return index > 0;
}

export function canReorderDown<T extends { id: string; sort_order: number }>(
  items: T[],
  itemId: string,
): boolean {
  const sorted = sortedByDisplayOrder(items);
  const index = sorted.findIndex((item) => item.id === itemId);
  return index >= 0 && index < sorted.length - 1;
}
