import { describe, it } from "node:test";
import assert from "node:assert/strict";
import {
  buildCatchUpWireFields,
  buildRecoverAuthorizeIntentFields,
  buildSuccessorWireFields,
  canOfferRecoverAffordance,
  c2LimitationCopy,
  editorsFromReviewCatchUp,
  isRecoverAuthorizeEnabled,
  parseBrowserLocalWall,
  recoverZoneLabels,
  shouldApplyReviewResponse,
  type RecoverFormIntent,
} from "../src/recoverHeldUi.ts";

describe("recoverHeldUi stale / generation", () => {
  it("disables Authorize when stale or generation mismatch", () => {
    assert.equal(
      isRecoverAuthorizeEnabled({
        stale: true,
        reviewOkForAuthorize: true,
        reviewBinding: "tok",
        appliedGeneration: 1,
        currentGeneration: 1,
        mutationPending: false,
      }),
      false,
    );
    assert.equal(
      isRecoverAuthorizeEnabled({
        stale: false,
        reviewOkForAuthorize: true,
        reviewBinding: "tok",
        appliedGeneration: 0,
        currentGeneration: 1,
        mutationPending: false,
      }),
      false,
    );
    assert.equal(
      isRecoverAuthorizeEnabled({
        stale: false,
        reviewOkForAuthorize: true,
        reviewBinding: "tok",
        appliedGeneration: 2,
        currentGeneration: 2,
        mutationPending: false,
      }),
      true,
    );
  });

  it("discards out-of-order review responses", () => {
    assert.equal(shouldApplyReviewResponse(1, 2), false);
    assert.equal(shouldApplyReviewResponse(2, 2), true);
  });

  it("requires binding and review_ok", () => {
    assert.equal(
      isRecoverAuthorizeEnabled({
        stale: false,
        reviewOkForAuthorize: false,
        reviewBinding: "tok",
        appliedGeneration: 0,
        currentGeneration: 0,
        mutationPending: false,
      }),
      false,
    );
    assert.equal(
      isRecoverAuthorizeEnabled({
        stale: false,
        reviewOkForAuthorize: true,
        reviewBinding: "",
        appliedGeneration: 0,
        currentGeneration: 0,
        mutationPending: false,
      }),
      false,
    );
  });
});

describe("recoverHeldUi zone labels (Option A)", () => {
  it("labels edit-zone as browser local and rule-zone from cadence", () => {
    const labels = recoverZoneLabels("America/New_York");
    assert.match(labels.editZoneLabel, /browser local/);
    assert.match(labels.ruleZoneLabel, /America\/New_York/);
    assert.ok(labels.editZone.length > 0);
  });
});

describe("recoverHeldUi catch-up wire omit-vs-null", () => {
  it("omits unchanged catch-up dates and sends null on clear", () => {
    const mapped = editorsFromReviewCatchUp({
      due_at: "2026-10-21T15:00:45.123Z",
      start_no_earlier_at: null,
      start_no_later_at: null,
      deadline_at: "2026-10-22T18:00:00.000Z",
      remaining_minutes: 30,
      remaining_minutes_default: 30,
    });
    const unchanged: RecoverFormIntent = {
      successor: "none",
      stepCount: "1",
      editors: { ...mapped.editors },
      baseline: mapped.baseline,
      remainingTouched: false,
    };
    const omit = buildCatchUpWireFields(unchanged);
    assert.equal(omit.ok, true);
    if (omit.ok) {
      assert.equal("catch_up_due_at" in omit.fields, false);
      assert.equal("catch_up_deadline_at" in omit.fields, false);
      assert.equal("catch_up_remaining_minutes" in omit.fields, false);
    }

    const cleared: RecoverFormIntent = {
      ...unchanged,
      editors: { ...mapped.editors, dueLocal: "", deadlineLocal: "" },
    };
    const clearedWire = buildCatchUpWireFields(cleared);
    assert.equal(clearedWire.ok, true);
    if (clearedWire.ok) {
      assert.equal(clearedWire.fields.catch_up_due_at, null);
      assert.equal(clearedWire.fields.catch_up_deadline_at, null);
    }
  });

  it("sends remaining override including 0 when touched", () => {
    const mapped = editorsFromReviewCatchUp({
      due_at: null,
      start_no_earlier_at: null,
      start_no_later_at: null,
      deadline_at: null,
      remaining_minutes: 40,
      remaining_minutes_default: 40,
    });
    const intent: RecoverFormIntent = {
      successor: "none",
      stepCount: "1",
      editors: { ...mapped.editors, remainingMinutes: "0" },
      baseline: mapped.baseline,
      remainingTouched: true,
    };
    const wire = buildCatchUpWireFields(intent);
    assert.equal(wire.ok, true);
    if (wire.ok) {
      assert.equal(wire.fields.catch_up_remaining_minutes, 0);
    }
  });

  it("authorize payload includes remaining after stale→refresh with override", () => {
    // Open / true-read-only review: default remaining 60, no override on wire.
    const initial = editorsFromReviewCatchUp({
      due_at: null,
      start_no_earlier_at: null,
      start_no_later_at: null,
      deadline_at: null,
      remaining_minutes: 60,
      remaining_minutes_default: 60,
    });
    const editIntent: RecoverFormIntent = {
      successor: "none",
      stepCount: "1",
      editors: { ...initial.editors, remainingMinutes: "45" },
      baseline: initial.baseline,
      remainingTouched: true,
    };
    const reviewWire = buildCatchUpWireFields(editIntent);
    assert.equal(reviewWire.ok, true);
    if (!reviewWire.ok) return;
    assert.equal(reviewWire.fields.catch_up_remaining_minutes, 45);

    // After refresh review: response absorbs 45 into catch_up; pane clears remainingTouched
    // and remaps editors/baseline — rebuild would omit remaining (the R3 bug).
    const afterRefresh = editorsFromReviewCatchUp({
      due_at: null,
      start_no_earlier_at: null,
      start_no_later_at: null,
      deadline_at: null,
      remaining_minutes: 45,
      remaining_minutes_default: 60,
    });
    const rebuildAfterRefresh = buildCatchUpWireFields({
      successor: "none",
      stepCount: "1",
      editors: afterRefresh.editors,
      baseline: afterRefresh.baseline,
      remainingTouched: false,
    });
    assert.equal(rebuildAfterRefresh.ok, true);
    if (rebuildAfterRefresh.ok) {
      assert.equal(
        "catch_up_remaining_minutes" in rebuildAfterRefresh.fields,
        false,
        "rebuild-from-editors must omit after remapped baseline (do not use for authorize)",
      );
    }

    // Authorize echoes the bound review wire (and successor).
    const authorizeFields = buildRecoverAuthorizeIntentFields({
      boundCatchUpFields: reviewWire.fields,
      boundSuccessorFields: buildSuccessorWireFields(editIntent),
    });
    assert.equal(authorizeFields.catch_up_remaining_minutes, 45);
  });
});

describe("recoverHeldUi parseBrowserLocalWall", () => {
  it("rejects invalid walls", () => {
    assert.equal(parseBrowserLocalWall("not-a-date").ok, false);
  });

  it("accepts a round-trippable local wall", () => {
    const parsed = parseBrowserLocalWall("2026-06-15T14:30");
    assert.equal(parsed.ok, true);
    if (parsed.ok) {
      assert.match(parsed.iso, /Z$/);
    }
  });
});

describe("recoverHeldUi affordance / C2 copy", () => {
  it("offers Recover only when task has recurrence", () => {
    assert.equal(canOfferRecoverAffordance(true), true);
    assert.equal(canOfferRecoverAffordance(false), false);
  });

  it("surfaces C2 code without delete/unpin remedy", () => {
    const copy = c2LimitationCopy("BLOCKS_PREVENT_NEXT_NORMAL", "same-task pins");
    assert.match(copy, /BLOCKS_PREVENT_NEXT_NORMAL/);
    assert.doesNotMatch(copy, /delete|unpin|manual clear/i);
  });
});
