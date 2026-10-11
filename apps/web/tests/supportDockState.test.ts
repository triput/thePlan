import { describe, it } from "node:test";
import assert from "node:assert/strict";
import {
  dirtyPromptFor,
  resolveSupportDockMode,
  shouldOfferDirtyPrompt,
} from "../src/supportDockState.ts";

describe("resolveSupportDockMode", () => {
  it("prefers task over preview on calendar", () => {
    assert.equal(
      resolveSupportDockMode({
        isCalendarView: true,
        dockCollapsed: false,
        selectedTaskId: "task-1",
        previewOpen: true,
      }),
      "task",
    );
  });

  it("shows preview when open and no task", () => {
    assert.equal(
      resolveSupportDockMode({
        isCalendarView: true,
        dockCollapsed: false,
        selectedTaskId: null,
        previewOpen: true,
      }),
      "preview",
    );
  });

  it("hides preview surface when dock collapsed but keeps session elsewhere", () => {
    assert.equal(
      resolveSupportDockMode({
        isCalendarView: true,
        dockCollapsed: true,
        selectedTaskId: null,
        previewOpen: true,
      }),
      "hidden",
    );
  });

  it("shows calendar idle when expanded on calendar", () => {
    assert.equal(
      resolveSupportDockMode({
        isCalendarView: true,
        dockCollapsed: false,
        selectedTaskId: null,
        previewOpen: false,
      }),
      "calendar-idle",
    );
  });

  it("hides on list view without task", () => {
    assert.equal(
      resolveSupportDockMode({
        isCalendarView: false,
        dockCollapsed: false,
        selectedTaskId: null,
        previewOpen: false,
      }),
      "hidden",
    );
  });

  it("shows task on list view when selected", () => {
    assert.equal(
      resolveSupportDockMode({
        isCalendarView: false,
        dockCollapsed: true,
        selectedTaskId: "abc",
        previewOpen: false,
      }),
      "task",
    );
  });

  it("still resolves task when collapsed until selection is cleared", () => {
    assert.equal(
      resolveSupportDockMode({
        isCalendarView: true,
        dockCollapsed: true,
        selectedTaskId: "task-1",
        previewOpen: false,
      }),
      "task",
    );
  });

  it("honors collapse on calendar when no task is selected", () => {
    assert.equal(
      resolveSupportDockMode({
        isCalendarView: true,
        dockCollapsed: true,
        selectedTaskId: null,
        previewOpen: true,
      }),
      "hidden",
    );
  });
});

describe("dirtyPromptFor", () => {
  it("uses Save and open for task switch", () => {
    const copy = dirtyPromptFor("switch_task");
    assert.match(copy.saveLabel, /Save and open/i);
    assert.equal(copy.discardLabel, "Discard");
  });

  it("scopes change_view message", () => {
    const copy = dirtyPromptFor("change_view", { viewLabel: "Trash" });
    assert.match(copy.message, /Trash/);
  });
});

describe("shouldOfferDirtyPrompt", () => {
  it("only prompts when dirty", () => {
    assert.equal(shouldOfferDirtyPrompt(false), false);
    assert.equal(shouldOfferDirtyPrompt(true), true);
  });
});
