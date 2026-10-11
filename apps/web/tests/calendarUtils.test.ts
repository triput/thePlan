import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  heightPercentForDuration,
  isCompactCalendarBlock,
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

describe("heightPercentForDuration", () => {
  it("uses true duration without a visual floor", () => {
    const bounds = resolveHourBounds(false);
    const pct = heightPercentForDuration(5, bounds);
    assert.ok(pct < 1);
    assert.ok(pct > 0);
  });
});

describe("isCompactCalendarBlock", () => {
  it("flags very short blocks", () => {
    const bounds = resolveHourBounds(false);
    assert.equal(isCompactCalendarBlock(5, bounds), true);
    assert.equal(isCompactCalendarBlock(60, bounds), false);
  });
});

describe("blockDurationMinutesForTask", () => {
  it("prefers task estimate, then settings default, then 60", () => {
    assert.equal(blockDurationMinutesForTask(45, 30), 45);
    assert.equal(blockDurationMinutesForTask(0, 30), 30);
    assert.equal(blockDurationMinutesForTask(0, 0), 60);
  });
});
