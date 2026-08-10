import { useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { fetchMe, fetchProjects, fetchTask } from "./api";
import { CalendarView } from "./components/CalendarView";
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
  const [view, setView] = useState<ViewSelection>({ type: "inbox" });
  const [selectedTaskId, setSelectedTaskId] = useState<string | null>(null);
  const quickAddRef = useRef<QuickAddHandle>(null);
  const searchRef = useRef<SearchBoxHandle>(null);
  const { undo } = useUndoStack();

  const me = useQuery({ queryKey: ["me"], queryFn: fetchMe });
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
      if (isEditableTarget(e.target)) return;

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

      if (e.key === "/") {
        e.preventDefault();
        searchRef.current?.focus();
      }
    };
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [undo]);

  return (
    <div className="shell">
      <Sidebar view={view} onSelectView={setView} />
      <div className="main">
        <header className="top-bar">
          <QuickAdd ref={quickAddRef} view={view} projects={projects} />
          <SearchBox ref={searchRef} onSelectTask={setSelectedTaskId} />
          {me.isSuccess && (
            <span className="user-chip">{me.data.display_name ?? me.data.email}</span>
          )}
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
