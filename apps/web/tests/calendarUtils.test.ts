import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  resolveHourBounds,
  startTimeFromSlotOffset,
} from "../src/calendarUtils.ts";
import { blockDurationMinutesForTask } from "../src/taskCalendarDrag.ts";

describe("startTimeFromSlotOffset", () => {
  const bounds = resolveHourBounds(false);
  const day = new Date(2026, 9, 8);

  it("snaps to 15 minutes from pixel offset", () => {
    const start = startTimeFromSlotOffset(day, 12, 48, bounds);
    assert.equal(start.getHours(), bounds.start);
    assert.equal(start.getMinutes(), 15);
  });

  it("clamps to the visible window end minus min block", () => {
    const maxY = bounds.hours * 48;
    const start = startTimeFromSlotOffset(day, maxY + 200, 48, bounds);
    const windowEndMins = bounds.end * 60;
    const startMins = start.getHours() * 60 + start.getMinutes();
    assert.ok(startMins <= windowEndMins - 15);
  });
});

describe("blockDurationMinutesForTask", () => {
  it("prefers task estimate, then settings default, then 60", () => {
    assert.equal(blockDurationMinutesForTask(45, 30), 45);
    assert.equal(blockDurationMinutesForTask(0, 30), 30);
    assert.equal(blockDurationMinutesForTask(0, 0), 60);
  });
});
