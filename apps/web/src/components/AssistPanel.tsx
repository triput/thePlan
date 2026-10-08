import { useState, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ApiError,
  applyAssist,
  fetchAssistStatus,
  proposeAssist,
  type AssistAction,
  type AssistCreateProjectAction,
  type AssistCreateTaskAction,
  type TaskPriority,
} from "../api";
import { Modal } from "./Modal";
import { emitToast } from "./ToastHost";

const PRIORITIES: TaskPriority[] = ["p1", "p2", "p3", "p4"];

type ReviewAction = AssistAction & { clientId: string };

function withClientIds(actions: AssistAction[]): ReviewAction[] {
  return actions.map((action) => ({
    ...action,
    clientId: crypto.randomUUID(),
  }));
}

function toDatetimeLocal(iso: string | null | undefined): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function fromDatetimeLocal(value: string): string | null {
  if (!value) return null;
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return null;
  return d.toISOString();
}

function actionTypeLabel(type: AssistAction["type"]): string {
  return type === "create_project" ? "Project" : "Task";
}

function TaskReviewRow({
  action,
  index,
  onChange,
  onRemove,
}: {
  action: ReviewAction & AssistCreateTaskAction;
  index: number;
  onChange: (index: number, next: ReviewAction) => void;
  onRemove: (index: number) => void;
}) {
  const durationValue =
    action.estimated_duration_minutes != null ? String(action.estimated_duration_minutes) : "";

  return (
    <li className="assist-action">
      <div className="assist-action-main">
        <span className="assist-type-badge">Task</span>
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
      <div className="assist-action-fields">
        <label className="field">
          <span>Due</span>
          <input
            type="datetime-local"
            className="field-datetime"
            value={toDatetimeLocal(action.due_at)}
            aria-label={`Proposed task ${index + 1} due`}
            onChange={(e) =>
              onChange(index, { ...action, due_at: fromDatetimeLocal(e.target.value) })
            }
          />
        </label>
        <label className="field">
          <span>Duration (minutes)</span>
          <input
            type="number"
            className="field-number"
            min={1}
            max={24 * 60}
            step={5}
            value={durationValue}
            placeholder="settings default"
            aria-label={`Proposed task ${index + 1} duration`}
            onChange={(e) => {
              const raw = e.target.value.trim();
              if (!raw) {
                onChange(index, { ...action, estimated_duration_minutes: null });
                return;
              }
              const n = Number(raw);
              onChange(index, {
                ...action,
                estimated_duration_minutes: Number.isFinite(n) && n >= 1 ? Math.floor(n) : null,
              });
            }}
          />
        </label>
      </div>
      <div className="assist-action-meta muted small">
        {action.project_name ? <span>Project: {action.project_name}</span> : <span>Inbox</span>}
        {action.section_name ? <span> · Section: {action.section_name}</span> : null}
        {action.label_names && action.label_names.length > 0 ? (
          <span> · Labels: {action.label_names.join(", ")}</span>
        ) : null}
      </div>
    </li>
  );
}

function ProjectReviewRow({
  action,
  index,
  onChange,
  onRemove,
}: {
  action: ReviewAction & AssistCreateProjectAction;
  index: number;
  onChange: (index: number, next: ReviewAction) => void;
  onRemove: (index: number) => void;
}) {
  return (
    <li className="assist-action">
      <div className="assist-action-main">
        <span className="assist-type-badge">Project</span>
        <input
          className="assist-action-title"
          value={action.title}
          aria-label={`Proposed project ${index + 1} title`}
          onChange={(e) => onChange(index, { ...action, title: e.target.value })}
        />
        <button type="button" className="btn secondary small" onClick={() => onRemove(index)}>
          Remove
        </button>
      </div>
      <div className="assist-action-fields">
        <label className="field">
          <span>Epic (name)</span>
          <input
            type="text"
            className="field-text"
            value={action.epic_name ?? ""}
            placeholder="optional — existing epic"
            aria-label={`Proposed project ${index + 1} epic`}
            onChange={(e) => {
              const raw = e.target.value.trim();
              onChange(index, {
                ...action,
                epic_name: raw || null,
                epic_id: raw ? null : action.epic_id,
              });
            }}
          />
        </label>
        <label className="field">
          <span>Color</span>
          <input
            type="text"
            className="field-text"
            value={action.color_hex ?? ""}
            placeholder="#0A8558 default"
            aria-label={`Proposed project ${index + 1} color`}
            onChange={(e) => {
              const raw = e.target.value.trim();
              onChange(index, { ...action, color_hex: raw || null });
            }}
          />
        </label>
      </div>
      {action.description ? (
        <div className="assist-action-meta muted small">Notes: {action.description}</div>
      ) : null}
    </li>
  );
}

function ActionReviewRow(props: {
  action: ReviewAction;
  index: number;
  onChange: (index: number, next: ReviewAction) => void;
  onRemove: (index: number) => void;
}) {
  if (props.action.type === "create_project") {
    return <ProjectReviewRow {...props} action={props.action} />;
  }
  return <TaskReviewRow {...props} action={props.action} />;
}

function summarizeApplyResults(results: { ok: boolean; action_type: string }[]): string {
  const tasks = results.filter((r) => r.ok && r.action_type === "create_task").length;
  const projects = results.filter((r) => r.ok && r.action_type === "create_project").length;
  const failCount = results.filter((r) => !r.ok).length;
  const parts: string[] = [];
  if (tasks > 0) parts.push(`${tasks} task${tasks === 1 ? "" : "s"}`);
  if (projects > 0) parts.push(`${projects} project${projects === 1 ? "" : "s"}`);
  const created = parts.length ? `Created ${parts.join(" and ")}` : "Nothing created";
  if (failCount === 0) return created;
  return `${created}, ${failCount} failed`;
}

export function AssistPanel() {
  const [open, setOpen] = useState(false);
  const [text, setText] = useState("");
  const [actions, setActions] = useState<ReviewAction[] | null>(null);
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
      setActions(withClientIds(data.actions));
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
    mutationFn: (items: ReviewAction[]) =>
      applyAssist(
        items.map(({ clientId: _clientId, ...action }) => action),
      ),
    onSuccess: (data) => {
      emitToast(summarizeApplyResults(data.results));
      void queryClient.invalidateQueries({ queryKey: ["tasks"] });
      void queryClient.invalidateQueries({ queryKey: ["labels"] });
      void queryClient.invalidateQueries({ queryKey: ["projects"] });
      void queryClient.invalidateQueries({ queryKey: ["epics"] });
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
          Describe what you need. Review proposed tasks and projects, then approve. Ollama down never
          blocks normal CRUD. “Schedule at …” on tasks means due time, not a calendar block.
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
            placeholder="e.g. Create a project Garden Renovation under epic Home, and add buy oat milk as p3"
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
            Proposal from <code>{model}</code> — edit or remove rows before approve (
            {actions.map((a) => actionTypeLabel(a.type)).join(", ")}).
          </p>
        )}
        {actions && actions.length > 0 && (
          <ul className="assist-action-list">
            {actions.map((action, index) => (
              <ActionReviewRow
                key={action.clientId}
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
