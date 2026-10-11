import { useCallback, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import {
  ApiError,
  fetchSchedulePreview,
  postSchedulePreview,
  postSchedulePreviewApply,
  type SchedulePreviewOut,
  type StaleCategory,
} from "../api";
import { emitToast } from "../components/ToastHost";

const REPLAN_POLL_MS = 500;
const REPLAN_TIMEOUT_MS = 60_000;

export interface SchedulePreviewApplyError {
  message: string;
  code?: string;
  staleCategories?: StaleCategory[];
}

export function useSchedulePreviewActions() {
  const queryClient = useQueryClient();
  const [previewOpen, setPreviewOpen] = useState(false);
  const [previewPolling, setPreviewPolling] = useState(false);
  const [previewData, setPreviewData] = useState<SchedulePreviewOut | null>(null);
  const [previewApplying, setPreviewApplying] = useState(false);
  const [previewApplyError, setPreviewApplyError] = useState<SchedulePreviewApplyError | null>(null);

  const invalidateCalendar = useCallback(() => {
    queryClient.invalidateQueries({ queryKey: ["scheduled-blocks"] });
    queryClient.invalidateQueries({ queryKey: ["calendar-events"] });
    queryClient.invalidateQueries({ queryKey: ["calendar-conflicts"] });
    queryClient.invalidateQueries({ queryKey: ["tasks"] });
    queryClient.invalidateQueries({ queryKey: ["schedule-explanation"] });
    queryClient.invalidateQueries({ queryKey: ["schedule-runs"] });
    queryClient.invalidateQueries({ queryKey: ["schedule-run-stale-summary"] });
  }, [queryClient]);

  const pollPreviewUntilSettled = useCallback(async (previewId: string) => {
    let preview = await fetchSchedulePreview(previewId);
    const deadline = Date.now() + REPLAN_TIMEOUT_MS;
    while (preview.status === "running" && Date.now() < deadline) {
      await new Promise((resolve) => setTimeout(resolve, REPLAN_POLL_MS));
      preview = await fetchSchedulePreview(previewId);
    }
    if (preview.status === "running") {
      preview = await fetchSchedulePreview(previewId);
    }
    return preview;
  }, []);

  const runSchedulePreview = useCallback(async () => {
    setPreviewApplyError(null);
    setPreviewPolling(true);
    setPreviewOpen(true);
    try {
      const started = await postSchedulePreview();
      const settled = await pollPreviewUntilSettled(started.id);
      setPreviewData(settled);
      if (settled.status === "running") {
        emitToast("Preview is still running — refresh from the panel in a moment");
      }
    } catch (err) {
      emitToast(err instanceof Error ? err.message : "Couldn't start schedule preview");
      setPreviewOpen(false);
      setPreviewData(null);
    } finally {
      setPreviewPolling(false);
    }
  }, [pollPreviewUntilSettled]);

  const refreshSchedulePreview = useCallback(async () => {
    setPreviewApplyError(null);
    setPreviewPolling(true);
    try {
      const started = await postSchedulePreview();
      const settled = await pollPreviewUntilSettled(started.id);
      setPreviewData(settled);
    } catch (err) {
      emitToast(err instanceof Error ? err.message : "Couldn't refresh preview");
    } finally {
      setPreviewPolling(false);
    }
  }, [pollPreviewUntilSettled]);

  const closeSchedulePreview = useCallback(() => {
    if (previewApplying) return;
    setPreviewOpen(false);
    setPreviewApplyError(null);
  }, [previewApplying]);

  const applySchedulePreview = useCallback(async () => {
    if (!previewData || previewApplying) return;
    setPreviewApplying(true);
    setPreviewApplyError(null);
    try {
      const receipt = await postSchedulePreviewApply(previewData.id);
      invalidateCalendar();
      const parts: string[] = [];
      if (receipt.blocks_created > 0) {
        parts.push(`${receipt.blocks_created} block${receipt.blocks_created === 1 ? "" : "s"} created`);
      }
      if (receipt.overbooked_count > 0) {
        parts.push(`${receipt.overbooked_count} overbooked`);
      }
      emitToast(
        parts.length > 0 ? `Preview applied: ${parts.join(", ")}` : "Preview applied",
      );
      setPreviewOpen(false);
      setPreviewData(null);
    } catch (err) {
      if (err instanceof ApiError) {
        setPreviewApplyError({
          message: err.message,
          code: err.code,
          staleCategories: err.body.stale_categories,
        });
        if (err.code === "PREVIEW_STALE" || err.code === "PREVIEW_EXPIRED") {
          try {
            const refreshed = await fetchSchedulePreview(previewData.id);
            setPreviewData(refreshed);
          } catch {
            /* keep prior preview row */
          }
        }
        return;
      }
      setPreviewApplyError({
        message: err instanceof Error ? err.message : "Couldn't apply preview",
      });
    } finally {
      setPreviewApplying(false);
    }
  }, [previewApplying, previewData, invalidateCalendar]);

  return {
    previewOpen,
    previewPolling,
    previewData,
    previewApplying,
    previewApplyError,
    runSchedulePreview,
    refreshSchedulePreview,
    closeSchedulePreview,
    applySchedulePreview,
    setPreviewOpen,
  };
}
