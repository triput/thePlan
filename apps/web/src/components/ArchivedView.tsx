import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  fetchEpics,
  fetchProjects,
  unarchiveEpic,
  unarchiveProject,
  type Epic,
  type Project,
} from "../api";
import { emitToast } from "./ToastHost";

function ArchivedRow({
  kind,
  title,
  colorHex,
  subtitle,
  onRestore,
  pending,
  error,
}: {
  kind: "Epic" | "Project";
  title: string;
  colorHex: string;
  subtitle?: string;
  onRestore: () => void;
  pending: boolean;
  error?: string;
}) {
  return (
    <li className="archived-row">
      <span className="label-swatch" style={{ backgroundColor: colorHex }} aria-hidden />
      <div className="archived-row-text">
        <span className="archived-row-title">{title}</span>
        <span className="archived-row-meta muted">
          {kind}
          {subtitle ? ` · ${subtitle}` : ""}
        </span>
        {error && <span className="form-error">{error}</span>}
      </div>
      <button
        type="button"
        className="btn secondary small"
        onClick={onRestore}
        disabled={pending}
        aria-label={`Restore ${kind.toLowerCase()} ${title}`}
      >
        {pending ? "Restoring…" : "Unarchive"}
      </button>
    </li>
  );
}

export function ArchivedView() {
  const queryClient = useQueryClient();

  const epicsQuery = useQuery({
    queryKey: ["epics", "archived"],
    queryFn: () => fetchEpics({ archived: true, limit: 200 }),
  });
  const projectsQuery = useQuery({
    queryKey: ["projects", "archived"],
    queryFn: () => fetchProjects({ archived: true, limit: 200 }),
  });
  // Active epics (often already cached) — titles for archived projects still under a live epic.
  const activeEpicsQuery = useQuery({
    queryKey: ["epics"],
    queryFn: () => fetchEpics({ limit: 200 }),
  });

  const epics = epicsQuery.data?.items ?? [];
  const projects = projectsQuery.data?.items ?? [];

  const epicTitleById = new Map<string, string>();
  for (const e of activeEpicsQuery.data?.items ?? []) epicTitleById.set(e.id, e.title);
  for (const e of epics) epicTitleById.set(e.id, e.title);

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ["epics"] });
    queryClient.invalidateQueries({ queryKey: ["projects"] });
  };

  const unarchiveEpicMutation = useMutation({
    mutationFn: (epicId: string) => unarchiveEpic(epicId),
    onSuccess: (epic: Epic) => {
      invalidate();
      emitToast(`Restored epic “${epic.title}”`);
    },
  });

  const unarchiveProjectMutation = useMutation({
    mutationFn: (projectId: string) => unarchiveProject(projectId),
    onSuccess: (project: Project) => {
      invalidate();
      emitToast(`Restored project “${project.title}”`);
    },
  });

  const loading = epicsQuery.isLoading || projectsQuery.isLoading;
  const loadError =
    (epicsQuery.isError && (epicsQuery.error as Error).message) ||
    (projectsQuery.isError && (projectsQuery.error as Error).message) ||
    null;
  const empty = !loading && !loadError && epics.length === 0 && projects.length === 0;

  return (
    <div className="archived-view">
      <header className="pane-header">
        <h1>Archived</h1>
      </header>

      {loading && <p className="muted">Loading archived items…</p>}
      {loadError && <p className="form-error">{loadError}</p>}
      {empty && (
        <p className="empty-state">Nothing archived. Archive an epic or project from its edit menu.</p>
      )}

      {epics.length > 0 && (
        <section className="labels-section">
          <h2 className="labels-section-title">Epics</h2>
          <ul className="labels-list" aria-label="Archived epics">
            {epics.map((epic) => (
              <ArchivedRow
                key={epic.id}
                kind="Epic"
                title={epic.title}
                colorHex={epic.color_hex}
                onRestore={() => unarchiveEpicMutation.mutate(epic.id)}
                pending={
                  unarchiveEpicMutation.isPending && unarchiveEpicMutation.variables === epic.id
                }
                error={
                  unarchiveEpicMutation.isError && unarchiveEpicMutation.variables === epic.id
                    ? (unarchiveEpicMutation.error as Error).message
                    : undefined
                }
              />
            ))}
          </ul>
        </section>
      )}

      {projects.length > 0 && (
        <section className="labels-section">
          <h2 className="labels-section-title">Projects</h2>
          <ul className="labels-list" aria-label="Archived projects">
            {projects.map((project) => (
              <ArchivedRow
                key={project.id}
                kind="Project"
                title={project.title}
                colorHex={project.color_hex}
                subtitle={
                  project.epic_id
                    ? (epicTitleById.get(project.epic_id) ?? "Epic archived or unknown")
                    : "Standalone"
                }
                onRestore={() => unarchiveProjectMutation.mutate(project.id)}
                pending={
                  unarchiveProjectMutation.isPending &&
                  unarchiveProjectMutation.variables === project.id
                }
                error={
                  unarchiveProjectMutation.isError &&
                  unarchiveProjectMutation.variables === project.id
                    ? (unarchiveProjectMutation.error as Error).message
                    : undefined
                }
              />
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
