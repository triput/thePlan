/**
 * Saved-view filter draft validation and predicate round-trips (F7 W3, B-F7-2).
 *
 * Run the web suite from apps/web:
 *   npm test
 *   node --experimental-strip-types --test tests/*.test.ts
 */
import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  draftFromPredicate,
  predicateFromDraft,
  validateSavedViewFilterDraft,
} from "../src/savedViewPredicate.ts";
import {
  savedViewPresentationPayload,
  savedViewPresentationSort,
} from "../src/taskPresentation.ts";

const FIXED_FROM = "2026-10-10T07:00:00.000Z";
const FIXED_TO = "2026-10-11T07:00:00.000Z";

describe("validateSavedViewFilterDraft", () => {
  it("rejects fixed due with a missing bound", () => {
    const msg = validateSavedViewFilterDraft({
      dueKind: "fixed",
      dueFixedFrom: "2026-10-10",
      dueFixedTo: "",
    } as ReturnType<typeof draftFromPredicate>);
    assert.equal(msg, "Fixed due range requires both From and To dates.");
  });
});

describe("completion omission (R6)", () => {
  it("does not add completion when the stored view omitted it", () => {
    const draft = draftFromPredicate({ v: 1, dimensions: {} });
    assert.equal(draft.completion, null);
    const out = predicateFromDraft({ ...draft, inbox: false });
    assert.equal("completion" in out.dimensions, false);
  });

  it("new create still defaults open in the draft factory path", () => {
    const out = predicateFromDraft({
      inbox: false,
      projectIds: [],
      epicIds: [],
      labelIds: [],
      labelMatch: "any",
      priorities: [],
      workflowStates: [],
      completion: "open",
      scheduleStatuses: [],
      scheduleStyles: [],
      dueKind: null,
      dueRolling: null,
      dueWithinDays: 7,
      dueFixedFrom: "",
      dueFixedTo: "",
    });
    assert.equal(out.dimensions.completion, "open");
  });
});

describe("fixed due round-trip (R4)", () => {
  const pred = {
    v: 1 as const,
    dimensions: {
      completion: "any" as const,
      due: { kind: "fixed" as const, from: FIXED_FROM, to: FIXED_TO },
    },
  };

  it("preserves absolute ISO bounds on rename-only under America/Los_Angeles", () => {
    const draft = draftFromPredicate(pred, { userTimezone: "America/Los_Angeles" });
    const out = predicateFromDraft(
      { ...draft, projectIds: [...draft.projectIds] },
      { userTimezone: "America/Los_Angeles" },
    );
    assert.equal(out.dimensions.due?.from, FIXED_FROM);
    assert.equal(out.dimensions.due?.to, FIXED_TO);
  });

  it("preserves absolute ISO bounds on rename-only under Asia/Tokyo", () => {
    const draft = draftFromPredicate(pred, { userTimezone: "Asia/Tokyo" });
    const out = predicateFromDraft(
      { ...draft, epicIds: [...draft.epicIds] },
      { userTimezone: "Asia/Tokyo" },
    );
    assert.equal(out.dimensions.due?.from, FIXED_FROM);
    assert.equal(out.dimensions.due?.to, FIXED_TO);
  });

  it("keeps presentation sort across a rename-only predicate round-trip", () => {
    const draft = draftFromPredicate(pred, { userTimezone: "America/Los_Angeles" });
    const out = predicateFromDraft(draft, { userTimezone: "America/Los_Angeles" });
    assert.equal(out.dimensions.due?.from, FIXED_FROM);
    const presentation = { mode: "board", sort: "-title", note: "kept on server merge" };
    assert.equal(savedViewPresentationSort(presentation), "-title");
    assert.deepEqual(savedViewPresentationPayload("board", presentation.sort), {
      mode: "board",
      sort: "-title",
    });
  });

  it("throws instead of emitting an unbounded predicate when fixed bounds are incomplete (R3)", () => {
    const draft = draftFromPredicate(pred, { userTimezone: "America/Los_Angeles" });
    const broken = { ...draft, dueFixedTo: "" };
    assert.ok(validateSavedViewFilterDraft(broken));
    assert.throws(
      () => predicateFromDraft(broken, { userTimezone: "America/Los_Angeles" }),
      /both From and To/,
    );
  });
});
