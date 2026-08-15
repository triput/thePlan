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
  estimated_duration_minutes: number;
  preferred_time_window_id: string | null;
  is_completed: boolean;
  completed_at: string | null;
  status: string;
  sort_order: number;
  label_ids: string[];
  open_subtask_count: number;
  recurrence?: Recurrence | null;
  recurrence_advanced?: boolean;
  previous_due_at?: string | null;
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

export type ScheduleStyle = "standalone" | "time_block" | "bundle";

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

export interface ScheduledBlock {
  id: string;
  task_id: string;
  start_time: string;
  end_time: string;
  is_pinned: boolean;
  created_at: string;
  updated_at: string;
}

export interface ScheduledBlockCreate {
  task_id: string;
  start_time: string;
  end_time: string;
  is_pinned?: boolean;
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
  due_from?: string;
  due_to?: string;
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

export type AssistActionType = "create_task";

export interface AssistCreateTaskAction {
  type: AssistActionType;
  title: string;
  description?: string | null;
  project_name?: string | null;
  section_name?: string | null;
  priority?: TaskPriority | null;
  due_at?: string | null;
  label_names?: string[];
  estimated_duration_minutes?: number | null;
}

export interface AssistProposeResponse {
  actions: AssistCreateTaskAction[];
  model: string;
}

export interface AssistApplyResultItem {
  ok: boolean;
  action_type: string;
  title?: string | null;
  task_id?: string | null;
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

export function applyAssist(actions: AssistCreateTaskAction[]) {
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
  epic_key: string;
}

export interface OutlineCreateSectionAction {
  type: "create_section";
  key: string;
  title: string;
  description?: string | null;
  sort_order: number;
  project_key: string;
}

export interface OutlineCreateTaskAction {
  type: "create_task";
  key: string;
  title: string;
  description?: string | null;
  sort_order: number;
  project_key: string;
  section_key?: string | null;
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

export function updateScheduledBlock(blockId: string, body: ScheduledBlockUpdate) {
  return apiFetch<ScheduledBlock>(`/api/v1/scheduled-blocks/${blockId}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
}

export function deleteScheduledBlock(blockId: string) {
  return apiFetch<void>(`/api/v1/scheduled-blocks/${blockId}`, { method: "DELETE" });
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
