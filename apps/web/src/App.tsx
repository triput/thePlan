import { useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { fetchEpics, fetchProjects, fetchTask } from "./api";
import { useAuth } from "./auth";
import { CalendarView } from "./components/CalendarView";
import { HelpOverlay } from "./components/HelpOverlay";
import { LabelsManagement } from "./components/LabelsManagement";
import { QuickAdd, type QuickAddHandle } from "./components/QuickAdd";
import { AssistPanel } from "./components/AssistPanel";
import { ReminderPoller } from "./components/ReminderPoller";
import { SearchBox, type SearchBoxHandle } from "./components/SearchBox";
import { Sidebar } from "./components/Sidebar";
import { TaskDetailPanel } from "./components/TaskDetailPanel";
import { TaskList } from "./components/TaskList";
import { emitToast, ToastHost } from "./components/ToastHost";
import { NARROW_QUERY, useMediaQuery } from "./hooks/useMediaQuery";
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
  const isNarrow = useMediaQuery(NARROW_QUERY);
  const [view, setView] = useState<ViewSelection>({ type: "inbox" });
  const [selectedTaskId, setSelectedTaskId] = useState<string | null>(null);
  const [helpOpen, setHelpOpen] = useState(false);
  const [navOpen, setNavOpen] = useState(false);
  const quickAddRef = useRef<QuickAddHandle>(null);
  const searchRef = useRef<SearchBoxHandle>(null);
  const { undo } = useUndoStack();

  const projectsQuery = useQuery({ queryKey: ["projects"], queryFn: () => fetchProjects() });
  const epicsQuery = useQuery({ queryKey: ["epics"], queryFn: () => fetchEpics() });
  const projects = projectsQuery.data?.items ?? [];
  const epics = epicsQuery.data?.items ?? [];

  const projectTitle =
    view.type === "project"
      ? projects.find((p) => p.id === view.projectId)?.title
      : view.type === "epic"
        ? epics.find((e) => e.id === view.epicId)?.title
        : undefined;

  const showTaskList = view.type !== "labels" && view.type !== "calendar";
  const showCalendar = view.type === "calendar";

  const selectedTaskQuery = useQuery({
    queryKey: ["task", selectedTaskId],
    queryFn: () => fetchTask(selectedTaskId!),
    enabled: selectedTaskId !== null,
  });

  useEffect(() => {
    if (!isNarrow) setNavOpen(false);
  }, [isNarrow]);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    let changed = false;
    let openCalendar = false;

    const gcal = params.get("gcal");
    if (gcal) {
      if (gcal === "connected") {
        emitToast("Google Calendar connected");
        openCalendar = true;
      } else if (gcal === "error") {
        emitToast(`Google Calendar connect failed (${params.get("reason") ?? "error"})`);
      }
      params.delete("gcal");
      params.delete("reason");
      changed = true;
    }

    const mcal = params.get("mcal");
    if (mcal) {
      if (mcal === "connected") {
        emitToast("Microsoft Calendar connected");
        openCalendar = true;
      } else if (mcal === "error") {
        emitToast(`Microsoft Calendar connect failed (${params.get("reason") ?? "error"})`);
      }
      params.delete("mcal");
      params.delete("reason");
      changed = true;
    }

    if (openCalendar) setView({ type: "calendar" });
    if (changed) {
      const next = params.toString();
      window.history.replaceState({}, "", `${window.location.pathname}${next ? `?${next}` : ""}`);
    }
  }, []);

  const selectView = (next: ViewSelection) => {
    setView(next);
    setNavOpen(false);
    setSelectedTaskId(null);
  };

  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && navOpen) {
        e.preventDefault();
        setNavOpen(false);
        return;
      }

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
  }, [undo, navOpen]);

  const userLabel = user.display_name ?? user.username ?? user.email;
  const shellClass = [
    "shell",
    isNarrow ? "is-narrow" : "",
    navOpen ? "nav-open" : "",
    selectedTaskId ? "has-task-detail" : "",
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <div className={shellClass}>
      {navOpen && (
        <button
          type="button"
          className="nav-backdrop"
          aria-label="Close navigation"
          onClick={() => setNavOpen(false)}
        />
      )}
      <Sidebar view={view} onSelectView={selectView} onRequestClose={() => setNavOpen(false)} />
      <div className="main">
        <header className="top-bar">
          <button
            type="button"
            className="icon-btn nav-toggle"
            aria-label={navOpen ? "Close menu" : "Open menu"}
            aria-expanded={navOpen}
            onClick={() => setNavOpen((open) => !open)}
          >
            {navOpen ? "✕" : "☰"}
          </button>
          <QuickAdd ref={quickAddRef} view={view} projects={projects} />
          <AssistPanel />
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
              <aside className="task-detail-panel task-detail-sheet" aria-busy="true">
                <header className="detail-header">
                  <h2>Task details</h2>
                  <button
                    type="button"
                    className="icon-btn"
                    onClick={() => setSelectedTaskId(null)}
                    aria-label="Close panel"
                  >
                    ×
                  </button>
                </header>
                <p className="muted">Loading task…</p>
              </aside>
            ) : selectedTaskQuery.isError ? (
              <aside className="task-detail-panel task-detail-sheet">
                <header className="detail-header">
                  <h2>Task details</h2>
                  <button
                    type="button"
                    className="icon-btn"
                    onClick={() => setSelectedTaskId(null)}
                    aria-label="Close panel"
                  >
                    ×
                  </button>
                </header>
                <p className="form-error">
                  Failed to load task: {(selectedTaskQuery.error as Error).message}
                </p>
                <button type="button" className="btn secondary" onClick={() => setSelectedTaskId(null)}>
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
      <ReminderPoller />
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
