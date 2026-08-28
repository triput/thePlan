/**
 * Settings — calendar day-range display toggle (local preference).
 */
import { useEffect, useState } from "react";
import { loadShow24h, saveShow24h } from "../../calendarUtils";

const CALENDAR_HOURS_EVENT = "theplan:calendar-hours";

export function CalendarDisplaySection({ open }: { open: boolean }) {
  const [show24h, setShow24h] = useState(() => loadShow24h());

  useEffect(() => {
    if (!open) return;
    setShow24h(loadShow24h());
  }, [open]);

  const handleShow24hChange = (checked: boolean) => {
    setShow24h(checked);
    saveShow24h(checked);
    window.dispatchEvent(new CustomEvent(CALENDAR_HOURS_EVENT, { detail: checked }));
  };

  return (
    <section className="settings-section">
      <h3 className="settings-section-title">Calendar display</h3>
      <label className="calendar-display-check">
        <input
          type="checkbox"
          checked={show24h}
          onChange={(e) => handleShow24hChange(e.target.checked)}
        />
        Show 24 hours
      </label>
      <p className="settings-help muted small">
        When off, the calendar shows 6 AM–10 PM. Toggle also available in the calendar header.
      </p>
    </section>
  );
}
