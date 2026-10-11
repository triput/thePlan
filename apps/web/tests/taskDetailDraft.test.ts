import { describe, it } from "node:test";
import assert from "node:assert/strict";
import type { Task } from "../src/api.ts";
import {
  isTaskDraftDirty,
  shouldResetTaskDetailDraft,
  TASK_TITLE_MAX_LENGTH,
  taskToDraft,
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
});
