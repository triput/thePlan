import type { Project, Section, Task } from "../api";
import { TaskDetailSection, type DetailSectionId } from "./TaskDetailSection";

interface TaskDetailDepsProps {
  open: boolean;
  onToggle: (id: DetailSectionId) => void;
  projectId: string;
  projects: Project[];
  onProjectChange: (value: string) => void;
  onOpenCreateProject: () => void;
  sectionId: string;
  sections: Section[];
  onSectionChange: (value: string) => void;
  parentTaskId: string;
  parentOptions: Task[];
  onParentTaskIdChange: (value: string) => void;
  canCreateChild: boolean;
  childTitle: string;
  onChildTitleChange: (value: string) => void;
  createChildPending: boolean;
  onCreateChild: () => void;
}

export function TaskDetailDeps({
  open,
  onToggle,
  projectId,
  projects,
  onProjectChange,
  onOpenCreateProject,
  sectionId,
  sections,
  onSectionChange,
  parentTaskId,
  parentOptions,
  onParentTaskIdChange,
  canCreateChild,
  childTitle,
  onChildTitleChange,
  createChildPending,
  onCreateChild,
}: TaskDetailDepsProps) {
  return (
    <TaskDetailSection id="dependencies" title="Dependencies" open={open} onToggle={onToggle}>
      <div className="field detail-project-field">
        <span>Project</span>
        <select
          className="field-select"
          value={projectId}
          onChange={(e) => onProjectChange(e.target.value)}
          aria-label="Project"
        >
          <option value="">Inbox</option>
          {projects.map((p) => (
            <option key={p.id} value={p.id}>
              {p.title}
            </option>
          ))}
        </select>
        <button
          type="button"
          className="btn secondary small detail-inline-create-btn"
          onClick={onOpenCreateProject}
        >
          + New project
        </button>
        <span className="field-hint muted small">
          Creates a project and selects it for this task (save to keep)
        </span>
      </div>
      {projectId && (
        <label className="field">
          <span>Section</span>
          <select
            className="field-select"
            value={sectionId}
            onChange={(e) => onSectionChange(e.target.value)}
          >
            <option value="">None</option>
            {sections.map((s) => (
              <option key={s.id} value={s.id}>
                {s.title}
              </option>
            ))}
          </select>
        </label>
      )}
      <label className="field">
        <span>Parent task</span>
        <select
          className="field-select"
          value={parentTaskId}
          onChange={(e) => onParentTaskIdChange(e.target.value)}
        >
          <option value="">None (top-level)</option>
          {parentOptions.map((t) => (
            <option key={t.id} value={t.id}>
              {t.title}
            </option>
          ))}
        </select>
      </label>
      {canCreateChild ? (
        <div className="inline-form detail-child-form">
          <label className="field detail-child-field">
            <span>New subtask</span>
            <input
              type="text"
              value={childTitle}
              onChange={(e) => onChildTitleChange(e.target.value)}
              onKeyDown={(e) => {
                if (e.key !== "Enter") return;
                e.preventDefault();
                onCreateChild();
              }}
              placeholder="Subtask title"
              autoComplete="off"
            />
          </label>
          <button
            type="button"
            className="btn primary small"
            disabled={!childTitle.trim() || createChildPending}
            onClick={onCreateChild}
          >
            {createChildPending ? "Creating…" : "Add subtask"}
          </button>
        </div>
      ) : (
        <p className="muted small">Max nesting depth — can’t add a subtask here.</p>
      )}
    </TaskDetailSection>
  );
}
