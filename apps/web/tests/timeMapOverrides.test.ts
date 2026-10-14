import assert from "node:assert/strict";
import { describe, it } from "node:test";
import type { SegmentBand, SegmentMapWindow, SegmentOverride } from "../src/timeMapDaySegments.ts";
import {
  effectiveTimeMapSegmentsForDay,
  overrideUtcBounds,
} from "../src/timeMapDaySegments.ts";

const LA_SETTINGS = { timezone: "America/Los_Angeles" };

function band(tier: SegmentBand["tier"], start: string, end: string): SegmentBand {
  return {
    id: `band-${tier}-${start}`,
    tier,
    start_time: start,
    end_time: end,
    days_of_week: 127,
    sort_order: 0,
  };
}

function baseWindow(): SegmentMapWindow {
  return {
    strict_mode: true,
    bands: [band("green", "07:00", "12:00")],
  };
}

function tokyoOverride(): SegmentOverride {
  return {
    id: "ov-1",
    local_start_date: "2026-10-13",
    local_end_date: "2026-10-13",
    timezone: "Asia/Tokyo",
    strict_mode: true,
    bands: [band("red", "07:00", "12:00")],
  };
}

describe("effectiveTimeMapSegmentsForDay (V3-D2)", () => {
  const day = new Date("2026-10-13T12:00:00-07:00");

  it("splits LA Oct 13 at Tokyo override end (08:00 LA / 15:00 UTC)", () => {
    const override = tokyoOverride();
    const { end } = overrideUtcBounds(override);
    assert.equal(end.toISOString(), "2026-10-13T15:00:00.000Z");

    const segments = effectiveTimeMapSegmentsForDay(
      baseWindow(),
      [override],
      day,
      LA_SETTINGS.timezone,
    );
    assert.equal(segments.length, 2);
    assert.equal(segments[0]?.source, "override");
    assert.equal(segments[0]?.bands[0]?.tier, "red");
    assert.equal(segments[0]?.endUtc.toISOString(), "2026-10-13T15:00:00.000Z");
    assert.equal(segments[1]?.source, "base_map");
    assert.equal(segments[1]?.bands[0]?.tier, "green");
    assert.equal(segments[1]?.startUtc.toISOString(), "2026-10-13T15:00:00.000Z");
  });

  it("splits Monday LA at override start boundary", () => {
    const override = tokyoOverride();
    override.bands = [band("green", "08:00", "08:30")];
    const monday = new Date("2026-10-12T12:00:00-07:00");
    const segments = effectiveTimeMapSegmentsForDay(
      baseWindow(),
      [override],
      monday,
      LA_SETTINGS.timezone,
    );
    assert.equal(segments.length, 2);
    assert.equal(segments[0]?.source, "base_map");
    assert.equal(segments[0]?.endUtc.toISOString(), "2026-10-12T15:00:00.000Z");
    assert.equal(segments[1]?.source, "override");
    assert.equal(segments[1]?.startUtc.toISOString(), "2026-10-12T15:00:00.000Z");
  });
});
