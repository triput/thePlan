import { useQuery } from "@tanstack/react-query";
import { fetchHeldMisses, type HeldDispositionOut } from "../api";
import { HELD_MISSES_QUERY_KEY } from "../heldMissesQuery";
import { formatScheduleReasonFact } from "../scheduleReasonFacts";
import type { CalendarSupportSnapshot } from "../supportDockContext";

export interface CalendarSupportIdleProps {
  snapshot: CalendarSupportSnapshot;
  onOpenPreview: () => void;
  previewReady: boolean;
  previewPolling: boolean;
  onSelectTask: (taskId: string) => void;
}

const HELD_LIST_CAP = 8;

function heldTitle(
  held: HeldDispositionOut,
  tasksById: ReadonlyMap<string, { title: string }>,
): string {
  const cached = tasksById.get(held.task_id);
  if (cached?.title) return cached.title;
  return `Task ${held.task_id.slice(0, 8)}…`;
}

function heldMissLine(held: HeldDispositionOut): string {
  if (held.miss_reason_code) {
    return formatScheduleReasonFact(held.miss_reason_code, held.miss_reason_params ?? {});
  }
  return "Held miss";
}

export function CalendarSupportIdle({
  snapshot,
  onOpenPreview,
  previewReady,
  previewPolling,
  onSelectTask,
}: CalendarSupportIdleProps) {
  const { unscheduledTotal, unscheduledSample, scheduleStaleHint, legend, tasksById } = snapshot;

  const heldQuery = useQuery({
    queryKey: HELD_MISSES_QUERY_KEY,
    queryFn: fetchHeldMisses,
    staleTime: 15_000,
  });

  const heldRows = (heldQuery.data ?? []).filter(
    (row) => row.resolution === "unresolved_held",
  );
  const heldSample = heldRows.slice(0, HELD_LIST_CAP);

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

      <section className="support-dock-section" aria-labelledby="cal-support-held-heading">
        <h3 id="cal-support-held-heading" className="support-dock-section-title">
          Held misses
        </h3>
        {heldQuery.isLoading && (
          <p className="muted small" role="status">
            Loading held…
          </p>
        )}
        {heldQuery.isError && (
          <p className="form-error" role="alert">
            Could not load held misses.{" "}
            <button
              type="button"
              className="btn link small"
              onClick={() => void heldQuery.refetch()}
            >
              Retry
            </button>
          </p>
        )}
        {heldQuery.isSuccess && heldRows.length === 0 && (
          <p className="muted small">No held misses.</p>
        )}
        {heldQuery.isSuccess && heldRows.length > 0 && (
          <>
            <p className="muted small">
              {heldRows.length} held miss{heldRows.length === 1 ? "" : "es"}
            </p>
            <ul className="calendar-support-unscheduled-list">
              {heldSample.map((row) => (
                <li key={row.id}>
                  <button
                    type="button"
                    className="btn link small calendar-support-task-link"
                    onClick={() => onSelectTask(row.task_id)}
                  >
                    {heldTitle(row, tasksById)}
                  </button>
                  <span className="muted small calendar-support-held-reason">
                    {" "}
                    — {heldMissLine(row)}
                  </span>
                </li>
              ))}
            </ul>
            {heldRows.length > heldSample.length && (
              <p className="muted small">
                {heldRows.length - heldSample.length} more — open a task for leave / skip / release.
              </p>
            )}
          </>
        )}
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
