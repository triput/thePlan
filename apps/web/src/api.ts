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

export interface ProjectCreate {
  title: string;
  description?: string | null;
  epic_id?: string | null;
  color_hex?: string;
}

export interface SectionCreate {
  project_id: string;
  title: string;
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

export interface TaskCompleteBody {
  bulk_children?: boolean;
  force_parent_only?: boolean;
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

export function fetchSections(projectId: string) {
  return apiFetchUrl<PaginatedResponse<Section>>(
    buildUrl("/api/v1/sections", { project_id: projectId }),
  );
}

export function createSection(body: SectionCreate) {
  return apiFetch<Section>("/api/v1/sections", { method: "POST", body: JSON.stringify(body) });
}

export function fetchTasks(params?: {
  project_id?: string;
  section_id?: string;
  parent_task_id?: string;
  is_completed?: boolean;
  inbox?: boolean;
  limit?: number;
  offset?: number;
}) {
  return apiFetchUrl<PaginatedResponse<Task>>(buildUrl("/api/v1/tasks", params));
}

export function createTask(body: TaskCreate) {
  return apiFetch<Task>("/api/v1/tasks", { method: "POST", body: JSON.stringify(body) });
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

export { API_URL };
