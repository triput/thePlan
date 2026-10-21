import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { formatScheduleReasonFact } from "../src/scheduleReasonFacts.ts";

describe("formatScheduleReasonFact held / bounds", () => {
  it("formats occurrence_disposition_held", () => {
    assert.match(
      formatScheduleReasonFact("occurrence_disposition_held", {}),
      /held as a missed start window/i,
    );
  });

  it("formats occurrence_disposition_skipped", () => {
    assert.match(
      formatScheduleReasonFact("occurrence_disposition_skipped", {}),
      /skipped/i,
    );
  });

  it("formats occurrence_bounds_miss", () => {
    assert.match(
      formatScheduleReasonFact("occurrence_bounds_miss", {}),
      /held as missed/i,
    );
  });
});
