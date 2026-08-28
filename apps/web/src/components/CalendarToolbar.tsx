import type { FocusWindow } from "../api";
import type { CalendarMode } from "../calendarUtils";

export interface CalendarToolbarProps {
  headerTitle: string;
  conflictCount: number;
  mode: CalendarMode;
  isNarrow: boolean;
  show24h: boolean;
  replanPolling: boolean;
  clearUnpinnedPending: boolean;
  focusWindows: ReadonlyArray<Pick<FocusWindow, "id" | "name">>;
  effectiveOverlayMapId: string;
  onPrev: () => void;
  onNext: () => void;
  onToday: () => void;
  onClearUnpinned: () => void;
  onUpdateSchedule: () => void;
  onToggleShow24h: () => void;
  onSetTimeMapOverlay: (mapId: string) => void;
  onSetMode: (mode: CalendarMode) => void;
}

export function CalendarToolbar({
  headerTitle,
  conflictCount,
  mode,
  isNarrow,
  show24h,
  replanPolling,
  clearUnpinnedPending,
  focusWindows,
  effectiveOverlayMapId,
  onPrev,
  onNext,
  onToday,
  onClearUnpinned,
  onUpdateSchedule,
  onToggleShow24h,
  onSetTimeMapOverlay,
  onSetMode,
}: CalendarToolbarProps) {
  return (
    <header className="cal-header">
      <div className="cal-nav">
        <button type="button" className="btn ghost small" onClick={onPrev} aria-label="Previous">
          ‹
        </button>
        <button type="button" className="btn secondary small" onClick={onToday}>
          Today
        </button>
        <button type="button" className="btn ghost small" onClick={onNext} aria-label="Next">
          ›
        </button>
      </div>
      <h1 className="cal-title">{headerTitle}</h1>
      {conflictCount > 0 && (
        <p className="cal-conflict-banner muted small" role="status">
          {conflictCount} schedule conflict{conflictCount === 1 ? "" : "s"}
        </p>
      )}
      <div className="cal-mode-toggle">
        <button
          type="button"
          className="btn small ghost cal-clear-btn"
          onClick={onClearUnpinned}
          disabled={clearUnpinnedPending || replanPolling}
          title="Remove unpinned blocks in the visible day or week"
        >
          {clearUnpinnedPending ? "Clearing…" : "Clear unpinned"}
        </button>
        <button
          type="button"
          className="btn small primary cal-replan-btn"
          onClick={onUpdateSchedule}
          disabled={replanPolling}
        >
          {replanPolling ? "Updating…" : "Update Schedule"}
        </button>
        <button
          type="button"
          className="btn small cal-hours-toggle ghost"
          onClick={onToggleShow24h}
          aria-pressed={show24h}
          title={
            show24h
              ? "Showing 24 hours — click for 6 AM–10 PM"
              : "Showing 6 AM–10 PM — click for 24 hours"
          }
        >
          {show24h ? "24h" : "6A–10P"}
        </button>
        {mode === "week" && (
          <label className="cal-time-map-overlay">
            <span className="cal-time-map-overlay-label">Time Map</span>
            <select
              className="cal-time-map-overlay-select"
              value={effectiveOverlayMapId}
              onChange={(e) => onSetTimeMapOverlay(e.target.value)}
              aria-label="Time Map overlay — visual only; does not change scheduling"
              title="Visual prompt only — does not change scheduling"
            >
              <option value="">Neutral</option>
              {focusWindows.map((window) => (
                <option key={window.id} value={window.id}>
                  {window.name}
                </option>
              ))}
            </select>
          </label>
        )}
        <button
          type="button"
          className={`btn small${mode === "day" ? " primary" : " ghost"}`}
          onClick={() => onSetMode("day")}
        >
          Day
        </button>
        <button
          type="button"
          className={`btn small cal-week-btn${mode === "week" ? " primary" : " ghost"}`}
          onClick={() => onSetMode("week")}
          hidden={isNarrow}
        >
          Week
        </button>
      </div>
    </header>
  );
}
