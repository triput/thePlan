// ==============================================================================
//  File: apps/web/src/components/OutlineImportPanel.tsx
//  Description: Free-form outline import via /api/v1/outlines (paste, upload, propose, apply).
//  Component: F5 Outline
//  Version: 1.0
//  Created: 2026-10-09
//  Last Update: 2026-10-10
// ==============================================================================

import { useRef, useState, type ChangeEvent, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  applyOutline,
  fetchEpics,
  fetchProjects,
  fetchSections,
  proposeOutline,
  type OutlineAction,
  type OutlineAttachKind,
  type OutlineAttachUnder,
  type OutlineProposeSummary,
  type OutlineTemplateId,
} from "../api";
import { Modal } from "./Modal";
import { emitToast } from "./ToastHost";

const TEMPLATE_OPTIONS: { id: OutlineTemplateId; label: string }[] = [
  { id: "coursera_specialization", label: "Coursera specialization" },
  { id: "hierarchy_v1", label: "Generic hierarchy (v1)" },
];

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

export function OutlineImportPanel({
  onApplied,
  embedded = false,
  active = true,
  shellOpen,
  onRequestClose,
}: {
  onApplied?: (epicId: string | null) => void;
  embedded?: boolean;
  /** Visible tab (draft survives when false). */
  active?: boolean;
  /** Keep attach queries warm while Import modal is open. */
  shellOpen?: boolean;
  /** When embedded, parent Import shell closes after a successful apply. */
  onRequestClose?: () => void;
}) {
  const [internalOpen, setInternalOpen] = useState(false);
  const panelOpen = embedded ? (shellOpen ?? active) : internalOpen;

  const closeShell = () => {
    if (embedded) onRequestClose?.();
    else setInternalOpen(false);
  };
  const [jsonText, setJsonText] = useState("");
  const [templateId, setTemplateId] = useState<OutlineTemplateId>("coursera_specialization");
  const [skipOptional, setSkipOptional] = useState(false);
  const [attachKind, setAttachKind] = useState<OutlineAttachKind | "new">("new");
  const [attachEpicId, setAttachEpicId] = useState("");
  const [attachProjectId, setAttachProjectId] = useState("");
  const [attachSectionId, setAttachSectionId] = useState("");
  const [actions, setActions] = useState<ReviewAction[] | null>(null);
  const [summary, setSummary] = useState<OutlineProposeSummary | null>(null);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const queryClient = useQueryClient();

  const epicsQuery = useQuery({
    queryKey: ["epics", "outline-import"],
    queryFn: () => fetchEpics({ archived: false, limit: 200 }),
    enabled: panelOpen && attachKind !== "new",
  });

  const projectsQuery = useQuery({
    queryKey: ["projects", "outline-import", attachEpicId],
    queryFn: () =>
      fetchProjects({
        archived: false,
        limit: 200,
        epic_id: attachKind === "project" || attachKind === "section" ? attachEpicId || undefined : undefined,
      }),
    enabled: panelOpen && (attachKind === "project" || attachKind === "section"),
  });

  const sectionsQuery = useQuery({
    queryKey: ["sections", "outline-import", attachProjectId],
    queryFn: () => fetchSections(attachProjectId),
    enabled: panelOpen && attachKind === "section" && Boolean(attachProjectId),
  });

  const buildAttachUnder = (): OutlineAttachUnder | null => {
    if (attachKind === "new") return null;
    if (attachKind === "epic") {
      if (!attachEpicId) return null;
      return { kind: "epic", id: attachEpicId };
    }
    if (attachKind === "project") {
      if (!attachProjectId) return null;
      return { kind: "project", id: attachProjectId };
    }
    if (!attachSectionId) return null;
    return { kind: "section", id: attachSectionId };
  };

  const navigateEpicId = (): string | null => {
    if (attachKind === "epic" && attachEpicId) return attachEpicId;
    if (attachKind === "project" && attachEpicId) return attachEpicId;
    if (attachKind === "section" && attachEpicId) return attachEpicId;
    return null;
  };

  const proposeMutation = useMutation({
    mutationFn: (outline: Record<string, unknown>) => {
      const attach_under = buildAttachUnder();
      if (attachKind !== "new" && !attach_under) {
        throw new Error("Pick a target parent before proposing");
      }
      return proposeOutline({
        template_id: templateId,
        outline,
        skip_optional: skipOptional,
        attach_under,
      });
    },
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
      const createdEpicId =
        data.results.find((r) => r.ok && r.action_type === "create_epic" && r.entity_id)?.entity_id ??
        null;
      const epicId = createdEpicId ?? navigateEpicId();
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
      closeShell();
      onApplied?.(epicId);
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

  const epics = epicsQuery.data?.items ?? [];
  const projects = projectsQuery.data?.items ?? [];
  const sections = sectionsQuery.data?.items ?? [];

  const attachHelp =
    attachKind === "new"
      ? "Creates a new epic from certificate.title."
      : attachKind === "epic"
        ? "Imports course(s) as projects under the selected epic. Use full certificate JSON or a course fragment."
        : attachKind === "project"
          ? "Imports modules as sections under the selected project. Use modules[] or a single-course fragment."
          : "Imports tasks into the selected section. Use tasks[] or a single-module fragment.";

  const flowBody = (
    <>
        <p className="outline-help muted small">
          Paste or upload an operator-owned outline JSON file. No Coursera sync — local file only.
        </p>
        <div className="outline-options">
          <label className="outline-option">
            <span className="outline-option-label">Template</span>
            <select
              value={templateId}
              onChange={(e) => setTemplateId(e.target.value as OutlineTemplateId)}
              aria-label="Outline template"
            >
              {TEMPLATE_OPTIONS.map((opt) => (
                <option key={opt.id} value={opt.id}>
                  {opt.label}
                </option>
              ))}
            </select>
          </label>
          <label className="outline-option">
            <span className="outline-option-label">Attach under</span>
            <select
              value={attachKind}
              onChange={(e) => {
                const next = e.target.value as OutlineAttachKind | "new";
                setAttachKind(next);
                setAttachEpicId("");
                setAttachProjectId("");
                setAttachSectionId("");
                setActions(null);
                setSummary(null);
              }}
              aria-label="Attach import under"
            >
              <option value="new">New epic (full tree)</option>
              <option value="epic">Existing epic</option>
              <option value="project">Existing project</option>
              <option value="section">Existing section</option>
            </select>
          </label>
        </div>
        {attachKind !== "new" && (
          <div className="outline-attach-targets">
            {(attachKind === "epic" || attachKind === "project" || attachKind === "section") && (
              <label className="outline-option">
                <span className="outline-option-label">Epic</span>
                <select
                  value={attachEpicId}
                  onChange={(e) => {
                    setAttachEpicId(e.target.value);
                    setAttachProjectId("");
                    setAttachSectionId("");
                  }}
                  aria-label="Target epic"
                >
                  <option value="">Select epic…</option>
                  {epics.map((epic) => (
                    <option key={epic.id} value={epic.id}>
                      {epic.title}
                    </option>
                  ))}
                </select>
              </label>
            )}
            {(attachKind === "project" || attachKind === "section") && (
              <label className="outline-option">
                <span className="outline-option-label">Project</span>
                <select
                  value={attachProjectId}
                  onChange={(e) => {
                    setAttachProjectId(e.target.value);
                    setAttachSectionId("");
                  }}
                  disabled={!attachEpicId}
                  aria-label="Target project"
                >
                  <option value="">Select project…</option>
                  {projects.map((project) => (
                    <option key={project.id} value={project.id}>
                      {project.title}
                    </option>
                  ))}
                </select>
              </label>
            )}
            {attachKind === "section" && (
              <label className="outline-option">
                <span className="outline-option-label">Section</span>
                <select
                  value={attachSectionId}
                  onChange={(e) => setAttachSectionId(e.target.value)}
                  disabled={!attachProjectId}
                  aria-label="Target section"
                >
                  <option value="">Select section…</option>
                  {sections.map((section) => (
                    <option key={section.id} value={section.id}>
                      {section.title}
                    </option>
                  ))}
                </select>
              </label>
            )}
            <p className="outline-help muted small">{attachHelp}</p>
          </div>
        )}
        <form className="outline-form" onSubmit={handlePropose}>
          <textarea
            className="outline-input"
            rows={8}
            value={jsonText}
            onChange={(e) => {
              setJsonText(e.target.value);
              setError(null);
            }}
            placeholder={
              attachKind === "new"
                ? "Paste outline JSON (certificate → courses → modules → tasks)"
                : attachKind === "epic"
                  ? "Paste certificate JSON or a course / courses[] fragment"
                  : attachKind === "project"
                    ? "Paste modules[] or course.modules fragment"
                    : "Paste tasks[] or module.tasks fragment"
            }
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
    </>
  );

  if (embedded) {
    return <div className="outline outline-embedded">{flowBody}</div>;
  }

  return (
    <div className="outline">
      <button
        type="button"
        className="btn secondary small outline-toggle"
        aria-expanded={internalOpen}
        onClick={() => setInternalOpen(true)}
      >
        Outline
      </button>
      <Modal open={internalOpen} title="Outline import" onClose={() => setInternalOpen(false)} className="outline-modal">
        {flowBody}
      </Modal>
    </div>
  );
}
