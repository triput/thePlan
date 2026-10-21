import { describe, it } from "node:test";
import assert from "node:assert/strict";
import type { Task } from "../src/api.ts";
import {
  buildDatesOnlyUpdateFromDraft,
  buildTaskUpdateFromDraft,
  isOccurrenceDatesDirty,
  isTaskDraftDirty,
  shouldResetTaskDetailDraft,
  TASK_TITLE_MAX_LENGTH,
  taskToDraft,
  validateOccurrenceDatesForSave,
  validateTaskDraftForSave,
} from "../src/taskDetailDraft.ts";

const baseTask = {
  id: "t1",
  title: "Write tests",
  description: null,
  priority: "p3",
  due_at: null,
  soft_target_at: null,
  deadline_at: null,
  start_no_earlier_at: null,
  start_no_later_at: null,
  estimated_duration_minutes: 60,
  project_id: null,
  section_id: null,
  parent_task_id: null,
  label_ids: [],
  preferred_time_window_id: null,
  schedule_style: null,
  plan_id: null,
} as Task;

describe("taskDetailDraft", () => {
  it("detects title edits", () => {
    const draft = taskToDraft(baseTask);
    draft.title = "Changed";
    assert.equal(isTaskDraftDirty(baseTask, draft), true);
  });

  it("fresh draft from task is clean", () => {
    const draft = taskToDraft(baseTask);
    assert.equal(isTaskDraftDirty(baseTask, draft), false);
  });

  it("treats label id reorder as clean (order-insensitive compare)", () => {
    const withLabels = { ...baseTask, label_ids: ["a", "b"] } as Task;
    const draft = taskToDraft(withLabels);
    draft.labelIds = ["b", "a"];
    assert.equal(isTaskDraftDirty(withLabels, draft), false);
  });

  it("shouldResetTaskDetailDraft only on task identity change", () => {
    assert.equal(shouldResetTaskDetailDraft(null, baseTask), true);
    assert.equal(shouldResetTaskDetailDraft("t1", baseTask), false);
    assert.equal(shouldResetTaskDetailDraft("t1", { ...baseTask, title: "Rollback" } as Task), false);
    assert.equal(shouldResetTaskDetailDraft("t1", { ...baseTask, id: "t2" } as Task), true);
    assert.equal(shouldResetTaskDetailDraft("t1", null), true);
    assert.equal(shouldResetTaskDetailDraft(null, null), false);
  });

  it("rejects overlong titles before save", () => {
    const draft = taskToDraft(baseTask);
    draft.title = "x".repeat(TASK_TITLE_MAX_LENGTH + 1);
    assert.match(validateTaskDraftForSave(draft) ?? "", /500/);
  });

  it("rejects invalid datetime-local values instead of silent null", () => {
    const draft = taskToDraft(baseTask);
    draft.deadlineAtLocal = "not-a-datetime";
    assert.match(validateTaskDraftForSave(draft) ?? "", /Deadline is invalid/);
    assert.equal(buildTaskUpdateFromDraft(baseTask, draft), null);
  });

  it("omits unchanged occurrence bounds from PATCH", () => {
    const withBounds = {
      ...baseTask,
      start_no_earlier_at: "2026-10-21T15:00:00.000Z",
      start_no_later_at: "2026-10-21T17:00:00.000Z",
    } as Task;
    const draft = taskToDraft(withBounds);
    const body = buildTaskUpdateFromDraft(withBounds, draft);
    assert.ok(body);
    assert.equal("start_no_earlier_at" in body!, false);
    assert.equal("start_no_later_at" in body!, false);
  });

  it("preserves deadline second precision on unrelated saves (omit unchanged)", () => {
    const withDeadline = {
      ...baseTask,
      deadline_at: "2026-10-21T15:00:45.123Z",
    } as Task;
    const draft = taskToDraft(withDeadline);
    draft.title = "Title only edit";
    const body = buildTaskUpdateFromDraft(withDeadline, draft);
    assert.ok(body);
    assert.equal(body!.title, "Title only edit");
    assert.equal("deadline_at" in body!, false);
  });

  it("sends null when deadline is cleared", () => {
    const withDeadline = {
      ...baseTask,
      deadline_at: "2026-10-21T15:00:45.123Z",
    } as Task;
    const draft = taskToDraft(withDeadline);
    draft.deadlineAtLocal = "";
    const body = buildTaskUpdateFromDraft(withDeadline, draft);
    assert.ok(body);
    assert.equal(body!.deadline_at, null);
  });

  it("sends null when occurrence bound is cleared", () => {
    const withBounds = {
      ...baseTask,
      start_no_earlier_at: "2026-10-21T15:00:00.000Z",
    } as Task;
    const draft = taskToDraft(withBounds);
    draft.startNoEarlierAtLocal = "";
    const body = buildTaskUpdateFromDraft(withBounds, draft);
    assert.ok(body);
    assert.equal(body!.start_no_earlier_at, null);
  });

  it("detects start window edits as dirty", () => {
    const draft = taskToDraft(baseTask);
    draft.startNoLaterAtLocal = "2026-10-22T12:00";
    assert.equal(isTaskDraftDirty(baseTask, draft), true);
    assert.equal(isOccurrenceDatesDirty(baseTask, draft), true);
  });

  it("isOccurrenceDatesDirty ignores title/priority/project edits", () => {
    const draft = taskToDraft(baseTask);
    draft.title = "Other edit";
    draft.priority = "p1";
    draft.projectId = "proj-1";
    assert.equal(isTaskDraftDirty(baseTask, draft), true);
    assert.equal(isOccurrenceDatesDirty(baseTask, draft), false);
  });

  it("buildDatesOnlyUpdateFromDraft sends only date fields", () => {
    const withDates = {
      ...baseTask,
      deadline_at: "2026-10-21T15:00:45.123Z",
      start_no_earlier_at: "2026-10-21T14:00:00.000Z",
    } as Task;
    const draft = taskToDraft(withDates);
    draft.title = "Should not PATCH";
    draft.priority = "p1";
    draft.deadlineAtLocal = "";
    draft.startNoLaterAtLocal = "2026-10-22T12:00";
    const body = buildDatesOnlyUpdateFromDraft(withDates, draft);
    assert.ok(body);
    assert.equal("title" in body!, false);
    assert.equal("priority" in body!, false);
    assert.equal("project_id" in body!, false);
    assert.equal(body!.deadline_at, null);
    assert.equal("start_no_earlier_at" in body!, false);
    assert.ok(body!.start_no_later_at);
  });

  it("buildDatesOnlyUpdateFromDraft rejects invalid dates", () => {
    const draft = taskToDraft(baseTask);
    draft.startNoEarlierAtLocal = "bogus";
    assert.match(validateOccurrenceDatesForSave(draft) ?? "", /Start no earlier is invalid/);
    assert.equal(buildDatesOnlyUpdateFromDraft(baseTask, draft), null);
  });
});
