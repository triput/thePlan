import { useRef, useState, type ChangeEvent, type FormEvent } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  applyOutline,
  proposeOutline,
  type OutlineAction,
  type OutlineProposeSummary,
} from "../api";
import { Modal } from "./Modal";
import { emitToast } from "./ToastHost";

const TEMPLATE_ID = "coursera_specialization";

type ReviewAction = OutlineAction & { clientId: string };

function withClientIds(actions: OutlineAction[]): ReviewAction[] {
  return actions.map((action) => ({
    ...action,
    clientId: crypto.randomUUID(),
  }));
}

function typeLabel(type: OutlineAction["type"]): string {
  switch (type) {
    case "create_epic":
      return "Epic";
    case "create_project":
      return "Project";
    case "create_section":
      return "Section";
    case "create_task":
      return "Task";
  }
}

function formatSummary(summary: OutlineProposeSummary): string {
  const parts = [
    `${summary.epic_count} epic${summary.epic_count === 1 ? "" : "s"}`,
    `${summary.project_count} project${summary.project_count === 1 ? "" : "s"}`,
    `${summary.section_count} section${summary.section_count === 1 ? "" : "s"}`,
    `${summary.task_count} task${summary.task_count === 1 ? "" : "s"}`,
  ];
  if (summary.optional_skipped > 0) {
    parts.push(`${summary.optional_skipped} optional skipped`);
  }
  return parts.join(" · ");
}

function ActionReviewRow({
  action,
  index,
  onChange,
  onRemove,
}: {
  action: ReviewAction;
  index: number;
  onChange: (index: number, next: ReviewAction) => void;
  onRemove: (index: number) => void;
}) {
  return (
    <li className="outline-action">
      <div className="outline-action-main">
        <span className={`outline-type-badge outline-type-${action.type}`}>{typeLabel(action.type)}</span>
        <input
          className="outline-action-title"
          value={action.title}
          aria-label={`Proposed ${typeLabel(action.type).toLowerCase()} ${index + 1} title`}
          onChange={(e) => onChange(index, { ...action, title: e.target.value })}
        />
        <button type="button" className="btn secondary small" onClick={() => onRemove(index)}>
          Remove
        </button>
      </div>
      {action.type === "create_task" && (action.label_names?.length ?? 0) > 0 ? (
        <div className="outline-action-meta muted small">Labels: {action.label_names!.join(", ")}</div>
      ) : null}
    </li>
  );
}

export function OutlineImportPanel() {
  const [open, setOpen] = useState(false);
  const [jsonText, setJsonText] = useState("");
  const [skipOptional, setSkipOptional] = useState(false);
  const [actions, setActions] = useState<ReviewAction[] | null>(null);
  const [summary, setSummary] = useState<OutlineProposeSummary | null>(null);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const queryClient = useQueryClient();

  const proposeMutation = useMutation({
    mutationFn: (outline: Record<string, unknown>) =>
      proposeOutline({
        template_id: TEMPLATE_ID,
        outline,
        skip_optional: skipOptional,
      }),
    onSuccess: (data) => {
      setActions(withClientIds(data.actions));
      setSummary(data.summary);
      setError(null);
      if (data.actions.length === 0) {
        emitToast("Outline produced no actions");
      }
    },
    onError: (err) => {
      setActions(null);
      setSummary(null);
      setError(err instanceof Error ? err.message : "Propose failed");
    },
  });

  const applyMutation = useMutation({
    mutationFn: (items: ReviewAction[]) =>
      applyOutline(items.map(({ clientId: _clientId, ...action }) => action)),
    onSuccess: (data) => {
      const okCount = data.results.filter((r) => r.ok).length;
      const failCount = data.results.length - okCount;
      emitToast(
        failCount === 0
          ? `Applied ${okCount} action${okCount === 1 ? "" : "s"}`
          : `Applied ${okCount}, ${failCount} failed`,
      );
      void queryClient.invalidateQueries({ queryKey: ["epics"] });
      void queryClient.invalidateQueries({ queryKey: ["projects"] });
      void queryClient.invalidateQueries({ queryKey: ["sections"] });
      void queryClient.invalidateQueries({ queryKey: ["tasks"] });
      void queryClient.invalidateQueries({ queryKey: ["labels"] });
      setJsonText("");
      setActions(null);
      setSummary(null);
      setOpen(false);
    },
    onError: (err) => {
      setError(err instanceof Error ? err.message : "Apply failed");
    },
  });

  const handlePropose = (e: FormEvent) => {
    e.preventDefault();
    const trimmed = jsonText.trim();
    if (!trimmed) return;
    let parsed: unknown;
    try {
      parsed = JSON.parse(trimmed) as unknown;
    } catch {
      setError("Invalid JSON");
      return;
    }
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
      setError("Outline must be a JSON object");
      return;
    }
    proposeMutation.mutate(parsed as Record<string, unknown>);
  };

  const handleFile = (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
      const text = typeof reader.result === "string" ? reader.result : "";
      setJsonText(text);
      setActions(null);
      setSummary(null);
      setError(null);
    };
    reader.onerror = () => {
      setError("Could not read file");
    };
    reader.readAsText(file);
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
    <div className="outline">
      <button
        type="button"
        className="btn secondary small outline-toggle"
        aria-expanded={open}
        onClick={() => setOpen(true)}
      >
        Outline
      </button>
      <Modal
        open={open}
        title="Outline import"
        onClose={() => setOpen(false)}
        className="outline-modal"
      >
        <p className="outline-help muted small">
          Paste or upload an operator-owned outline JSON file. No Coursera sync — local file only.
          Template: <code>{TEMPLATE_ID}</code>.
        </p>
        <form className="outline-form" onSubmit={handlePropose}>
          <textarea
            className="outline-input"
            rows={8}
            value={jsonText}
            onChange={(e) => {
              setJsonText(e.target.value);
              setError(null);
            }}
            placeholder='Paste outline JSON (certificate → courses → modules → tasks)'
            aria-label="Outline JSON"
          />
          <div className="outline-upload-row">
            <input
              ref={fileInputRef}
              type="file"
              accept=".json,application/json"
              className="outline-file-input"
              onChange={handleFile}
              aria-label="Upload outline JSON file"
            />
            <button
              type="button"
              className="btn secondary small"
              onClick={() => fileInputRef.current?.click()}
            >
              Upload .json
            </button>
            <label className="outline-skip">
              <input
                type="checkbox"
                checked={skipOptional}
                onChange={(e) => setSkipOptional(e.target.checked)}
              />
              Skip optional tasks
            </label>
          </div>
          <div className="outline-actions-bar">
            <button
              type="submit"
              className="btn primary small"
              disabled={proposeMutation.isPending || !jsonText.trim()}
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
                  setSummary(null);
                }}
              >
                Clear
              </button>
            )}
          </div>
        </form>
        {summary && actions && (
          <p className="outline-summary muted small">{formatSummary(summary)}</p>
        )}
        {actions && actions.length > 0 && (
          <ul className="outline-action-list">
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
