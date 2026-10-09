/** Empty = same-origin (Vite proxy / Compose nginx). Absolute URL only for special cases. */
const API_URL = import.meta.env.VITE_API_URL ?? "";

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}

export interface User {
  id: string;
  username: string | null;
  email: string;
  display_name: string | null;
  is_admin: boolean;
  must_change_password: boolean;
}

export interface AuthUserAdmin {
  id: string;
  username: string | null;
  email: string;
  display_name: string | null;
  is_admin: boolean;
  is_disabled: boolean;
  must_change_password: boolean;
}

export interface AuthRegisterBody {
  username: string;
  email: string;
  password: string;
  display_name?: string | null;
}

export interface AuthLoginBody {
  identifier: string;
  password: string;
}

export interface AuthUserCreateBody {
  username: string;
  email: string;
  password: string;
  display_name?: string | null;
  is_admin?: boolean;
}

export interface AuthUserUpdateBody {
  display_name?: string | null;
  email?: string;
  is_disabled?: boolean;
  password?: string;
  must_change_password?: boolean;
}

export interface AuthMeUpdateBody {
  password?: string;
  email?: string;
  display_name?: string | null;
}

export interface SourceRef {
  system: string;
  id: string;
  url?: string | null;
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
  preferred_time_window_id: string | null;
  schedule_style: ScheduleStyle | null;
  source_refs?: SourceRef[] | null;
}

export interface Project {
  id: string;
  title: string;
  description: string | null;
  epic_id: string | null;
  color_hex: string;
  sort_order: number;
  is_archived: boolean;
  preferred_time_window_id: string | null;
  schedule_style: ScheduleStyle | null;
  source_refs?: SourceRef[] | null;
}

export interface Section {
  id: string;
  project_id: string;
  title: string;
  sort_order: number;
}

export type TaskPriority = "p1" | "p2" | "p3" | "p4";

export type TaskWorkflowState = "ready" | "in_progress" | "waiting";

export type TaskBoardColumnId = "ready" | "in_progress" | "waiting" | "done";

export interface Label {
  id: string;
  name: string;
  color_hex: string;
  task_count?: number;
}

export interface Recurrence {
  rrule: string;
  is_fixed: boolean;
  timezone: string;
  starts_on: string | null;
  ends_on: string | null;
  display: string;
}

export interface RecurrenceUpsert {
  rrule?: string;
  is_fixed?: boolean;
  timezone?: string;
  starts_on?: string | null;
  ends_on?: string | null;
  text?: string;
}

export type ReminderChannel = "in_app" | "browser";

export interface Reminder {
  id: string;
  task_id: string;
  fire_at: string;
  channel: ReminderChannel;
  is_fired: boolean;
  created_at: string;
}

export interface ReminderDue extends Reminder {
  task_title: string;
}

export interface ReminderCreate {
  fire_at: string;
  channel?: ReminderChannel;
}

export interface ReminderUpdate {
  fire_at?: string;
  channel?: ReminderChannel;
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
  plan_id: string | null;
  plan_name?: string | null;
  schedule_style: ScheduleStyle | null;
  source_refs?: SourceRef[] | null;
  estimated_duration_minutes: number;
  preferred_time_window_id: string | null;
  is_completed: boolean;
  completed_at: string | null;
  deleted_at?: string | null;
  status: string;
  sort_order: number;
  label_ids: string[];
  open_subtask_count: number;
  workflow_state: TaskWorkflowState;
  board_column: TaskBoardColumnId;
  waiting_note: string | null;
  board_rank: number;
  board_revision: number;
  recurrence?: Recurrence | null;
  recurrence_advanced?: boolean;
  previous_due_at?: string | null;
}

export interface TaskWorkflowTransition {
  column: TaskBoardColumnId;
  expected_revision: number;
  waiting_note?: string | null;
  board_rank?: number;
  insert_before_id?: string;
  insert_after_id?: string;
  bulk_children?: boolean;
  force_parent_only?: boolean;
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
  preferred_time_window_id?: string | null;
  schedule_style?: ScheduleStyle | null;
}

export interface EpicUpdate {
  title?: string;
  description?: string | null;
  color_hex?: string;
  preferred_time_window_id?: string | null;
  schedule_style?: ScheduleStyle | null;
}

export interface ProjectCreate {
  title: string;
  description?: string | null;
  epic_id?: string | null;
  color_hex?: string;
  preferred_time_window_id?: string | null;
  schedule_style?: ScheduleStyle | null;
}

export interface ProjectUpdate {
  title?: string;
  description?: string | null;
  epic_id?: string | null;
  color_hex?: string;
  preferred_time_window_id?: string | null;
  schedule_style?: ScheduleStyle | null;
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
  deadline_at?: string | null;
  soft_target_at?: string | null;
  plan_id?: string | null;
  schedule_style?: ScheduleStyle | null;
  estimated_duration_minutes?: number;
  preferred_time_window_id?: string | null;
  label_ids?: string[];
  recurrence?: RecurrenceUpsert | null;
}

export interface TaskUpdate {
  title?: string;
  description?: string | null;
  project_id?: string | null;
  section_id?: string | null;
  parent_task_id?: string | null;
  priority?: TaskPriority;
  due_at?: string | null;
  deadline_at?: string | null;
  soft_target_at?: string | null;
  plan_id?: string | null;
  schedule_style?: ScheduleStyle | null;
  estimated_duration_minutes?: number;
  preferred_time_window_id?: string | null;
  label_ids?: string[];
}

export interface Plan {
  id: string;
  name: string;
  soft_target_at: string | null;
  created_at?: string;
  updated_at?: string;
}

export interface PlanCreate {
  name: string;
  soft_target_at?: string | null;
}

export interface PlanUpdate {
  name?: string;
  soft_target_at?: string | null;
}

export type ScheduleStyle = "standalone" | "time_block" | "bundle" | "manual";

export interface UserSettings {
  timezone: string;
  locale: string;
  workday_minutes: number;
  workday_start_local: string;
  workweek_days: number;
  inter_block_buffer_minutes: number;
  upcoming_horizon_days: number;
  default_estimated_duration_minutes: number;
  default_min_block_duration_minutes: number;
  default_schedule_style: ScheduleStyle;
  auto_defer_enabled: boolean;
  max_auto_schedule_minutes_per_project_per_day: number | null;
  ups_weights?: Record<string, unknown>;
  id?: string;
  owner_id?: string;
  created_at?: string;
  updated_at?: string;
}

export type UserSettingsUpdate = Partial<
  Pick<
    UserSettings,
    | "timezone"
    | "locale"
    | "workday_minutes"
    | "workday_start_local"
    | "workweek_days"
    | "inter_block_buffer_minutes"
    | "upcoming_horizon_days"
    | "default_estimated_duration_minutes"
    | "default_min_block_duration_minutes"
    | "default_schedule_style"
    | "auto_defer_enabled"
    | "max_auto_schedule_minutes_per_project_per_day"
  >
>;

export type TimeMapBandTier = "green" | "yellow" | "red";

export interface TimeMapBand {
  id?: string;
  tier: TimeMapBandTier;
  start_time: string;
  end_time: string;
  days_of_week: number;
  sort_order: number;
}

export interface FocusWindow {
  id: string;
  name: string;
  strict_mode: boolean;
  bands: TimeMapBand[];
  created_at: string;
  updated_at: string;
}

export interface FocusWindowCreate {
  name: string;
  strict_mode?: boolean;
  bands: TimeMapBand[];
}

export interface FocusWindowUpdate {
  name?: string;
  strict_mode?: boolean;
  bands?: TimeMapBand[];
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

export interface BundleMeta {
  kind: "bundle";
  member_task_ids: string[];
  source: "selection" | "parent_subtree";
}

export interface ScheduledBlock {
  id: string;
  task_id: string;
  start_time: string;
  end_time: string;
  is_pinned: boolean;
  created_at: string;
  updated_at: string;
  bundle_meta?: BundleMeta | null;
  bundle_inactive?: boolean;
}

export interface ScheduledBlockCreate {
  task_id: string;
  start_time: string;
  end_time: string;
  is_pinned?: boolean;
}

export interface ScheduledBlockBundleCreate {
  start_time: string;
  end_time?: string | null;
  is_pinned?: boolean;
  member_task_ids?: string[];
  parent_task_id?: string;
}

export interface ScheduledBlockUpdate {
  task_id?: string;
  start_time?: string;
  end_time?: string;
  is_pinned?: boolean;
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
  recurrence: Recurrence | null;
}

type QueryParams = Record<string, string | number | boolean | undefined | null>;

function buildUrl(path: string, params?: QueryParams): string {
  const url = API_URL
    ? new URL(`${API_URL.replace(/\/$/, "")}${path}`)
    : new URL(path, typeof window !== "undefined" ? window.location.origin : "http://127.0.0.1");
  if (params) {
    for (const [key, value] of Object.entries(params)) {
      if (value !== undefined && value !== null) {
        url.searchParams.set(key, String(value));
      }
    }
  }
  if (!API_URL) {
    return `${url.pathname}${url.search}`;
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
    credentials: "include",
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...init?.headers,
    },
  });
  if (init?.signal?.aborted) {
    throw new DOMException("The operation was aborted.", "AbortError");
  }
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
    credentials: "include",
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

export function fetchMe(signal?: AbortSignal) {
  return apiFetch<User>("/api/v1/auth/me", signal ? { signal } : undefined);
}

export function updateMe(body: AuthMeUpdateBody) {
  return apiFetch<User>("/api/v1/auth/me", {
    method: "PATCH",
    body: JSON.stringify(body),
  });
}

export function register(body: AuthRegisterBody) {
  return apiFetch<User>("/api/v1/auth/register", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function login(body: AuthLoginBody) {
  return apiFetch<User>("/api/v1/auth/login", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function logout() {
  return apiFetch<void>("/api/v1/auth/logout", { method: "POST" });
}

export function fetchUsers() {
  return apiFetch<AuthUserAdmin[]>("/api/v1/auth/users");
}

export function createUser(body: AuthUserCreateBody) {
  return apiFetch<AuthUserAdmin>("/api/v1/auth/users", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function updateUser(userId: string, body: AuthUserUpdateBody) {
  return apiFetch<AuthUserAdmin>(`/api/v1/auth/users/${userId}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
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

export function unarchiveEpic(epicId: string) {
  return apiFetch<Epic>(`/api/v1/epics/${epicId}/unarchive`, { method: "POST" });
}

export interface EpicDemoteToProjectBody {
  target_epic_id?: string | null;
}

export interface EpicDemoteToProjectResult {
  project: Project;
  orphaned_project_ids: string[];
}

/** DEF-023: fold epic into a new project; former child projects become standalone. */
export function demoteEpicToProject(epicId: string, body?: EpicDemoteToProjectBody) {
  return apiFetch<EpicDemoteToProjectResult>(`/api/v1/epics/${epicId}/demote-to-project`, {
    method: "POST",
    body: JSON.stringify(body ?? {}),
  });
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

export function unarchiveProject(projectId: string) {
  return apiFetch<Project>(`/api/v1/projects/${projectId}/unarchive`, { method: "POST" });
}

export interface ProjectPromoteToEpicResult {
  epic: Epic;
  project: Project;
}

/** DEF-023: create epic from project meta; keep project UUID under the new epic. */
export function promoteProjectToEpic(projectId: string) {
  return apiFetch<ProjectPromoteToEpicResult>(`/api/v1/projects/${projectId}/promote-to-epic`, {
    method: "POST",
  });
}

export interface TaskPromoteToProjectBody {
  include_descendants?: boolean;
  epic_id?: string | null;
}

export interface TaskPromoteToProjectResult {
  project: Project;
  task: Task;
}

/** DEF-023: create a project from a task; move task (+ descendants by default) into it. */
export function promoteTaskToProject(taskId: string, body?: TaskPromoteToProjectBody) {
  return apiFetch<TaskPromoteToProjectResult>(`/api/v1/tasks/${taskId}/promote-to-project`, {
    method: "POST",
    body: JSON.stringify(body ?? { include_descendants: true }),
  });
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

export interface SearchTask extends Task {
  project_title: string | null;
  labels: { id: string; name: string; color_hex: string }[];
}

export function searchTasks(q: string, limit?: number) {
  return apiFetchUrl<PaginatedResponse<SearchTask>>(
    buildUrl("/api/v1/search", { q, limit }),
  );
}

export function fetchTask(taskId: string) {
  return apiFetch<Task>(`/api/v1/tasks/${taskId}`);
}

export function fetchTasks(params?: {
  project_id?: string;
  section_id?: string;
  parent_task_id?: string;
  label_id?: string;
  epic_id?: string;
  is_completed?: boolean;
  inbox?: boolean;
  trashed?: boolean;
  workflow?: TaskBoardColumnId;
  board_order?: boolean;
  due_from?: string;
  due_to?: string;
  ids?: string[];
  limit?: number;
  offset?: number;
}) {
  const { ids, ...rest } = params ?? {};
  const url = API_URL
    ? new URL(`${API_URL.replace(/\/$/, "")}/api/v1/tasks`)
    : new URL("/api/v1/tasks", typeof window !== "undefined" ? window.location.origin : "http://127.0.0.1");
  for (const [key, value] of Object.entries(rest)) {
    if (value !== undefined && value !== null) {
      url.searchParams.set(key, String(value));
    }
  }
  if (ids) {
    for (const id of ids) {
      url.searchParams.append("ids", id);
    }
  }
  const path = API_URL ? url.toString() : `${url.pathname}${url.search}`;
  return apiFetchUrl<PaginatedResponse<Task>>(path);
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
      credentials: "include",
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

export function deleteLabel(labelId: string, body?: { reassign_to?: string[] }) {
  return apiFetch<void>(`/api/v1/labels/${labelId}`, {
    method: "DELETE",
    body: JSON.stringify(body ?? {}),
  });
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

export interface TaskBatchUpdateBody {
  task_ids: string[];
  patch?: TaskUpdate;
  add_label_ids?: string[];
}

export interface TaskBatchUpdateResponse {
  items: Task[];
}

export function batchUpdateTasks(body: TaskBatchUpdateBody) {
  return apiFetch<TaskBatchUpdateResponse>("/api/v1/tasks/batch", {
    method: "PATCH",
    body: JSON.stringify(body),
  });
}

export function deleteTask(taskId: string) {
  return apiFetch<void>(`/api/v1/tasks/${taskId}`, { method: "DELETE" });
}

export function restoreTask(taskId: string) {
  return apiFetch<Task>(`/api/v1/tasks/${taskId}/restore`, { method: "POST" });
}

export function emptyTrash(params?: { older_than_days?: number }) {
  return apiFetchUrl<void>(buildUrl("/api/v1/tasks/trash", params), {
    method: "DELETE",
  });
}

export function hardPurgeTask(taskId: string) {
  return apiFetch<void>(`/api/v1/tasks/${taskId}?hard=true`, { method: "DELETE" });
}

export function transitionTaskWorkflow(taskId: string, body: TaskWorkflowTransition) {
  return apiFetch<Task>(`/api/v1/tasks/${taskId}/workflow`, {
    method: "POST",
    body: JSON.stringify(body),
  });
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

export function putTaskRecurrence(taskId: string, body: RecurrenceUpsert) {
  return apiFetch<Recurrence>(`/api/v1/tasks/${taskId}/recurrence`, {
    method: "PUT",
    body: JSON.stringify(body),
  });
}

export function deleteTaskRecurrence(taskId: string) {
  return apiFetch<void>(`/api/v1/tasks/${taskId}/recurrence`, { method: "DELETE" });
}

export function fetchTaskReminders(taskId: string) {
  return apiFetch<Reminder[]>(`/api/v1/tasks/${taskId}/reminders`);
}

export function createTaskReminder(taskId: string, body: ReminderCreate) {
  return apiFetch<Reminder>(`/api/v1/tasks/${taskId}/reminders`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function updateReminder(reminderId: string, body: ReminderUpdate) {
  return apiFetch<Reminder>(`/api/v1/reminders/${reminderId}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
}

export function deleteReminder(reminderId: string) {
  return apiFetch<void>(`/api/v1/reminders/${reminderId}`, { method: "DELETE" });
}

export function fetchDueReminders() {
  return apiFetch<ReminderDue[]>("/api/v1/reminders/due");
}

export function ackReminder(reminderId: string) {
  return apiFetch<Reminder>(`/api/v1/reminders/${reminderId}/ack`, { method: "POST" });
}

export function parseQuickAdd(text: string) {
  return apiFetch<QuickAddParseResponse>("/api/v1/quick-add/parse", {
    method: "POST",
    body: JSON.stringify({ text }),
  });
}

export type AssistActionType = "create_task" | "create_project";

export interface AssistCreateTaskAction {
  type: "create_task";
  title: string;
  description?: string | null;
  project_name?: string | null;
  section_name?: string | null;
  priority?: TaskPriority | null;
  due_at?: string | null;
  label_names?: string[];
  estimated_duration_minutes?: number | null;
}

export interface AssistCreateProjectAction {
  type: "create_project";
  title: string;
  description?: string | null;
  epic_name?: string | null;
  epic_id?: string | null;
  color_hex?: string | null;
}

export type AssistAction = AssistCreateTaskAction | AssistCreateProjectAction;

export interface AssistProposeResponse {
  actions: AssistAction[];
  model: string;
}

export interface AssistApplyResultItem {
  ok: boolean;
  action_type: string;
  title?: string | null;
  task_id?: string | null;
  project_id?: string | null;
  error?: string | null;
  created_labels: string[];
}

export interface AssistApplyResponse {
  results: AssistApplyResultItem[];
}

export interface AssistStatus {
  reachable: boolean;
  base_url: string;
  model: string;
  detail?: string | null;
  enabled: boolean;
}

export function fetchAssistStatus() {
  return apiFetch<AssistStatus>("/api/v1/assist/status");
}

export function proposeAssist(text: string) {
  return apiFetch<AssistProposeResponse>("/api/v1/assist/propose", {
    method: "POST",
    body: JSON.stringify({ text }),
  });
}

export function applyAssist(actions: AssistAction[]) {
  return apiFetch<AssistApplyResponse>("/api/v1/assist/apply", {
    method: "POST",
    body: JSON.stringify({ actions }),
  });
}

export type OutlineActionType =
  | "create_epic"
  | "create_project"
  | "create_section"
  | "create_task";

export interface OutlineCreateEpicAction {
  type: "create_epic";
  key: string;
  title: string;
  description?: string | null;
  sort_order: number;
}

export interface OutlineCreateProjectAction {
  type: "create_project";
  key: string;
  title: string;
  description?: string | null;
  sort_order: number;
  epic_key?: string | null;
  epic_id?: string | null;
}

export interface OutlineCreateSectionAction {
  type: "create_section";
  key: string;
  title: string;
  description?: string | null;
  sort_order: number;
  project_key?: string | null;
  project_id?: string | null;
}

export interface OutlineCreateTaskAction {
  type: "create_task";
  key: string;
  title: string;
  description?: string | null;
  sort_order: number;
  project_key?: string | null;
  project_id?: string | null;
  section_key?: string | null;
  section_id?: string | null;
  label_names: string[];
  estimated_duration_minutes?: number | null;
  optional: boolean;
  outline_id?: string | null;
}

export type OutlineAction =
  | OutlineCreateEpicAction
  | OutlineCreateProjectAction
  | OutlineCreateSectionAction
  | OutlineCreateTaskAction;

export interface OutlineProposeSummary {
  epic_count: number;
  project_count: number;
  section_count: number;
  task_count: number;
  optional_skipped: number;
}

export type OutlineTemplateId = "coursera_specialization" | "hierarchy_v1";

export type OutlineAttachKind = "epic" | "project" | "section";

export interface OutlineAttachUnder {
  kind: OutlineAttachKind;
  id: string;
}

export interface OutlineProposeResponse {
  actions: OutlineAction[];
  template_id: string;
  summary: OutlineProposeSummary;
}

export interface OutlineApplyResultItem {
  ok: boolean;
  action_type: string;
  title?: string | null;
  key?: string | null;
  entity_id?: string | null;
  error?: string | null;
  created_labels: string[];
}

export interface OutlineApplyResponse {
  results: OutlineApplyResultItem[];
}

export function proposeOutline(body: {
  template_id: string;
  outline: Record<string, unknown>;
  skip_optional?: boolean;
  attach_under?: OutlineAttachUnder | null;
}) {
  return apiFetch<OutlineProposeResponse>("/api/v1/outlines/propose", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function applyOutline(actions: OutlineAction[]) {
  return apiFetch<OutlineApplyResponse>("/api/v1/outlines/apply", {
    method: "POST",
    body: JSON.stringify({ actions }),
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

export function fetchScheduledBlocks(params: { start: string; end: string }) {
  return apiFetchUrl<PaginatedResponse<ScheduledBlock>>(
    buildUrl("/api/v1/scheduled-blocks", params),
  );
}

export function fetchScheduledBlock(blockId: string) {
  return apiFetch<ScheduledBlock>(`/api/v1/scheduled-blocks/${blockId}`);
}

export function createScheduledBlock(body: ScheduledBlockCreate) {
  return apiFetch<ScheduledBlock>("/api/v1/scheduled-blocks", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function createScheduledBlockBundle(body: ScheduledBlockBundleCreate) {
  return apiFetch<ScheduledBlock>("/api/v1/scheduled-blocks/bundle", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function updateScheduledBlock(blockId: string, body: ScheduledBlockUpdate) {
  return apiFetch<ScheduledBlock>(`/api/v1/scheduled-blocks/${blockId}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
}

export function deleteScheduledBlock(blockId: string) {
  return apiFetch<void>(`/api/v1/scheduled-blocks/${blockId}`, { method: "DELETE" });
}

export interface ReleaseRemainderOut {
  block: ScheduledBlock | null;
  deleted: boolean;
}

export function releaseScheduledBlockRemainder(blockId: string, at?: string) {
  return apiFetch<ReleaseRemainderOut>(`/api/v1/scheduled-blocks/${blockId}/release-remainder`, {
    method: "POST",
    body: JSON.stringify(at ? { at } : {}),
  });
}

export interface ClearUnpinnedBlocksOut {
  deleted_count: number;
}

export function clearUnpinnedScheduledBlocks(body: { start: string; end: string }) {
  return apiFetch<ClearUnpinnedBlocksOut>("/api/v1/scheduled-blocks/clear-unpinned", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function fetchSettings() {
  return apiFetch<UserSettings>("/api/v1/settings");
}

export function updateSettings(patch: UserSettingsUpdate) {
  return apiFetch<UserSettings>("/api/v1/settings", {
    method: "PATCH",
    body: JSON.stringify(patch),
  });
}

export function fetchFocusWindows() {
  return apiFetch<FocusWindow[]>("/api/v1/focus-windows");
}

export function createFocusWindow(body: FocusWindowCreate) {
  return apiFetch<FocusWindow>("/api/v1/focus-windows", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function updateFocusWindow(windowId: string, body: FocusWindowUpdate) {
  return apiFetch<FocusWindow>(`/api/v1/focus-windows/${windowId}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
}

export function deleteFocusWindow(windowId: string) {
  return apiFetch<void>(`/api/v1/focus-windows/${windowId}`, { method: "DELETE" });
}

export function fetchPlans() {
  return apiFetch<Plan[]>("/api/v1/plans");
}

export function createPlan(body: PlanCreate) {
  return apiFetch<Plan>("/api/v1/plans", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function updatePlan(planId: string, body: PlanUpdate) {
  return apiFetch<Plan>(`/api/v1/plans/${planId}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
}

export function deletePlan(planId: string) {
  return apiFetch<void>(`/api/v1/plans/${planId}`, { method: "DELETE" });
}

export interface CalendarAccount {
  id: string;
  provider: string;
  account_email: string | null;
  is_enabled: boolean;
  mirror_blocks: boolean;
  sync_cursor: string | null;
  last_synced_at: string | null;
  token_expires_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface GoogleCalendarListItem {
  id: string;
  summary: string | null;
  primary: boolean;
  access_role: string | null;
}

export type CalendarSubscriptionRole = "primary" | "informational";

export interface CalendarSubscription {
  id: string;
  calendar_account_id: string;
  external_calendar_id: string;
  summary: string | null;
  role: CalendarSubscriptionRole;
  is_enabled: boolean;
  sync_cursor: string | null;
}

export interface CalendarSubscriptionPutItem {
  external_calendar_id: string;
  summary?: string | null;
  role: CalendarSubscriptionRole;
  is_enabled: boolean;
}

export interface CalendarAccountUpdate {
  mirror_blocks?: boolean;
  is_enabled?: boolean;
}

export interface ExternalCalendarEvent {
  id: string;
  calendar_account_id: string;
  provider: string;
  external_event_id: string;
  calendar_id: string;
  title: string | null;
  start_time: string;
  end_time: string;
  is_all_day: boolean;
  last_synced_at: string;
}

export type CalendarConflictKind = "block_busy" | "block_block";

export interface CalendarConflict {
  kind: CalendarConflictKind;
  block_id: string;
  other_block_id: string | null;
  external_event_id: string | null;
  external_title: string | null;
  start_time: string;
  end_time: string;
  is_pinned: boolean;
}

export interface CalendarConflictsResult {
  items: CalendarConflict[];
  count: number;
}

export function fetchCalendarAccounts() {
  return apiFetchUrl<PaginatedResponse<CalendarAccount>>(buildUrl("/api/v1/calendar/accounts"));
}

export function updateCalendarAccount(accountId: string, body: CalendarAccountUpdate) {
  return apiFetch<CalendarAccount>(`/api/v1/calendar/accounts/${accountId}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
}

export function fetchGoogleCalendars(accountId: string) {
  return apiFetchUrl<PaginatedResponse<GoogleCalendarListItem>>(
    buildUrl("/api/v1/calendar/calendars", { account_id: accountId }),
  );
}

export function fetchCalendarSubscriptions(accountId: string) {
  return apiFetchUrl<PaginatedResponse<CalendarSubscription>>(
    buildUrl(`/api/v1/calendar/accounts/${accountId}/subscriptions`),
  );
}

export function putCalendarSubscriptions(accountId: string, items: CalendarSubscriptionPutItem[]) {
  return apiFetchUrl<PaginatedResponse<CalendarSubscription>>(
    buildUrl(`/api/v1/calendar/accounts/${accountId}/subscriptions`),
    { method: "PUT", body: JSON.stringify({ items }) },
  );
}

export function disconnectCalendarAccount(accountId: string) {
  return apiFetch<void>(`/api/v1/calendar/accounts/${accountId}`, { method: "DELETE" });
}

export function syncCalendarAccount(
  accountId: string,
  params?: { start?: string; end?: string },
) {
  return apiFetchUrl<{ account_id: string; upserted: number }>(
    buildUrl(`/api/v1/calendar/accounts/${accountId}/sync`, params),
    { method: "POST", body: "{}" },
  );
}

export function fetchExternalCalendarEvents(params: { start: string; end: string }) {
  return apiFetchUrl<PaginatedResponse<ExternalCalendarEvent>>(
    buildUrl("/api/v1/calendar/events", params),
  );
}

export function fetchCalendarConflicts(params: { start: string; end: string }) {
  return apiFetchUrl<CalendarConflictsResult>(buildUrl("/api/v1/calendar/conflicts", params));
}

export type ScheduleRunStatus = "running" | "completed" | "failed";

export interface ScheduleRunOut {
  id: string;
  status: ScheduleRunStatus;
  started_at: string;
  finished_at: string | null;
  tasks_scheduled: number;
  blocks_created: number;
  overbooked_count: number;
  error_message: string | null;
  stats_json: Record<string, unknown> | null;
}

export function postScheduleReplan() {
  return apiFetch<ScheduleRunOut>("/api/v1/schedule/replan", {
    method: "POST",
    body: "{}",
  });
}

export function fetchScheduleRun(id: string) {
  return apiFetch<ScheduleRunOut>(`/api/v1/schedule/runs/${id}`);
}

export function fetchScheduleRuns(params?: { limit?: number; offset?: number }) {
  return apiFetchUrl<PaginatedResponse<ScheduleRunOut>>(
    buildUrl("/api/v1/schedule/runs", params),
  );
}

export type StaleCategory =
  | "duration"
  | "deadline"
  | "map_style"
  | "deps"
  | "pins"
  | "project_daily_cap"
  | "timezone_horizon_workweek"
  | "lifecycle"
  | "busy_external"
  | "prerequisite_state"
  | "due_at_soft_target"
  | "provenance";
export type ScheduleEvaluationState = "evaluated" | "never_evaluated";

export interface ReasonFactOut {
  code: string;
  params: Record<string, unknown>;
}

export interface ScheduleExplanationOut {
  id: string;
  schedule_run_id: string;
  task_id: string;
  evaluated_at: string;
  outcome: string;
  primary_reason_code: string;
  requested_minutes: number;
  pinned_minutes: number;
  placed_minutes: number;
  remaining_minutes: number;
  reason_facts: ReasonFactOut[];
  summary_text: string;
  placement_facts: Record<string, unknown> | null;
  algorithm_version: string | null;
  input_fingerprint: string | null;
  input_snapshot: Record<string, unknown> | null;
  is_stale: boolean;
  stale_categories: StaleCategory[];
}

export interface TaskScheduleExplanationOut {
  task_id: string;
  evaluation_state: ScheduleEvaluationState;
  summary_text: string;
  is_stale: boolean;
  stale_categories: StaleCategory[];
  explanation: ScheduleExplanationOut | null;
}

export function fetchTaskScheduleExplanation(taskId: string) {
  return apiFetch<TaskScheduleExplanationOut>(`/api/v1/tasks/${taskId}/schedule-explanation`);
}

export function fetchScheduleRunExplanations(
  runId: string,
  params?: { task_id?: string; limit?: number; offset?: number },
) {
  return apiFetchUrl<{
    items: ScheduleExplanationOut[];
    total: number;
    limit: number;
    offset: number;
  }>(buildUrl(`/api/v1/schedule/runs/${runId}/explanations`, params));
}

/** Full-page navigation so session cookie rides the OAuth round-trip. */
export function googleCalendarConnectHref(): string {
  const base = API_URL.replace(/\/$/, "");
  return `${base}/api/v1/calendar/oauth/google/start`;
}

/** Full-page navigation so session cookie rides the OAuth round-trip. */
export function microsoftCalendarConnectHref(): string {
  const base = API_URL.replace(/\/$/, "");
  return `${base}/api/v1/calendar/oauth/microsoft/start`;
}

export { API_URL };
