import { useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { fetchEpics, fetchProjects, fetchTask } from "./api";
import { useAuth } from "./auth";
import { CalendarView } from "./components/CalendarView";
import { HelpOverlay } from "./components/HelpOverlay";
import { ArchivedView } from "./components/ArchivedView";
import { LabelsManagement } from "./components/LabelsManagement";
import { TrashView } from "./components/TrashView";
import { QuickAdd, type QuickAddHandle } from "./components/QuickAdd";
import { AssistPanel } from "./components/AssistPanel";
import { ImportPanel } from "./components/ImportPanel";
import { ReminderPoller } from "./components/ReminderPoller";
import { SearchBox, type SearchBoxHandle } from "./components/SearchBox";
import { requestExpandEpic, Sidebar } from "./components/Sidebar";
import { SupportDock } from "./components/SupportDock";
import { TaskList } from "./components/TaskList";
import { UnsavedTaskChangesDialog } from "./components/UnsavedTaskChangesDialog";
import { emitToast, ToastHost } from "./components/ToastHost";
import type { TaskDetailPanelHandle } from "./components/TaskDetailPanel";
import { NARROW_QUERY, useMediaQuery } from "./hooks/useMediaQuery";
import { loadNavCollapsed, saveNavCollapsed } from "./navPrefs";
import {
  loadSupportDockCollapsed,
  saveSupportDockCollapsed,
} from "./supportDockPrefs";
import { SupportDockProvider, useSupportDock } from "./supportDockContext";
import {
  dirtyPromptFor,
  resolveSupportDockMode,
  type DirtyNavigationKind,
} from "./supportDockState";
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
  const [navCollapsed, setNavCollapsed] = useState(loadNavCollapsed);
  const [supportCollapsed, setSupportCollapsed] = useState(loadSupportDockCollapsed);
  const [dirtyNav, setDirtyNav] = useState<{
    kind: DirtyNavigationKind;
    proceed: () => void;
  } | null>(null);
  const [dirtySavePending, setDirtySavePending] = useState(false);
  const quickAddRef = useRef<QuickAddHandle>(null);
  const searchRef = useRef<SearchBoxHandle>(null);
  const taskDetailRef = useRef<TaskDetailPanelHandle>(null);
  const { undo } = useUndoStack();
  const { previewOpen, runSchedulePreview } = useSupportDock();

  const projectsQuery = useQuery({
    queryKey: ["projects"],
    queryFn: () => fetchProjects({ limit: 200 }),
  });
  const epicsQuery = useQuery({ queryKey: ["epics"], queryFn: () => fetchEpics({ limit: 200 }) });
  const projects = projectsQuery.data?.items ?? [];
  const epics = epicsQuery.data?.items ?? [];

  const projectTitle =
    view.type === "project"
      ? projects.find((p) => p.id === view.projectId)?.title
      : view.type === "epic"
        ? epics.find((e) => e.id === view.epicId)?.title
        : undefined;

  const showCalendar = view.type === "calendar";
  const showArchived = view.type === "archived";
  const showTrash = view.type === "trash";
  const showLabels = view.type === "labels";

  const selectedTaskQuery = useQuery({
    queryKey: ["task", selectedTaskId],
    queryFn: () => fetchTask(selectedTaskId!),
    enabled: selectedTaskId !== null,
  });

  useEffect(() => {
    if (!isNarrow) setNavOpen(false);
  }, [isNarrow]);

  useEffect(() => {
    const onSelectInbox = () => {
      setView({ type: "inbox" });
      setNavOpen(false);
      setSelectedTaskId(null);
    };
    window.addEventListener("theplan:select-inbox", onSelectInbox);
    return () => window.removeEventListener("theplan:select-inbox", onSelectInbox);
  }, []);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const savedViewId = params.get("saved_view") ?? params.get("view");
    if (savedViewId && /^[0-9a-f-]{36}$/i.test(savedViewId)) {
      setView({ type: "saved", id: savedViewId });
    }
  }, []);

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

  const runWithDirtyGuard = (kind: DirtyNavigationKind, proceed: () => void) => {
    if (selectedTaskId && taskDetailRef.current?.isDirty()) {
      setDirtyNav({ kind, proceed });
      return;
    }
    proceed();
  };

  const requestSelectTask = (taskId: string | null) => {
    if (taskId === selectedTaskId) return;
    if (taskId === null) {
      runWithDirtyGuard("close_task", () => setSelectedTaskId(null));
      return;
    }
    runWithDirtyGuard("switch_task", () => setSelectedTaskId(taskId));
  };

  const selectView = (next: ViewSelection) => {
    runWithDirtyGuard("change_view", () => {
      setView(next);
      setNavOpen(false);
      setSelectedTaskId(null);
    });
  };

  const revealSupportDock = () => {
    setSupportCollapsed(false);
    saveSupportDockCollapsed(false);
  };

  const collapseSupportDock = () => {
    setSupportCollapsed(true);
    saveSupportDockCollapsed(true);
    setSelectedTaskId(null);
  };

  const toggleSupportCollapsed = () => {
    if (!supportCollapsed) {
      runWithDirtyGuard("collapse_dock", () => {
        collapseSupportDock();
      });
      return;
    }
    revealSupportDock();
  };

  const startCalendarPreview = () => {
    revealSupportDock();
    void runSchedulePreview();
  };

  const handleCalendarPreview = () => {
    if (selectedTaskId) {
      runWithDirtyGuard("close_preview", () => {
        setSelectedTaskId(null);
        startCalendarPreview();
      });
      return;
    }
    startCalendarPreview();
  };

  useEffect(() => {
    try {
      const raw = localStorage.getItem("theplan.taskDetail.width");
      if (!raw) return;
      const parsed = Number(raw);
      if (!Number.isFinite(parsed)) return;
      const clamped = Math.min(720, Math.max(280, Math.round(parsed)));
      document.documentElement.style.setProperty("--task-detail-width", `${clamped}px`);
    } catch {
      /* ignore quota / private mode */
    }
  }, []);

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
  const toggleNavCollapsed = () => {
    setNavCollapsed((prev) => {
      const next = !prev;
      saveNavCollapsed(next);
      return next;
    });
  };

  const dockMode = resolveSupportDockMode({
    isCalendarView: showCalendar,
    dockCollapsed: supportCollapsed,
    selectedTaskId,
    previewOpen,
  });

  const supportDockActive =
    showCalendar && (dockMode !== "hidden" || (supportCollapsed && !selectedTaskId));

  const mainBodyClass = [
    "main-body",
    selectedTaskId && isNarrow ? "with-task-detail" : "",
    supportDockActive || selectedTaskId ? "with-support-dock" : "",
  ]
    .filter(Boolean)
    .join(" ");

  const shellClass = [
    "shell",
    isNarrow ? "is-narrow" : "",
    navOpen ? "nav-open" : "",
    !isNarrow && navCollapsed ? "nav-collapsed" : "",
    selectedTaskId ? "has-task-detail" : "",
    supportDockActive ? "has-support-dock" : "",
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
      <Sidebar
        view={view}
        onSelectView={selectView}
        onRequestClose={() => setNavOpen(false)}
        collapsed={!isNarrow && navCollapsed}
        onToggleCollapsed={toggleNavCollapsed}
        showCollapseControl={!isNarrow}
      />
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
          <div className="assist-cluster">
            <AssistPanel />
            <ImportPanel
              onApplied={(epicId) => {
                if (!epicId) return;
                requestExpandEpic(epicId);
                selectView({ type: "epic", epicId });
              }}
            />
          </div>
          <SearchBox ref={searchRef} onSelectTask={requestSelectTask} />
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
        <div className={mainBodyClass}>
          <main className="main-content">
            {showCalendar ? (
              <CalendarView
                onPreviewSchedule={handleCalendarPreview}
                onSelectTask={requestSelectTask}
              />
            ) : showArchived ? (
              <ArchivedView />
            ) : showTrash ? (
              <TrashView />
            ) : showLabels ? (
              <LabelsManagement />
            ) : (
              <TaskList
                view={view}
                projectTitle={projectTitle}
                selectedTaskId={selectedTaskId}
                onSelectTask={requestSelectTask}
              />
            )}
          </main>
          <SupportDock
            isCalendarView={showCalendar}
            isNarrow={isNarrow}
            dockCollapsed={supportCollapsed}
            onToggleCollapse={toggleSupportCollapsed}
            onOpenPreview={handleCalendarPreview}
            selectedTaskId={selectedTaskId}
            selectedTaskQuery={selectedTaskQuery}
            taskDetailRef={taskDetailRef}
            onCloseTask={() => requestSelectTask(null)}
            onSelectTask={(id) => requestSelectTask(id)}
          />
        </div>
      </div>
      <UnsavedTaskChangesDialog
        open={dirtyNav !== null}
        copy={dirtyPromptFor(dirtyNav?.kind ?? "close_task")}
        pending={dirtySavePending}
        onCancel={() => setDirtyNav(null)}
        onDiscard={() => {
          taskDetailRef.current?.discardDraft();
          const proceed = dirtyNav?.proceed;
          setDirtyNav(null);
          proceed?.();
        }}
        onSave={() => {
          void (async () => {
            setDirtySavePending(true);
            const ok = await taskDetailRef.current?.save(false);
            setDirtySavePending(false);
            if (!ok) return;
            const proceed = dirtyNav?.proceed;
            setDirtyNav(null);
            proceed?.();
          })();
        }}
      />
      <ToastHost />
      <ReminderPoller />
      <HelpOverlay open={helpOpen} onClose={() => setHelpOpen(false)} />
    </div>
  );
}

function App() {
  return (
    <UndoStackProvider onToast={emitToast}>
      <SupportDockProvider>
        <AppInner />
      </SupportDockProvider>
    </UndoStackProvider>
  );
}

export default App;
