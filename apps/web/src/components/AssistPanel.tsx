import { useState, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ApiError,
  applyAssist,
  fetchAssistStatus,
  proposeAssist,
  type AssistCreateTaskAction,
  type TaskPriority,
} from "../api";
import { Modal } from "./Modal";
import { emitToast } from "./ToastHost";

const PRIORITIES: TaskPriority[] = ["p1", "p2", "p3", "p4"];

function ActionReviewRow({
  action,
  index,
  onChange,
  onRemove,
}: {
  action: AssistCreateTaskAction;
  index: number;
  onChange: (index: number, next: AssistCreateTaskAction) => void;
  onRemove: (index: number) => void;
}) {
  return (
    <li className="assist-action">
      <div className="assist-action-main">
        <input
          className="assist-action-title"
          value={action.title}
          aria-label={`Proposed task ${index + 1} title`}
          onChange={(e) => onChange(index, { ...action, title: e.target.value })}
        />
        <select
          className="assist-action-priority"
          value={action.priority ?? "p4"}
          aria-label={`Proposed task ${index + 1} priority`}
          onChange={(e) =>
            onChange(index, { ...action, priority: e.target.value as TaskPriority })
          }
        >
          {PRIORITIES.map((p) => (
            <option key={p} value={p}>
              {p.toUpperCase()}
            </option>
          ))}
        </select>
        <button type="button" className="btn secondary small" onClick={() => onRemove(index)}>
          Remove
        </button>
      </div>
      <div className="assist-action-meta muted small">
        {action.project_name ? <span>Project: {action.project_name}</span> : <span>Inbox</span>}
        {action.section_name ? <span> · Section: {action.section_name}</span> : null}
        {action.label_names && action.label_names.length > 0 ? (
          <span> · Labels: {action.label_names.join(", ")}</span>
        ) : null}
        {action.due_at ? <span> · Due: {new Date(action.due_at).toLocaleString()}</span> : null}
      </div>
    </li>
  );
}

export function AssistPanel() {
  const [open, setOpen] = useState(false);
  const [text, setText] = useState("");
  const [actions, setActions] = useState<AssistCreateTaskAction[] | null>(null);
  const [model, setModel] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const queryClient = useQueryClient();

  const statusQuery = useQuery({
    queryKey: ["assist-status"],
    queryFn: fetchAssistStatus,
    enabled: open,
    staleTime: 30_000,
    retry: false,
  });

  const proposeMutation = useMutation({
    mutationFn: proposeAssist,
    onSuccess: (data) => {
      setActions(data.actions);
      setModel(data.model);
      setError(null);
      if (data.actions.length === 0) {
        emitToast("Assist found nothing to create");
      }
    },
    onError: (err) => {
      setActions(null);
      setModel(null);
      if (err instanceof ApiError && err.code === "ASSIST_UNAVAILABLE") {
        setError("Assist unavailable — is Ollama running?");
      } else {
        setError(err instanceof Error ? err.message : "Propose failed");
      }
    },
  });

  const applyMutation = useMutation({
    mutationFn: applyAssist,
    onSuccess: (data) => {
      const okCount = data.results.filter((r) => r.ok).length;
      const failCount = data.results.length - okCount;
      emitToast(
        failCount === 0
          ? `Created ${okCount} task${okCount === 1 ? "" : "s"}`
          : `Created ${okCount}, ${failCount} failed`,
      );
      void queryClient.invalidateQueries({ queryKey: ["tasks"] });
      void queryClient.invalidateQueries({ queryKey: ["labels"] });
      setText("");
      setActions(null);
      setModel(null);
      setOpen(false);
    },
    onError: (err) => {
      setError(err instanceof Error ? err.message : "Apply failed");
    },
  });

  const handlePropose = (e: FormEvent) => {
    e.preventDefault();
    const trimmed = text.trim();
    if (!trimmed) return;
    proposeMutation.mutate(trimmed);
  };

  const handleApprove = () => {
    if (!actions || actions.length === 0) return;
    const cleaned = actions
      .map((a) => ({ ...a, title: a.title.trim() }))
      .filter((a) => a.title.length > 0);
    if (cleaned.length === 0) {
      setError("Nothing left to approve");
      return;
    }
    applyMutation.mutate(cleaned);
  };

  return (
    <div className="assist">
      <button
        type="button"
        className="btn secondary small assist-toggle"
        aria-expanded={open}
        onClick={() => setOpen(true)}
      >
        Assist
      </button>
      <Modal open={open} title="Assist" onClose={() => setOpen(false)} className="assist-modal">
        <p className="assist-help muted small">
          Describe what you need. Review proposed tasks, then approve. Ollama down never blocks
          normal CRUD.
        </p>
        {statusQuery.data && (
          <p className="assist-status muted small">
            Model: <code>{statusQuery.data.model}</code>
            {" · "}
            {statusQuery.data.reachable ? "reachable" : "unreachable"}
            {statusQuery.data.detail ? ` (${statusQuery.data.detail})` : null}
          </p>
        )}
        <form className="assist-form" onSubmit={handlePropose}>
          <textarea
            className="assist-input"
            rows={4}
            value={text}
            onChange={(e) => {
              setText(e.target.value);
              setError(null);
            }}
            placeholder="e.g. Add buy oat milk as p3 with label errands, and schedule dog walk tomorrow"
            aria-label="Assist request"
          />
          <div className="assist-actions-bar">
            <button
              type="submit"
              className="btn primary small"
              disabled={proposeMutation.isPending || !text.trim()}
            >
              {proposeMutation.isPending ? "Proposing…" : "Propose"}
            </button>
            {actions && actions.length > 0 && (
              <button
                type="button"
                className="btn primary small"
                disabled={applyMutation.isPending}
                onClick={handleApprove}
              >
                {applyMutation.isPending ? "Applying…" : "Approve"}
              </button>
            )}
            {actions && (
              <button
                type="button"
                className="btn secondary small"
                onClick={() => {
                  setActions(null);
                  setModel(null);
                }}
              >
                Clear
              </button>
            )}
          </div>
        </form>
        {model && actions && (
          <p className="muted small">
            Proposal from <code>{model}</code> — edit or remove before approve.
          </p>
        )}
        {actions && actions.length > 0 && (
          <ul className="assist-action-list">
            {actions.map((action, index) => (
              <ActionReviewRow
                key={`${action.title}-${index}`}
                action={action}
                index={index}
                onChange={(i, next) =>
                  setActions((prev) => (prev ? prev.map((a, j) => (j === i ? next : a)) : prev))
                }
                onRemove={(i) =>
                  setActions((prev) => (prev ? prev.filter((_, j) => j !== i) : prev))
                }
              />
            ))}
          </ul>
        )}
        {error && <p className="form-error">{error}</p>}
      </Modal>
    </div>
  );
}
