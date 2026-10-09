/** Page item identity used when merging board column accumulators. */
export type AccumPageItem = { id: string };

/**
 * Merge a fetched page into the local accumulator.
 * Offset 0 replaces (first page / after reset); later pages append unseen ids.
 */
export function mergeAccumPage<T extends AccumPageItem>(
  prev: T[],
  pageItems: T[],
  offset: number,
): T[] {
  if (offset === 0) return pageItems;
  const seen = new Set(prev.map((t) => t.id));
  const appended = pageItems.filter((t) => !seen.has(t.id));
  return [...prev, ...appended];
}

/**
 * Whether an accumulator population effect should re-run after a move clears
 * local state. TanStack Query may keep the same `.data` reference when a
 * refetch returns unchanged content; if offset is already 0, only a bumped
 * `accumResetGen` forces repopulation.
 */
export function accumEffectDepsChanged(args: {
  prevDataRef: unknown;
  nextDataRef: unknown;
  prevOffset: number;
  nextOffset: number;
  prevResetGen: number;
  nextResetGen: number;
}): boolean {
  return (
    args.nextDataRef !== args.prevDataRef ||
    args.nextOffset !== args.prevOffset ||
    args.nextResetGen !== args.prevResetGen
  );
}

/**
 * Clear-on-move then restore from retained query cache when effect deps change.
 * Models Done and smart-open paths Dex reproduced.
 */
export function restoreAccumAfterMoveClear<T extends AccumPageItem>(args: {
  cachedPage: T[];
  prevDataRef: unknown;
  nextDataRef: unknown;
  prevOffset: number;
  nextOffset: number;
  prevResetGen: number;
  nextResetGen: number;
}): T[] {
  if (
    !accumEffectDepsChanged({
      prevDataRef: args.prevDataRef,
      nextDataRef: args.nextDataRef,
      prevOffset: args.prevOffset,
      nextOffset: args.nextOffset,
      prevResetGen: args.prevResetGen,
      nextResetGen: args.nextResetGen,
    })
  ) {
    return [];
  }
  return mergeAccumPage([], args.cachedPage, args.nextOffset);
}
