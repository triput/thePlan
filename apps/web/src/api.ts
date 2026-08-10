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
  color_hex: string;
  is_archived: boolean;
}

export interface Task {
  id: string;
  title: string;
  priority: string;
  is_completed: boolean;
  project_id: string | null;
}

async function apiFetch<T>(path: string): Promise<T> {
  const response = await fetch(`${API_URL}${path}`);
  if (!response.ok) {
    throw new Error(`${response.status} ${response.statusText}`);
  }
  return response.json() as Promise<T>;
}

export function fetchHealth() {
  return apiFetch<{ status: string }>("/health");
}

export function fetchMe() {
  return apiFetch<User>("/api/v1/auth/me");
}

export function fetchEpics() {
  return apiFetch<PaginatedResponse<Epic>>("/api/v1/epics");
}

export function fetchTasks() {
  return apiFetch<PaginatedResponse<Task>>("/api/v1/tasks");
}

export { API_URL };
