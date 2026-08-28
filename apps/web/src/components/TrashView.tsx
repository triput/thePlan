import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { emptyTrash, fetchTasks, restoreTask, type Task } from "../api";
import { ConfirmDialog } from "./ConfirmDialog";
import { Modal } from "./Modal";
import { emitToast } from "./ToastHost";

function formatDeletedAt(iso: string | null | undefined): string {
  if (!iso) return "Unknown time";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "Unknown time";
  return d.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

export function TrashView() {
  const queryClient = useQueryClient();
  const [confirmEmpty, setConfirmEmpty] = useState(false);
  const [confirmPurgeOlder, setConfirmPurgeOlder] = useState(false);
  const [purgeDays, setPurgeDays] = useState(30);

  const trashQuery = useQuery({
    queryKey: ["tasks", "trash"],
    queryFn: () => fetchTasks({ trashed: true, limit: 200 }),
  });

  const items = trashQuery.data?.items ?? [];

  const restoreMutation = useMutation({
    mutationFn: (taskId: string) => restoreTask(taskId),
    onSuccess: (task: Task) => {
      queryClient.invalidateQueries({ queryKey: ["tasks"] });
      emitToast(`Restored “${task.title}”`);
    },
  });

  const emptyMutation = useMutation({
    mutationFn: () => emptyTrash(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["tasks"] });
      setConfirmEmpty(false);
      emitToast("Trash emptied");
    },
  });

  const purgeOlderMutation = useMutation({
    mutationFn: (days: number) => emptyTrash({ older_than_days: days }),
    onSuccess: (_data, days) => {
      queryClient.invalidateQueries({ queryKey: ["tasks"] });
      setConfirmPurgeOlder(false);
      emitToast(`Purged trash older than ${days} days`);
    },
  });

  const loading = trashQuery.isLoading;
  const loadError = trashQuery.isError ? (trashQuery.error as Error).message : null;
  const empty = !loading && !loadError && items.length === 0;
  const purgeBusy = emptyMutation.isPending || purgeOlderMutation.isPending;
  const purgeDaysValid = Number.isFinite(purgeDays) && purgeDays >= 1;

  return (
    <div className="archived-view trash-view">
      <header className="pane-header">
        <h1>Trash</h1>
        {items.length > 0 && (
          <div className="pane-header-actions">
            <button
              type="button"
              className="btn secondary small"
              onClick={() => {
                setPurgeDays(30);
                setConfirmPurgeOlder(true);
              }}
              disabled={purgeBusy}
            >
              Purge older than 30 days…
            </button>
            <button
              type="button"
              className="btn danger small"
              onClick={() => setConfirmEmpty(true)}
              disabled={purgeBusy}
            >
              Empty trash
            </button>
          </div>
        )}
      </header>
      <p className="muted small trash-hint">
        Soft-deleted tasks stay here until you restore, purge older items, or empty trash. No
        background auto-purge — clean up manually.
      </p>

      {loading && <p className="muted">Loading trash…</p>}
      {loadError && <p className="form-error">{loadError}</p>}
      {empty && (
        <p className="empty-state">Trash is empty. Deleted tasks will show up here.</p>
      )}

      {items.length > 0 && (
        <ul className="labels-list" aria-label="Trashed tasks">
          {items.map((task) => (
            <li key={task.id} className="archived-row">
              <div className="archived-row-text">
                <span className="archived-row-title">{task.title}</span>
                <span className="archived-row-meta muted">
                  Deleted {formatDeletedAt(task.deleted_at)}
                  {task.nesting_level > 0 ? ` · nesting ${task.nesting_level}` : ""}
                </span>
                {restoreMutation.isError && restoreMutation.variables === task.id && (
                  <span className="form-error">{(restoreMutation.error as Error).message}</span>
                )}
              </div>
              <button
                type="button"
                className="btn secondary small"
                onClick={() => restoreMutation.mutate(task.id)}
                disabled={restoreMutation.isPending && restoreMutation.variables === task.id}
                aria-label={`Restore task ${task.title}`}
              >
                {restoreMutation.isPending && restoreMutation.variables === task.id
                  ? "Restoring…"
                  : "Restore"}
              </button>
            </li>
          ))}
        </ul>
      )}

      <ConfirmDialog
        open={confirmEmpty}
        title="Empty trash?"
        message={`Permanently delete all ${items.length} item${items.length === 1 ? "" : "s"} in trash? This cannot be undone.`}
        confirmLabel="Empty trash"
        destructive
        pending={emptyMutation.isPending}
        onClose={() => setConfirmEmpty(false)}
        onConfirm={() => emptyMutation.mutate()}
      />
      {emptyMutation.isError && confirmEmpty && (
        <p className="form-error">{(emptyMutation.error as Error).message}</p>
      )}

      <Modal
        open={confirmPurgeOlder}
        title="Purge older trash?"
        onClose={() => {
          if (!purgeOlderMutation.isPending) setConfirmPurgeOlder(false);
        }}
      >
        <div className="entity-form">
          <p className="dialog-text">
            Permanently delete trashed tasks older than the number of days below. Newer trash items
            stay. This cannot be undone.
          </p>
          <label className="field">
            <span>Older than (days)</span>
            <input
              type="number"
              className="field-number"
              min={1}
              step={1}
              value={purgeDays}
              disabled={purgeOlderMutation.isPending}
              onChange={(e) => setPurgeDays(Number(e.target.value))}
              aria-label="Purge items older than this many days"
            />
          </label>
          <div className="form-actions">
            <button
              type="button"
              className="btn secondary"
              onClick={() => setConfirmPurgeOlder(false)}
              disabled={purgeOlderMutation.isPending}
            >
              Cancel
            </button>
            <button
              type="button"
              className="btn danger"
              disabled={purgeOlderMutation.isPending || !purgeDaysValid}
              onClick={() => purgeOlderMutation.mutate(Math.floor(purgeDays))}
            >
              {purgeOlderMutation.isPending
                ? "Working…"
                : `Purge older than ${purgeDaysValid ? Math.floor(purgeDays) : "…"} days`}
            </button>
          </div>
          {purgeOlderMutation.isError && (
            <p className="form-error">{(purgeOlderMutation.error as Error).message}</p>
          )}
        </div>
      </Modal>
    </div>
  );
}
