import { createContext, useContext, useMemo, useState, type ReactNode } from "react";
import type { Task } from "./api";
import { useSchedulePreviewActions } from "./hooks/useSchedulePreviewActions";

export interface CalendarSupportSnapshot {
  tasksById: ReadonlyMap<string, Task>;
  unscheduledTotal: number;
  unscheduledSample: ReadonlyArray<{ id: string; title: string }>;
  scheduleStaleHint: { taskCount: number; title: string } | null;
  legend: {
    overlayMapName: string | null;
    pinnedBlockCount: number;
    busyInRangeCount: number;
  };
}

interface SupportDockContextValue {
  calendarSupport: CalendarSupportSnapshot | null;
  setCalendarSupport: (snapshot: CalendarSupportSnapshot | null) => void;
  previewOpen: boolean;
  previewPolling: boolean;
  previewData: ReturnType<typeof useSchedulePreviewActions>["previewData"];
  previewApplying: boolean;
  previewApplyError: ReturnType<typeof useSchedulePreviewActions>["previewApplyError"];
  runSchedulePreview: () => Promise<void>;
  refreshSchedulePreview: () => Promise<void>;
  closeSchedulePreview: () => void;
  applySchedulePreview: () => Promise<void>;
}

const SupportDockContext = createContext<SupportDockContextValue | null>(null);

export function SupportDockProvider({ children }: { children: ReactNode }) {
  const preview = useSchedulePreviewActions();
  const [calendarSupport, setCalendarSupport] = useState<CalendarSupportSnapshot | null>(null);

  const value = useMemo(
    (): SupportDockContextValue => ({
      calendarSupport,
      setCalendarSupport,
      previewOpen: preview.previewOpen,
      previewPolling: preview.previewPolling,
      previewData: preview.previewData,
      previewApplying: preview.previewApplying,
      previewApplyError: preview.previewApplyError,
      runSchedulePreview: preview.runSchedulePreview,
      refreshSchedulePreview: preview.refreshSchedulePreview,
      closeSchedulePreview: preview.closeSchedulePreview,
      applySchedulePreview: preview.applySchedulePreview,
    }),
    [calendarSupport, preview],
  );

  return <SupportDockContext.Provider value={value}>{children}</SupportDockContext.Provider>;
}

export function useSupportDock(): SupportDockContextValue {
  const ctx = useContext(SupportDockContext);
  if (!ctx) {
    throw new Error("useSupportDock must be used within SupportDockProvider");
  }
  return ctx;
}
