import { useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { fetchProjects, fetchTask } from "./api";
import { useAuth } from "./auth";
import { CalendarView } from "./components/CalendarView";
import { HelpOverlay } from "./components/HelpOverlay";
import { LabelsManagement } from "./components/LabelsManagement";
import { QuickAdd, type QuickAddHandle } from "./components/QuickAdd";
import { SearchBox, type SearchBoxHandle } from "./components/SearchBox";
import { Sidebar } from "./components/Sidebar";
import { TaskDetailPanel } from "./components/TaskDetailPanel";
import { TaskList } from "./components/TaskList";
import { emitToast, ToastHost } from "./components/ToastHost";
import { UndoStackProvider, useUndoStack } from "./undoStack";
import type { ViewSelection } from "./view";
import "./App.css";

function isEditableTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  return (
    target.tagName === "INPUT" ||
    target.tagName === "TEXTAREA" ||
    target.isContentEditable
  );
}

function AppInner() {
  const { user, logout } = useAuth();
  const [view, setView] = useState<ViewSelection>({ type: "inbox" });
  const [selectedTaskId, setSelectedTaskId] = useState<string | null>(null);
  const [helpOpen, setHelpOpen] = useState(false);
  const quickAddRef = useRef<QuickAddHandle>(null);
  const searchRef = useRef<SearchBoxHandle>(null);
  const { undo } = useUndoStack();

  const projectsQuery = useQuery({ queryKey: ["projects"], queryFn: () => fetchProjects() });
  const projects = projectsQuery.data?.items ?? [];

  const projectTitle =
    view.type === "project"
      ? projects.find((p) => p.id === view.projectId)?.title
      : undefined;

  const showTaskList = view.type !== "labels" && view.type !== "calendar";
  const showCalendar = view.type === "calendar";

  const selectedTaskQuery = useQuery({
    queryKey: ["task", selectedTaskId],
    queryFn: () => fetchTask(selectedTaskId!),
    enabled: selectedTaskId !== null,
  });

  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "?") {
        if (!isEditableTarget(e.target)) {
          e.preventDefault();
          setHelpOpen((open) => !open);
        }
        return;
      }

      if (isEditableTarget(e.target)) return;
      if (document.querySelector(".modal-backdrop")) return;

      if ((e.ctrlKey || e.metaKey) && e.key === "z" && !e.shiftKey) {
        e.preventDefault();
        void undo();
        return;
      }

      if (e.key === "q" || e.key === "Q") {
        e.preventDefault();
        quickAddRef.current?.focus();
        return;
      }

      if ((e.ctrlKey || e.metaKey) && (e.key === "k" || e.key === "K")) {
        e.preventDefault();
        quickAddRef.current?.focus();
        return;
      }

      if (e.key === "/") {
        e.preventDefault();
        searchRef.current?.focus();
      }
    };
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [undo]);

  const userLabel = user.display_name ?? user.username ?? user.email;

  return (
    <div className="shell">
      <Sidebar view={view} onSelectView={setView} />
      <div className="main">
        <header className="top-bar">
          <QuickAdd ref={quickAddRef} view={view} projects={projects} />
          <SearchBox ref={searchRef} onSelectTask={setSelectedTaskId} />
          <button
            type="button"
            className="icon-btn help-btn"
            onClick={() => setHelpOpen(true)}
            title="Keyboard shortcuts (?)"
            aria-label="Keyboard shortcuts"
          >
            ?
          </button>
          <div className="user-area">
            <span className="user-chip" title={user.email}>
              {userLabel}
            </span>
            <button
              type="button"
              className="btn secondary small logout-btn"
              onClick={() => void logout()}
            >
              Sign out
            </button>
          </div>
        </header>
        <div className={`main-body${selectedTaskId ? " with-task-detail" : ""}`}>
          <main className="main-content">
            {showCalendar ? (
              <CalendarView />
            ) : showTaskList ? (
              <TaskList
                view={view}
                projectTitle={projectTitle}
                selectedTaskId={selectedTaskId}
                onSelectTask={setSelectedTaskId}
              />
            ) : (
              <LabelsManagement />
            )}
          </main>
          {selectedTaskId && (
            selectedTaskQuery.isLoading ? (
              <aside className="task-detail-panel" aria-busy="true">
                <p className="muted">Loading task…</p>
              </aside>
            ) : selectedTaskQuery.isError ? (
              <aside className="task-detail-panel">
                <p className="form-error">
                  Failed to load task: {(selectedTaskQuery.error as Error).message}
                </p>
                <button type="button" className="btn secondary small" onClick={() => setSelectedTaskId(null)}>
                  Close
                </button>
              </aside>
            ) : (
              <TaskDetailPanel
                task={selectedTaskQuery.data ?? null}
                allTasks={selectedTaskQuery.data ? [selectedTaskQuery.data] : []}
                onClose={() => setSelectedTaskId(null)}
              />
            )
          )}
        </div>
      </div>
      <ToastHost />
      <HelpOverlay open={helpOpen} onClose={() => setHelpOpen(false)} />
    </div>
  );
}

function App() {
  return (
    <UndoStackProvider onToast={emitToast}>
      <AppInner />
    </UndoStackProvider>
  );
}

export default App;
