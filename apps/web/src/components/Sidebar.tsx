import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { fetchEpics, fetchProjects, type Epic, type Project } from "../api";
import type { ViewSelection } from "../view";
import { CreateEpicForm } from "./CreateEpicForm";
import { CreateProjectForm } from "./CreateProjectForm";

interface SidebarProps {
  view: ViewSelection;
  onSelectView: (view: ViewSelection) => void;
}

function NavItem({
  active,
  label,
  onClick,
  indent,
  swatchColor,
}: {
  active: boolean;
  label: string;
  onClick: () => void;
  indent?: boolean;
  swatchColor?: string;
}) {
  return (
    <button
      type="button"
      className={`nav-item${active ? " active" : ""}${indent ? " indent" : ""}`}
      onClick={onClick}
    >
      {swatchColor && (
        <span className="nav-swatch" style={{ backgroundColor: swatchColor }} aria-hidden />
      )}
      {label}
    </button>
  );
}

export function Sidebar({ view, onSelectView }: SidebarProps) {
  const [expandedEpics, setExpandedEpics] = useState<Set<string>>(new Set());
  const [showCreateEpic, setShowCreateEpic] = useState(false);
  const [createProjectEpicId, setCreateProjectEpicId] = useState<string | null | undefined>(
    undefined,
  );

  const epicsQuery = useQuery({ queryKey: ["epics"], queryFn: () => fetchEpics() });
  const projectsQuery = useQuery({ queryKey: ["projects"], queryFn: () => fetchProjects() });

  const epics = epicsQuery.data?.items ?? [];
  const projects = projectsQuery.data?.items ?? [];

  const standaloneProjects = projects.filter((p) => !p.epic_id);
  const projectsByEpic = epics.reduce<Record<string, Project[]>>((acc, epic) => {
    acc[epic.id] = projects.filter((p) => p.epic_id === epic.id);
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
          />
        ))}
      </nav>

      <CreateEpicForm open={showCreateEpic} onClose={() => setShowCreateEpic(false)} />
      <CreateProjectForm
        open={createProjectEpicId !== undefined}
        epicId={createProjectEpicId ?? null}
        onClose={() => setCreateProjectEpicId(undefined)}
      />
    </aside>
  );
}

export type { Project };
