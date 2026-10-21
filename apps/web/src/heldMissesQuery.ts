import type { QueryClient } from "@tanstack/react-query";

/** React Query key for GET /schedule/held-misses. */
export const HELD_MISSES_QUERY_KEY = ["held-misses"] as const;

/** Invalidate held + explanation + calendar + preview-related caches after disposition writes. */
export function invalidateAfterHeldMutation(queryClient: QueryClient): void {
  void queryClient.invalidateQueries({ queryKey: HELD_MISSES_QUERY_KEY });
  void queryClient.invalidateQueries({ queryKey: ["schedule-explanation"] });
  void queryClient.invalidateQueries({ queryKey: ["scheduled-blocks"] });
  void queryClient.invalidateQueries({ queryKey: ["calendar-events"] });
  void queryClient.invalidateQueries({ queryKey: ["calendar-conflicts"] });
  void queryClient.invalidateQueries({ queryKey: ["tasks"] });
  void queryClient.invalidateQueries({ queryKey: ["settings"] });
  void queryClient.invalidateQueries({ queryKey: ["schedule-runs"] });
  void queryClient.invalidateQueries({ queryKey: ["schedule-run-stale-summary"] });
}
