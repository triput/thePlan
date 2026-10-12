/**
 * App shell navigation — epics/projects, smart views, Trash/Archived entry.
 * Owns sidebar expand/collapse and epic tree; settings opens as a panel.
 */
import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  fetchEpics,
  fetchLabels,
  fetchProjects,
  listViews,
  patchView,
  reorderProjects,
  type Epic,
  type Project,
  type SavedView,
} from "../api";
import { SavedViewFilterModal } from "./SavedViewFilterModal";
import {
  buildReorderSwap,
  canReorderDown,
  canReorderUp,
  compareBySortOrderThenName,
} from "../reorder";
import type { ViewSelection } from "../view";
import { CreateEpicForm } from "./CreateEpicForm";
import { CreateProjectForm } from "./CreateProjectForm";
import { EditEpicForm } from "./EditEpicForm";
import { EditProjectForm } from "./EditProjectForm";
import { ReorderButtons } from "./ReorderButtons";
import { SettingsPanel } from "./SettingsPanel";
import {
  loadNavSectionCollapsed,
  saveNavSectionCollapsed,
  type NavSectionId,
  type NavSectionCollapsed,
} from "../navPrefs";

const EXPAND_EPIC_EVENT = "theplan:expand-epic";

export function requestExpandEpic(epicId: string) {
  window.dispatchEvent(new CustomEvent(EXPAND_EPIC_EVENT, { detail: { epicId } }));
}

interface SidebarProps {
  view: ViewSelection;
  onSelectView: (view: ViewSelection) => void;
  onRequestClose?: () => void;
  collapsed?: boolean;
  onToggleCollapsed?: () => void;
  showCollapseControl?: boolean;
}

function NavItem({
  active,
  label,
  mark,
  onClick,
  indent,
  swatchColor,
  onEdit,
  reorder,
}: {
  active: boolean;
  label: string;
  mark?: string;
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
  const railMark = mark ?? label.charAt(0).toUpperCase();
  return (
    <div className={`nav-item-row${indent ? " indent" : ""}`}>
      <button
        type="button"
        className={`nav-item${active ? " active" : ""}`}
        onClick={onClick}
        aria-label={label}
        title={label}
      >
        {swatchColor && (
          <span className="nav-swatch" style={{ backgroundColor: swatchColor }} aria-hidden />
        )}
        <span className="nav-item-mark" aria-hidden>
          {railMark}
        </span>
        <span className="nav-item-label">{label}</span>
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

export function Sidebar({
  view,
  onSelectView,
  onRequestClose,
  collapsed = false,
  onToggleCollapsed,
  showCollapseControl = false,
}: SidebarProps) {
  const queryClient = useQueryClient();
  const [expandedEpics, setExpandedEpics] = useState<Set<string>>(new Set());
  const [showCreateEpic, setShowCreateEpic] = useState(false);
  const [createProjectEpicId, setCreateProjectEpicId] = useState<string | null | undefined>(
    undefined,
  );
  const [editingEpic, setEditingEpic] = useState<Epic | null>(null);
  const [editingProject, setEditingProject] = useState<Project | null>(null);
  const [showSettings, setShowSettings] = useState(false);
  const [showCreateSavedView, setShowCreateSavedView] = useState(false);
  const [sectionCollapsed, setSectionCollapsed] = useState<NavSectionCollapsed>(loadNavSectionCollapsed);

  const toggleNavSection = (id: NavSectionId) => {
    setSectionCollapsed((prev) => {
      const next = { ...prev, [id]: !prev[id] };
      saveNavSectionCollapsed(next);
      return next;
    });
  };

  const viewsQuery = useQuery({ queryKey: ["views"], queryFn: listViews });
  const userSavedViews = useMemo(() => {
    const rows = viewsQuery.data ?? [];
    return rows
      .filter((v) => !v.is_system)
      .sort((a, b) => a.sort_order - b.sort_order || a.name.localeCompare(b.name));
  }, [viewsQuery.data]);

  const epicsQuery = useQuery({ queryKey: ["epics"], queryFn: () => fetchEpics({ limit: 200 }) });
  const projectsQuery = useQuery({
    queryKey: ["projects"],
    queryFn: () => fetchProjects({ limit: 200 }),
  });
  const labelsQuery = useQuery({ queryKey: ["labels"], queryFn: () => fetchLabels({ limit: 200 }) });

  const epics = epicsQuery.data?.items ?? [];
  const projects = projectsQuery.data?.items ?? [];
  const labels = [...(labelsQuery.data?.items ?? [])].sort((a, b) => a.name.localeCompare(b.name));

  useEffect(() => {
    if (view.type === "epic") {
      setExpandedEpics((prev) => {
        if (prev.has(view.epicId)) return prev;
        const next = new Set(prev);
        next.add(view.epicId);
        return next;
      });
    }
  }, [view]);

  useEffect(() => {
    const onExpand = (event: Event) => {
      const epicId = (event as CustomEvent<{ epicId?: string }>).detail?.epicId;
      if (!epicId) return;
      setExpandedEpics((prev) => new Set(prev).add(epicId));
    };
    window.addEventListener(EXPAND_EPIC_EVENT, onExpand);
    return () => window.removeEventListener(EXPAND_EPIC_EVENT, onExpand);
  }, []);

  const reorderProjectsMutation = useMutation({
    mutationFn: reorderProjects,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["projects"] });
    },
  });

  const reorderSavedViewsMutation = useMutation({
    mutationFn: async (items: { id: string; sort_order: number }[]) => {
      await Promise.all(items.map((item) => patchView(item.id, { sort_order: item.sort_order })));
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["views"] });
    },
  });

  const handleReorderSavedView = (viewId: string, direction: "up" | "down") => {
    // Tie-break by name — must match userSavedViews display sort (M2).
    const items = buildReorderSwap(
      userSavedViews,
      viewId,
      direction,
      compareBySortOrderThenName,
    );
    if (!items) return;
    reorderSavedViewsMutation.mutate(items);
  };

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

  const isEpicActive = (epicId: string) => view.type === "epic" && view.epicId === epicId;

  const isLabelActive = (labelId: string) =>
    view.type === "label" && view.labelId === labelId;

  const isSavedViewActive = (row: SavedView) =>
    view.type === "saved" && view.id === row.id;

  const renderEpic = (epic: Epic) => {
    const expanded = expandedEpics.has(epic.id);
    const epicProjects = projectsByEpic[epic.id] ?? [];
    const epicActive = isEpicActive(epic.id);

    return (
      <div key={epic.id} className="epic-group">
        <div className={`epic-header${epicActive ? " active" : ""}`}>
          <button
            type="button"
            className="expand-btn"
            onClick={() => toggleEpic(epic.id)}
            aria-expanded={expanded}
            aria-label={`${expanded ? "Collapse" : "Expand"} ${epic.title}`}
          >
            {expanded ? "▾" : "▸"}
          </button>
          <button
            type="button"
            className={`epic-title-btn${epicActive ? " active" : ""}`}
            onClick={() => {
              setExpandedEpics((prev) => new Set(prev).add(epic.id));
              onSelectView({ type: "epic", epicId: epic.id });
            }}
            aria-label={epic.title}
            title={epic.title}
          >
            <span className="nav-swatch" style={{ backgroundColor: epic.color_hex }} aria-hidden />
            <span className="nav-item-mark epic-rail-mark" aria-hidden>
              {epic.title.charAt(0).toUpperCase()}
            </span>
            <span className="epic-title">{epic.title}</span>
          </button>
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
    <aside className={`sidebar${collapsed ? " is-collapsed" : ""}`}>
      <div className="sidebar-brand">
        <span className="brand-mark" aria-hidden>
          ◆
        </span>
        <span className="brand-name">thePlan</span>
        {showCollapseControl && onToggleCollapsed && (
          <button
            type="button"
            className="sidebar-collapse-btn"
            onClick={onToggleCollapsed}
            aria-expanded={!collapsed}
            aria-label={collapsed ? "Expand navigation" : "Collapse navigation"}
            title={collapsed ? "Expand navigation" : "Collapse navigation"}
          >
            <span aria-hidden>{collapsed ? "⟩" : "⟨"}</span>
          </button>
        )}
      </div>

      <nav className="sidebar-nav" aria-label="Main">
        <p className="nav-section-label">Views</p>
        <NavItem
          active={view.type === "inbox"}
          label="Inbox"
          mark="In"
          onClick={() => onSelectView({ type: "inbox" })}
        />
        <NavItem
          active={view.type === "work"}
          label="Work"
          mark="W"
          onClick={() => onSelectView({ type: "work" })}
        />
        <NavItem
          active={view.type === "today"}
          label="Today"
          mark="Td"
          onClick={() => onSelectView({ type: "today" })}
        />
        <NavItem
          active={view.type === "upcoming"}
          label="Upcoming"
          mark="Up"
          onClick={() => onSelectView({ type: "upcoming" })}
        />

        <div className="nav-section-header">
          <p className="nav-section-label">Saved views</p>
          <button
            type="button"
            className="icon-btn tiny"
            title="New saved view"
            aria-label="New saved view"
            onClick={() => setShowCreateSavedView(true)}
          >
            +
          </button>
        </div>
        {viewsQuery.isLoading && <p className="muted small">Loading…</p>}
        {userSavedViews.map((row) => (
          <NavItem
            key={row.id}
            active={isSavedViewActive(row)}
            label={row.name}
            indent
            onClick={() =>
              onSelectView({ type: "saved", id: row.id, slug: row.slug })
            }
            reorder={{
              canMoveUp: canReorderUp(userSavedViews, row.id, compareBySortOrderThenName),
              canMoveDown: canReorderDown(userSavedViews, row.id, compareBySortOrderThenName),
              onMoveUp: () => handleReorderSavedView(row.id, "up"),
              onMoveDown: () => handleReorderSavedView(row.id, "down"),
              pending: reorderSavedViewsMutation.isPending,
            }}
          />
        ))}
        {!viewsQuery.isLoading && userSavedViews.length === 0 && (
          <p className="muted small indent">No saved views yet.</p>
        )}

        <NavItem
          active={view.type === "calendar"}
          label="Calendar"
          mark="Cal"
          onClick={() => onSelectView({ type: "calendar" })}
        />

        <NavItem
          active={view.type === "labels"}
          label="Manage labels"
          mark="#"
          onClick={() => onSelectView({ type: "labels" })}
        />
        <NavItem
          active={view.type === "archived"}
          label="Archived"
          mark="Ar"
          onClick={() => onSelectView({ type: "archived" })}
        />
        <NavItem
          active={view.type === "trash"}
          label="Trash"
          mark="Tr"
          onClick={() => onSelectView({ type: "trash" })}
        />

        {labels.length > 0 && (
          <div className="nav-collapsible-section">
            <div className="nav-section-header">
              <button
                type="button"
                className="nav-section-toggle"
                aria-expanded={!sectionCollapsed.labels}
                onClick={() => toggleNavSection("labels")}
              >
                <span className="nav-section-chevron" aria-hidden>
                  {sectionCollapsed.labels ? "▸" : "▾"}
                </span>
                <span className="nav-section-label">Labels</span>
              </button>
            </div>
            {!sectionCollapsed.labels &&
              labels.map((label) => (
                <NavItem
                  key={label.id}
                  active={isLabelActive(label.id)}
                  label={label.name}
                  swatchColor={label.color_hex}
                  indent
                  onClick={() => onSelectView({ type: "label", labelId: label.id })}
                />
              ))}
          </div>
        )}

        <div className="nav-collapsible-section">
          <div className="nav-section-header">
            <button
              type="button"
              className="nav-section-toggle"
              aria-expanded={!sectionCollapsed.epics}
              onClick={() => toggleNavSection("epics")}
            >
              <span className="nav-section-chevron" aria-hidden>
                {sectionCollapsed.epics ? "▸" : "▾"}
              </span>
              <span className="nav-section-label">Epics</span>
            </button>
            <button
              type="button"
              className="icon-btn tiny"
              title="New epic"
              onClick={() => setShowCreateEpic(true)}
            >
              +
            </button>
          </div>
          {!sectionCollapsed.epics && (
            <>
              {epicsQuery.isLoading && <p className="muted small">Loading…</p>}
              {epics.map(renderEpic)}
            </>
          )}
        </div>

        <div className="nav-collapsible-section">
          <div className="nav-section-header">
            <button
              type="button"
              className="nav-section-toggle"
              aria-expanded={!sectionCollapsed.projects}
              onClick={() => toggleNavSection("projects")}
            >
              <span className="nav-section-chevron" aria-hidden>
                {sectionCollapsed.projects ? "▸" : "▾"}
              </span>
              <span className="nav-section-label">Projects</span>
            </button>
            <button
              type="button"
              className="icon-btn tiny"
              title="New standalone project"
              onClick={() => setCreateProjectEpicId(null)}
            >
              +
            </button>
          </div>
          {!sectionCollapsed.projects &&
            standaloneProjects.map((project) => (
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
        </div>
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
          <span className="settings-btn-label">Settings</span>
        </button>
      </footer>

      <SavedViewFilterModal
        open={showCreateSavedView}
        mode="create"
        onClose={() => setShowCreateSavedView(false)}
        onSaved={(row) => {
          onSelectView({ type: "saved", id: row.id, slug: row.slug });
        }}
      />
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
