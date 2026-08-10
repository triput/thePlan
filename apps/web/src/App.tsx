import { useQuery } from "@tanstack/react-query";
import { fetchEpics, fetchHealth, fetchMe, fetchTasks } from "./api";
import "./App.css";

function App() {
  const health = useQuery({ queryKey: ["health"], queryFn: fetchHealth });
  const me = useQuery({ queryKey: ["me"], queryFn: fetchMe });
  const epics = useQuery({ queryKey: ["epics"], queryFn: fetchEpics });
  const tasks = useQuery({ queryKey: ["tasks"], queryFn: fetchTasks });

  return (
    <div className="app">
      <header className="header">
        <h1>thePlan</h1>
        <p className="subtitle">Wave 0 scaffold — task + schedule app</p>
      </header>

      <section className="panel">
        <h2>API status</h2>
        {health.isLoading && <p>Checking health…</p>}
        {health.isError && <p className="error">API unreachable: {(health.error as Error).message}</p>}
        {health.isSuccess && (
          <p>
            Health: <code>{health.data.status}</code>
          </p>
        )}
        {me.isSuccess && (
          <p>
            Signed in as <strong>{me.data.display_name ?? me.data.email}</strong> ({me.data.email})
          </p>
        )}
      </section>

      <div className="columns">
        <section className="panel">
          <h2>Epics</h2>
          {epics.isLoading && <p>Loading…</p>}
          {epics.isError && <p className="error">Failed to load epics</p>}
          {epics.isSuccess && epics.data.items.length === 0 && <p className="muted">No epics yet.</p>}
          {epics.isSuccess && (
            <ul>
              {epics.data.items.map((epic) => (
                <li key={epic.id}>
                  <span className="swatch" style={{ backgroundColor: epic.color_hex }} />
                  {epic.title}
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className="panel">
          <h2>Tasks</h2>
          {tasks.isLoading && <p>Loading…</p>}
          {tasks.isError && <p className="error">Failed to load tasks</p>}
          {tasks.isSuccess && tasks.data.items.length === 0 && <p className="muted">No tasks yet — CRUD stubs ready.</p>}
          {tasks.isSuccess && (
            <ul>
              {tasks.data.items.map((task) => (
                <li key={task.id}>
                  {task.title}
                  <span className="badge">{task.priority}</span>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
    </div>
  );
}

export default App;
