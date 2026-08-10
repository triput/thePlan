import { useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { fetchMe, fetchProjects } from "./api";
import { LabelsManagement } from "./components/LabelsManagement";
import { QuickAdd, type QuickAddHandle } from "./components/QuickAdd";
import { Sidebar } from "./components/Sidebar";
import { TaskList } from "./components/TaskList";
import type { ViewSelection } from "./view";
import "./App.css";

function App() {
  const [view, setView] = useState<ViewSelection>({ type: "inbox" });
  const quickAddRef = useRef<QuickAddHandle>(null);

  const me = useQuery({ queryKey: ["me"], queryFn: fetchMe });
  const projectsQuery = useQuery({ queryKey: ["projects"], queryFn: () => fetchProjects() });
  const projects = projectsQuery.data?.items ?? [];

  const projectTitle =
    view.type === "project"
      ? projects.find((p) => p.id === view.projectId)?.title
      : undefined;

  const showTaskList = view.type !== "labels";

  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key !== "q" && e.key !== "Q") return;
      const target = e.target as HTMLElement;
      if (
        target.tagName === "INPUT" ||
        target.tagName === "TEXTAREA" ||
        target.isContentEditable
      ) {
        return;
      }
      e.preventDefault();
      quickAddRef.current?.focus();
    };
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, []);

  return (
    <div className="shell">
      <Sidebar view={view} onSelectView={setView} />
      <div className="main">
        <header className="top-bar">
          <QuickAdd ref={quickAddRef} view={view} projects={projects} />
          {me.isSuccess && (
            <span className="user-chip">{me.data.display_name ?? me.data.email}</span>
          )}
        </header>
        <main className="main-content">
          {showTaskList ? (
            <TaskList view={view} projectTitle={projectTitle} />
          ) : (
            <LabelsManagement />
          )}
        </main>
      </div>
    </div>
  );
}

export default App;
