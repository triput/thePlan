import type { ReorderItem } from "./api";

export function buildReorderSwap<T extends { id: string; sort_order: number }>(
  items: T[],
  itemId: string,
  direction: "up" | "down",
): ReorderItem[] | null {
  const sorted = [...items].sort((a, b) => a.sort_order - b.sort_order);
  const index = sorted.findIndex((item) => item.id === itemId);
  if (index === -1) return null;

  const swapIndex = direction === "up" ? index - 1 : index + 1;
  if (swapIndex < 0 || swapIndex >= sorted.length) return null;

  const current = sorted[index];
  const adjacent = sorted[swapIndex];
  return [
    { id: current.id, sort_order: adjacent.sort_order },
    { id: adjacent.id, sort_order: current.sort_order },
  ];
}

export function canReorderUp<T extends { id: string; sort_order: number }>(
  items: T[],
  itemId: string,
): boolean {
  const sorted = [...items].sort((a, b) => a.sort_order - b.sort_order);
  const index = sorted.findIndex((item) => item.id === itemId);
  return index > 0;
}

export function canReorderDown<T extends { id: string; sort_order: number }>(
  items: T[],
  itemId: string,
): boolean {
  const sorted = [...items].sort((a, b) => a.sort_order - b.sort_order);
  const index = sorted.findIndex((item) => item.id === itemId);
  return index >= 0 && index < sorted.length - 1;
}
