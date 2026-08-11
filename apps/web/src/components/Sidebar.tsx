import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { fetchEpics, fetchLabels, fetchProjects, reorderProjects, type Epic, type Project } from "../api";
import { buildReorderSwap, canReorderDown, canReorderUp } from "../reorder";
import type { ViewSelection } from "../view";
import { CreateEpicForm } from "./CreateEpicForm";
import { CreateProjectForm } from "./CreateProjectForm";
import { EditEpicForm } from "./EditEpicForm";
import { EditProjectForm } from "./EditProjectForm";
import { ReorderButtons } from "./ReorderButtons";
import { SettingsPanel } from "./SettingsPanel";

interface SidebarProps {
  view: ViewSelection;
  onSelectView: (view: ViewSelection) => void;
  onRequestClose?: () => void;
}

function NavItem({
  active,
  label,
  onClick,
  indent,
  swatchColor,
  onEdit,
  reorder,
}: {
  active: boolean;
  label: string;
  onClick: () => void;
  indent?: boolean;
  swatchColor?: string;
  onEdit?: () => void;
  reorder?: {
    canMoveUp: boolean;
    canMoveDown: boolean;
    onMoveUp: () => void;
    onMoveDown: () => void;
    pending?: boolean;
  };
}) {
  return (
    <div className={`nav-item-row${indent ? " indent" : ""}`}>
      <button type="button" className={`nav-item${active ? " active" : ""}`} onClick={onClick}>
        {swatchColor && (
          <span className="nav-swatch" style={{ backgroundColor: swatchColor }} aria-hidden />
        )}
        {label}
      </button>
      {reorder && (
        <ReorderButtons
          label={label}
          canMoveUp={reorder.canMoveUp}
          canMoveDown={reorder.canMoveDown}
          onMoveUp={reorder.onMoveUp}
          onMoveDown={reorder.onMoveDown}
          pending={reorder.pending}
          className="nav-reorder-btns"
        />
      )}
      {onEdit && (
        <button
          type="button"
          className="icon-btn tiny nav-edit-btn"
          title={`Edit ${label}`}
          aria-label={`Edit ${label}`}
          onClick={(e) => {
            e.stopPropagation();
            onEdit();
          }}
        >
          ✎
        </button>
      )}
    </div>
  );
}

export function Sidebar({ view, onSelectView, onRequestClose }: SidebarProps) {
  const queryClient = useQueryClient();
  const [expandedEpics, setExpandedEpics] = useState<Set<string>>(new Set());
  const [showCreateEpic, setShowCreateEpic] = useState(false);
  const [createProjectEpicId, setCreateProjectEpicId] = useState<string | null | undefined>(
    undefined,
  );
  const [editingEpic, setEditingEpic] = useState<Epic | null>(null);
  const [editingProject, setEditingProject] = useState<Project | null>(null);
  const [showSettings, setShowSettings] = useState(false);

  const epicsQuery = useQuery({ queryKey: ["epics"], queryFn: () => fetchEpics() });
  const projectsQuery = useQuery({ queryKey: ["projects"], queryFn: () => fetchProjects() });
  const labelsQuery = useQuery({ queryKey: ["labels"], queryFn: () => fetchLabels({ limit: 200 }) });

  const epics = epicsQuery.data?.items ?? [];
  const projects = projectsQuery.data?.items ?? [];
  const labels = [...(labelsQuery.data?.items ?? [])].sort((a, b) => a.name.localeCompare(b.name));

  const reorderProjectsMutation = useMutation({
    mutationFn: reorderProjects,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["projects"] });
    },
  });

  const handleReorderProject = (group: Project[], projectId: string, direction: "up" | "down") => {
    const items = buildReorderSwap(group, projectId, direction);
    if (items) reorderProjectsMutation.mutate({ items });
  };

  const standaloneProjects = [...projects.filter((p) => !p.epic_id)].sort(
    (a, b) => a.sort_order - b.sort_order,
  );
  const projectsByEpic = epics.reduce<Record<string, Project[]>>((acc, epic) => {
    acc[epic.id] = projects
      .filter((p) => p.epic_id === epic.id)
      .sort((a, b) => a.sort_order - b.sort_order);
    return acc;
  }, {});

  const toggleEpic = (epicId: string) => {
    setExpandedEpics((prev) => {
      const next = new Set(prev);
      if (next.has(epicId)) next.delete(epicId);
      else next.add(epicId);
      return next;
    });
  };

  const isProjectActive = (projectId: string) =>
    view.type === "project" && view.projectId === projectId;

  const isLabelActive = (labelId: string) =>
    view.type === "label" && view.labelId === labelId;

  const renderEpic = (epic: Epic) => {
    const expanded = expandedEpics.has(epic.id);
    const epicProjects = projectsByEpic[epic.id] ?? [];

    return (
      <div key={epic.id} className="epic-group">
        <div className="epic-header">
          <button
            type="button"
            className="expand-btn"
            onClick={() => toggleEpic(epic.id)}
            aria-expanded={expanded}
            aria-label={`${expanded ? "Collapse" : "Expand"} ${epic.title}`}
          >
            {expanded ? "▾" : "▸"}
          </button>
          <span className="nav-swatch" style={{ backgroundColor: epic.color_hex }} aria-hidden />
          <span className="epic-title">{epic.title}</span>
          <button
            type="button"
            className="icon-btn tiny"
            title="Edit epic"
            onClick={() => setEditingEpic(epic)}
          >
            ✎
          </button>
          <button
            type="button"
            className="icon-btn tiny"
            title="Add project to epic"
            onClick={() => setCreateProjectEpicId(epic.id)}
          >
            +
          </button>
        </div>
        {expanded &&
          epicProjects.map((project) => (
            <NavItem
              key={project.id}
              active={isProjectActive(project.id)}
              label={project.title}
              swatchColor={project.color_hex}
              indent
              onClick={() => onSelectView({ type: "project", projectId: project.id })}
              onEdit={() => setEditingProject(project)}
              reorder={{
                canMoveUp: canReorderUp(epicProjects, project.id),
                canMoveDown: canReorderDown(epicProjects, project.id),
                onMoveUp: () => handleReorderProject(epicProjects, project.id, "up"),
                onMoveDown: () => handleReorderProject(epicProjects, project.id, "down"),
                pending: reorderProjectsMutation.isPending,
              }}
            />
          ))}
      </div>
    );
  };

  return (
    <aside className="sidebar">
      <div className="sidebar-brand">
        <span className="brand-mark">◆</span>
        <span className="brand-name">thePlan</span>
      </div>

      <nav className="sidebar-nav" aria-label="Main">
        <p className="nav-section-label">Views</p>
        <NavItem
          active={view.type === "inbox"}
          label="Inbox"
          onClick={() => onSelectView({ type: "inbox" })}
        />
        <NavItem
          active={view.type === "today"}
          label="Today"
          onClick={() => onSelectView({ type: "today" })}
        />
        <NavItem
          active={view.type === "upcoming"}
          label="Upcoming"
          onClick={() => onSelectView({ type: "upcoming" })}
        />
        <NavItem
          active={view.type === "calendar"}
          label="Calendar"
          onClick={() => onSelectView({ type: "calendar" })}
        />

        <NavItem
          active={view.type === "labels"}
          label="Labels"
          onClick={() => onSelectView({ type: "labels" })}
        />

        {labels.length > 0 && (
          <>
            <p className="nav-section-label">By label</p>
            {labels.map((label) => (
              <NavItem
                key={label.id}
                active={isLabelActive(label.id)}
                label={label.name}
                swatchColor={label.color_hex}
                indent
                onClick={() => onSelectView({ type: "label", labelId: label.id })}
              />
            ))}
          </>
        )}

        <div className="nav-section-header">
          <p className="nav-section-label">Epics</p>
          <button
            type="button"
            className="icon-btn tiny"
            title="New epic"
            onClick={() => setShowCreateEpic(true)}
          >
            +
          </button>
        </div>
        {epicsQuery.isLoading && <p className="muted small">Loading…</p>}
        {epics.map(renderEpic)}

        <div className="nav-section-header">
          <p className="nav-section-label">Projects</p>
          <button
            type="button"
            className="icon-btn tiny"
            title="New standalone project"
            onClick={() => setCreateProjectEpicId(null)}
          >
            +
          </button>
        </div>
        {standaloneProjects.map((project) => (
          <NavItem
            key={project.id}
            active={isProjectActive(project.id)}
            label={project.title}
            swatchColor={project.color_hex}
            onClick={() => onSelectView({ type: "project", projectId: project.id })}
            onEdit={() => setEditingProject(project)}
            reorder={{
              canMoveUp: canReorderUp(standaloneProjects, project.id),
              canMoveDown: canReorderDown(standaloneProjects, project.id),
              onMoveUp: () => handleReorderProject(standaloneProjects, project.id, "up"),
              onMoveDown: () => handleReorderProject(standaloneProjects, project.id, "down"),
              pending: reorderProjectsMutation.isPending,
            }}
          />
        ))}
      </nav>

      <footer className="sidebar-footer">
        <button
          type="button"
          className="settings-btn"
          onClick={() => {
            setShowSettings(true);
            onRequestClose?.();
          }}
          aria-label="Settings"
          title="Settings"
        >
          <span className="settings-btn-icon" aria-hidden>
            ⚙
          </span>
          <span>Settings</span>
        </button>
      </footer>

      <SettingsPanel open={showSettings} onClose={() => setShowSettings(false)} />
      <CreateEpicForm open={showCreateEpic} onClose={() => setShowCreateEpic(false)} />
      <CreateProjectForm
        open={createProjectEpicId !== undefined}
        epicId={createProjectEpicId ?? null}
        onClose={() => setCreateProjectEpicId(undefined)}
      />
      <EditEpicForm epic={editingEpic} onClose={() => setEditingEpic(null)} />
      <EditProjectForm
        project={editingProject}
        onClose={() => setEditingProject(null)}
        view={view}
        onSelectView={onSelectView}
      />
    </aside>
  );
}

export type { Project };
