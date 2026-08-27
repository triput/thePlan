import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { fetchTasks, restoreTask, type Task } from "../api";
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

  const loading = trashQuery.isLoading;
  const loadError = trashQuery.isError ? (trashQuery.error as Error).message : null;
  const empty = !loading && !loadError && items.length === 0;

  return (
    <div className="archived-view trash-view">
      <header className="pane-header">
        <h1>Trash</h1>
      </header>
      <p className="muted small trash-hint">
        Soft-deleted tasks stay here until restored. Retention / auto-purge not enabled yet.
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
    </div>
  );
}
