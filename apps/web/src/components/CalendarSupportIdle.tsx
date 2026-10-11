import type { CalendarSupportSnapshot } from "../supportDockContext";

export interface CalendarSupportIdleProps {
  snapshot: CalendarSupportSnapshot;
  onOpenPreview: () => void;
  previewReady: boolean;
  previewPolling: boolean;
  onSelectTask: (taskId: string) => void;
}

export function CalendarSupportIdle({
  snapshot,
  onOpenPreview,
  previewReady,
  previewPolling,
  onSelectTask,
}: CalendarSupportIdleProps) {
  const { unscheduledTotal, unscheduledSample, scheduleStaleHint, legend } = snapshot;

  return (
    <div className="calendar-support-idle">
      <section className="support-dock-section" aria-labelledby="cal-support-schedule-heading">
        <h3 id="cal-support-schedule-heading" className="support-dock-section-title">
          Schedule
        </h3>
        {scheduleStaleHint ? (
          <p className="support-dock-callout warn small" role="status">
            {scheduleStaleHint.title}
          </p>
        ) : (
          <p className="muted small">Use Preview changes or Update Schedule from the calendar toolbar.</p>
        )}
        <button
          type="button"
          className="btn secondary small"
          onClick={() => void onOpenPreview()}
          disabled={previewPolling}
        >
          {previewPolling ? "Calculating…" : previewReady ? "Review open preview" : "Preview changes"}
        </button>
      </section>

      <section className="support-dock-section" aria-labelledby="cal-support-unscheduled-heading">
        <h3 id="cal-support-unscheduled-heading" className="support-dock-section-title">
          Unscheduled in horizon
        </h3>
        {unscheduledTotal === 0 ? (
          <p className="muted small">Every open task in view has at least one scheduled block.</p>
        ) : (
          <>
            <p className="muted small">
              {unscheduledTotal} open task{unscheduledTotal === 1 ? "" : "s"} without a block in the
              current range.
            </p>
            <ul className="calendar-support-unscheduled-list">
              {unscheduledSample.map((row) => (
                <li key={row.id}>
                  <button
                    type="button"
                    className="btn link small calendar-support-task-link"
                    onClick={() => onSelectTask(row.id)}
                  >
                    {row.title}
                  </button>
                </li>
              ))}
            </ul>
            {unscheduledTotal > unscheduledSample.length && (
              <p className="muted small">
                {unscheduledTotal - unscheduledSample.length} more — drag from the task list or use
                Preview changes.
              </p>
            )}
          </>
        )}
      </section>

      <section className="support-dock-section" aria-labelledby="cal-support-legend-heading">
        <h3 id="cal-support-legend-heading" className="support-dock-section-title">
          Map & blocks
        </h3>
        <p className="muted small">
          {legend.overlayMapName ? (
            <>
              <span className="cal-overlay-legend-map">{legend.overlayMapName}</span> overlay is visual
              only (does not replan).
            </>
          ) : (
            <>Time Map overlay is <strong>Neutral</strong> — no band tint on the grid.</>
          )}
        </p>
        <ul className="cal-legend-list" aria-label="Calendar legend">
          <li className="cal-legend-row">
            <span className="cal-legend-swatch cal-legend-swatch--preferred" aria-hidden />
            <span>
              <strong>Preferred</strong> (green band) — best placement window
            </span>
          </li>
          <li className="cal-legend-row">
            <span className="cal-legend-swatch cal-legend-swatch--acceptable" aria-hidden />
            <span>
              <strong>Acceptable</strong> (yellow band) — allowed with lower preference
            </span>
          </li>
          <li className="cal-legend-row">
            <span className="cal-legend-swatch cal-legend-swatch--excluded" aria-hidden />
            <span>
              <strong>Excluded</strong> (red band) — forbidden; overrides other tiers when stacked
            </span>
          </li>
          {!legend.overlayMapName && (
            <li className="cal-legend-row">
              <span className="cal-legend-swatch cal-legend-swatch--neutral" aria-hidden />
              <span>
                <strong>Neutral</strong> — no map bands drawn (toolbar: Time Map → Neutral)
              </span>
            </li>
          )}
          <li className="cal-legend-row">
            <span className="cal-legend-swatch cal-legend-swatch--external" aria-hidden />
            <span>
              <strong>External busy</strong>
              {legend.busyInRangeCount > 0
                ? ` — ${legend.busyInRangeCount} in view`
                : " — imported calendar holds"}
            </span>
          </li>
          <li className="cal-legend-row">
            <span className="cal-legend-swatch cal-legend-swatch--pinned" aria-hidden />
            <span>
              <strong>Pinned</strong>
              {legend.pinnedBlockCount > 0
                ? ` — ${legend.pinnedBlockCount} block${legend.pinnedBlockCount === 1 ? "" : "s"} fixed during replan`
                : " — replan leaves pinned times in place"}
            </span>
          </li>
          <li className="cal-legend-row">
            <span className="cal-legend-swatch cal-legend-swatch--movable" aria-hidden />
            <span>
              <strong>Movable</strong> — unpinned blocks (project color) move on Update Schedule
            </span>
          </li>
        </ul>
      </section>
    </div>
  );
}
