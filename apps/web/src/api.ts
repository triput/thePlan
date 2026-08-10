const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}

export interface User {
  id: string;
  email: string;
  display_name: string | null;
}

export interface Epic {
  id: string;
  title: string;
  description: string | null;
  color_hex: string;
  start_date: string | null;
  target_date: string | null;
  sort_order: number;
  is_archived: boolean;
}

export interface Project {
  id: string;
  title: string;
  description: string | null;
  epic_id: string | null;
  color_hex: string;
  sort_order: number;
  is_archived: boolean;
}

export interface Section {
  id: string;
  project_id: string;
  title: string;
  sort_order: number;
}

export type TaskPriority = "p1" | "p2" | "p3" | "p4";

export interface Label {
  id: string;
  name: string;
  color_hex: string;
  task_count?: number;
}

export interface Task {
  id: string;
  title: string;
  description: string | null;
  project_id: string | null;
  section_id: string | null;
  parent_task_id: string | null;
  nesting_level: number;
  priority: TaskPriority;
  due_at: string | null;
  deadline_at: string | null;
  soft_target_at: string | null;
  estimated_duration_minutes: number;
  is_completed: boolean;
  completed_at: string | null;
  status: string;
  sort_order: number;
  label_ids: string[];
  open_subtask_count: number;
}

export interface ApiErrorBody {
  detail: string;
  code?: string;
  open_count?: number;
}

export class ApiError extends Error {
  status: number;
  code?: string;
  openCount?: number;

  constructor(status: number, body: ApiErrorBody) {
    super(body.detail);
    this.name = "ApiError";
    this.status = status;
    this.code = body.code;
    this.openCount = body.open_count;
  }
}

export interface EpicCreate {
  title: string;
  description?: string | null;
  color_hex?: string;
}

export interface EpicUpdate {
  title?: string;
  description?: string | null;
  color_hex?: string;
}

export interface ProjectCreate {
  title: string;
  description?: string | null;
  epic_id?: string | null;
  color_hex?: string;
}

export interface ProjectUpdate {
  title?: string;
  description?: string | null;
  epic_id?: string | null;
  color_hex?: string;
}

export interface SectionCreate {
  project_id: string;
  title: string;
  sort_order?: number;
}

export interface SectionUpdate {
  title?: string;
  sort_order?: number;
}

export interface TaskCreate {
  title: string;
  description?: string | null;
  project_id?: string | null;
  section_id?: string | null;
  parent_task_id?: string | null;
  priority?: TaskPriority;
  due_at?: string | null;
  estimated_duration_minutes?: number;
  label_ids?: string[];
}

export interface TaskUpdate {
  title?: string;
  description?: string | null;
  project_id?: string | null;
  section_id?: string | null;
  parent_task_id?: string | null;
  priority?: TaskPriority;
  due_at?: string | null;
  estimated_duration_minutes?: number;
  label_ids?: string[];
}

export interface TaskCompleteBody {
  bulk_children?: boolean;
  force_parent_only?: boolean;
}

export interface LabelCreate {
  name: string;
  color_hex?: string;
}

export interface LabelUpdate {
  name?: string;
  color_hex?: string;
}

export interface QuickAddParseResponse {
  title: string;
  priority: TaskPriority | null;
  estimated_duration_minutes: number | null;
  due_at: string | null;
  epic_id: string | null;
  project_id: string | null;
  section_id: string | null;
  preferred_time_window_id: string | null;
  unresolved: string[];
}

type QueryParams = Record<string, string | number | boolean | undefined | null>;

function buildUrl(path: string, params?: QueryParams): string {
  const url = new URL(`${API_URL}${path}`);
  if (params) {
    for (const [key, value] of Object.entries(params)) {
      if (value !== undefined && value !== null) {
        url.searchParams.set(key, String(value));
      }
    }
  }
  return url.toString();
}

async function parseError(response: Response): Promise<ApiError> {
  let body: ApiErrorBody = { detail: response.statusText };
  try {
    body = (await response.json()) as ApiErrorBody;
  } catch {
    /* empty body */
  }
  return new ApiError(response.status, body);
}

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...init?.headers,
    },
  });
  if (!response.ok) {
    throw await parseError(response);
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return response.json() as T;
}

async function apiFetchUrl<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...init?.headers,
    },
  });
  if (!response.ok) {
    throw await parseError(response);
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return response.json() as T;
}

export function fetchHealth() {
  return apiFetch<{ status: string }>("/health");
}

export function fetchMe() {
  return apiFetch<User>("/api/v1/auth/me");
}

export function fetchEpics(params?: { archived?: boolean; limit?: number; offset?: number }) {
  return apiFetchUrl<PaginatedResponse<Epic>>(buildUrl("/api/v1/epics", params));
}

export function createEpic(body: EpicCreate) {
  return apiFetch<Epic>("/api/v1/epics", { method: "POST", body: JSON.stringify(body) });
}

export function updateEpic(epicId: string, body: EpicUpdate) {
  return apiFetch<Epic>(`/api/v1/epics/${epicId}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
}

export function deleteEpic(epicId: string) {
  return apiFetch<void>(`/api/v1/epics/${epicId}`, { method: "DELETE" });
}

export function archiveEpic(epicId: string) {
  return apiFetch<Epic>(`/api/v1/epics/${epicId}/archive`, { method: "POST" });
}

export function fetchProjects(params?: {
  epic_id?: string;
  archived?: boolean;
  limit?: number;
  offset?: number;
}) {
  return apiFetchUrl<PaginatedResponse<Project>>(buildUrl("/api/v1/projects", params));
}

export function createProject(body: ProjectCreate) {
  return apiFetch<Project>("/api/v1/projects", { method: "POST", body: JSON.stringify(body) });
}

export function updateProject(projectId: string, body: ProjectUpdate) {
  return apiFetch<Project>(`/api/v1/projects/${projectId}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
}

export function deleteProject(projectId: string) {
  return apiFetch<void>(`/api/v1/projects/${projectId}`, { method: "DELETE" });
}

export function archiveProject(projectId: string) {
  return apiFetch<Project>(`/api/v1/projects/${projectId}/archive`, { method: "POST" });
}

export function fetchSections(projectId: string) {
  return apiFetchUrl<PaginatedResponse<Section>>(
    buildUrl("/api/v1/sections", { project_id: projectId }),
  );
}

export function createSection(body: SectionCreate) {
  return apiFetch<Section>("/api/v1/sections", { method: "POST", body: JSON.stringify(body) });
}

export function updateSection(sectionId: string, body: SectionUpdate) {
  return apiFetch<Section>(`/api/v1/sections/${sectionId}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
}

export function deleteSection(sectionId: string) {
  return apiFetch<void>(`/api/v1/sections/${sectionId}`, { method: "DELETE" });
}

export function fetchTasks(params?: {
  project_id?: string;
  section_id?: string;
  parent_task_id?: string;
  label_id?: string;
  is_completed?: boolean;
  inbox?: boolean;
  limit?: number;
  offset?: number;
}) {
  return apiFetchUrl<PaginatedResponse<Task>>(buildUrl("/api/v1/tasks", params));
}

export function fetchLabels(params?: { limit?: number; offset?: number }) {
  return apiFetchUrl<PaginatedResponse<Label>>(buildUrl("/api/v1/labels", params));
}

export function createLabel(body: LabelCreate) {
  return apiFetch<Label>("/api/v1/labels", { method: "POST", body: JSON.stringify(body) });
}

export async function createLabelsBatch(bodies: LabelCreate[]): Promise<Label[]> {
  if (bodies.length === 0) return [];
  try {
    const response = await fetch(`${API_URL}/api/v1/labels/batch`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ labels: bodies }),
    });
    if (response.status === 404 || response.status === 405) {
      throw new Error("batch unavailable");
    }
    if (!response.ok) {
      throw await parseError(response);
    }
    const data = (await response.json()) as { items: Label[]; skipped?: unknown[] };
    return data.items ?? [];
  } catch (err) {
    if (err instanceof ApiError) throw err;
    const results: Label[] = [];
    for (const body of bodies) {
      try {
        results.push(await createLabel(body));
      } catch {
        // skip duplicates when falling back to sequential create
      }
    }
    return results;
  }
}

export function updateLabel(labelId: string, body: LabelUpdate) {
  return apiFetch<Label>(`/api/v1/labels/${labelId}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
}

export function deleteLabel(labelId: string) {
  return apiFetch<void>(`/api/v1/labels/${labelId}`, { method: "DELETE" });
}

export function createTask(body: TaskCreate) {
  return apiFetch<Task>("/api/v1/tasks", { method: "POST", body: JSON.stringify(body) });
}

export function updateTask(taskId: string, body: TaskUpdate) {
  return apiFetch<Task>(`/api/v1/tasks/${taskId}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
}

export function deleteTask(taskId: string) {
  return apiFetch<void>(`/api/v1/tasks/${taskId}`, { method: "DELETE" });
}

export function completeTask(taskId: string, body: TaskCompleteBody = {}) {
  return apiFetch<Task>(`/api/v1/tasks/${taskId}/complete`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function uncompleteTask(taskId: string) {
  return apiFetch<Task>(`/api/v1/tasks/${taskId}/uncomplete`, { method: "POST" });
}

export function parseQuickAdd(text: string) {
  return apiFetch<QuickAddParseResponse>("/api/v1/quick-add/parse", {
    method: "POST",
    body: JSON.stringify({ text }),
  });
}

export interface ReorderItem {
  id: string;
  sort_order: number;
}

export interface ReorderBody {
  items: ReorderItem[];
}

export function reorderProjects(body: ReorderBody) {
  return apiFetch<void>("/api/v1/projects/reorder", {
    method: "PATCH",
    body: JSON.stringify(body),
  });
}

export function reorderSections(body: ReorderBody) {
  return apiFetch<void>("/api/v1/sections/reorder", {
    method: "PATCH",
    body: JSON.stringify(body),
  });
}

export function reorderTasks(body: ReorderBody) {
  return apiFetch<void>("/api/v1/tasks/reorder", {
    method: "PATCH",
    body: JSON.stringify(body),
  });
}

export { API_URL };
