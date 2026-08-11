import { useEffect, useRef } from "react";
import { ackReminder, fetchDueReminders, type ReminderDue } from "../api";
import { emitToast } from "./ToastHost";

const POLL_MS = 30_000;

function showBrowserNotification(reminder: ReminderDue) {
  if (reminder.channel !== "browser") return;
  if (typeof Notification === "undefined") return;
  if (Notification.permission !== "granted") return;
  try {
    new Notification("thePlan reminder", {
      body: reminder.task_title,
      tag: `reminder-${reminder.id}`,
    });
  } catch {
    // Ignore Notification constructor failures (e.g. insecure context).
  }
}

/** Polls due reminders while authenticated; toasts + optional browser Notification, then ack. */
export function ReminderPoller() {
  const inFlight = useRef(new Set<string>());

  useEffect(() => {
    let cancelled = false;

    const poll = async () => {
      if (document.visibilityState === "hidden") return;
      try {
        const due = await fetchDueReminders();
        if (cancelled) return;
        for (const reminder of due) {
          if (inFlight.current.has(reminder.id)) continue;
          inFlight.current.add(reminder.id);
          emitToast(`Reminder: ${reminder.task_title}`);
          showBrowserNotification(reminder);
          try {
            await ackReminder(reminder.id);
          } catch {
            inFlight.current.delete(reminder.id);
          }
        }
      } catch {
        // Transient network / auth blips — next poll retries.
      }
    };

    void poll();
    const timer = window.setInterval(() => void poll(), POLL_MS);

    const onVisible = () => {
      if (document.visibilityState === "visible") void poll();
    };
    const onFocus = () => void poll();
    document.addEventListener("visibilitychange", onVisible);
    window.addEventListener("focus", onFocus);

    return () => {
      cancelled = true;
      window.clearInterval(timer);
      document.removeEventListener("visibilitychange", onVisible);
      window.removeEventListener("focus", onFocus);
    };
  }, []);

  return null;
}
