import { describe, it } from "node:test";
import assert from "node:assert/strict";
import {
  buildCatchUpWireFields,
  buildRecoverAuthorizeIntentFields,
  buildSuccessorWireFields,
  canOfferRecoverAffordance,
  c2LimitationCopy,
  editorsFromReviewCatchUp,
  effectiveCatchUpFieldsAfterReview,
  formatWallInTimeZone,
  isRecoverAuthorizeEnabled,
  parseBrowserLocalWall,
  parseWallInTimeZone,
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

  it("marks zonesDiffer when rule zone ≠ browser edit zone", () => {
    const browser = recoverZoneLabels("America/New_York").editZone;
    const other = browser === "UTC" ? "America/Los_Angeles" : "UTC";
    const differ = recoverZoneLabels(other);
    assert.equal(differ.zonesDiffer, true);
    const same = recoverZoneLabels(browser);
    assert.equal(same.zonesDiffer, false);
  });
});

describe("recoverHeldUi catch-up wire omit-vs-null + intent carry", () => {
  it("omits unchanged catch-up dates on first review and sends null on clear", () => {
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
      priorCatchUpFields: {},
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
      priorCatchUpFields: {},
    };
    const wire = buildCatchUpWireFields(intent);
    assert.equal(wire.ok, true);
    if (wire.ok) {
      assert.equal(wire.fields.catch_up_remaining_minutes, 0);
    }
  });

  it("two-refresh retains reviewed due + remaining (stateless review)", () => {
    // Review 1: operator sets due + remaining 45.
    const initial = editorsFromReviewCatchUp({
      due_at: null,
      start_no_earlier_at: null,
      start_no_later_at: null,
      deadline_at: null,
      remaining_minutes: 35,
      remaining_minutes_default: 35,
    });
    const dueIso = "2026-10-21T15:00:45.123Z";
    const review1Intent: RecoverFormIntent = {
      successor: "none",
      stepCount: "1",
      editors: {
        ...initial.editors,
        dueLocal: "2026-10-21T08:00", // wall used only for edit path; we inject prior below
        remainingMinutes: "45",
      },
      baseline: initial.baseline,
      remainingTouched: true,
      priorCatchUpFields: {},
    };
    // Simulate: first review sent due ISO + remaining 45 (as if parsed).
    const sent1 = {
      catch_up_due_at: dueIso,
      catch_up_remaining_minutes: 45,
    };
    const after1 = editorsFromReviewCatchUp({
      due_at: dueIso,
      start_no_earlier_at: null,
      start_no_later_at: null,
      deadline_at: null,
      remaining_minutes: 45,
      remaining_minutes_default: 35,
    });
    const prior1 = effectiveCatchUpFieldsAfterReview(sent1, {
      due_at: dueIso,
      start_no_earlier_at: null,
      start_no_later_at: null,
      deadline_at: null,
      remaining_minutes: 45,
      remaining_minutes_default: 35,
    });
    assert.equal(prior1.catch_up_due_at, dueIso);
    assert.equal(prior1.catch_up_remaining_minutes, 45);

    // Refresh alone (no edits): remapped baseline, remainingTouched false.
    const refreshAlone = buildCatchUpWireFields({
      successor: "none",
      stepCount: "1",
      editors: after1.editors,
      baseline: after1.baseline,
      remainingTouched: false,
      priorCatchUpFields: prior1,
    });
    assert.equal(refreshAlone.ok, true);
    if (!refreshAlone.ok) return;
    assert.equal(refreshAlone.fields.catch_up_due_at, dueIso);
    assert.equal(refreshAlone.fields.catch_up_remaining_minutes, 45);

    // Second refresh still retains.
    const prior2 = effectiveCatchUpFieldsAfterReview(refreshAlone.fields, {
      due_at: dueIso,
      start_no_earlier_at: null,
      start_no_later_at: null,
      deadline_at: null,
      remaining_minutes: 45,
      remaining_minutes_default: 35,
    });
    const refresh2 = buildCatchUpWireFields({
      successor: "none",
      stepCount: "1",
      editors: after1.editors,
      baseline: after1.baseline,
      remainingTouched: false,
      priorCatchUpFields: prior2,
    });
    assert.equal(refresh2.ok, true);
    if (!refresh2.ok) return;
    assert.equal(refresh2.fields.catch_up_due_at, dueIso);
    assert.equal(refresh2.fields.catch_up_remaining_minutes, 45);

    // Silence unused first-intent parse path (due wall may fail host TZ); we assert prior carry.
    void review1Intent;
  });

  it("edit-one-field retains all other reviewed fields", () => {
    const dueIso = "2026-10-21T15:00:45.123Z";
    const deadlineIso = "2026-10-22T18:00:00.456Z";
    const prior = {
      catch_up_due_at: dueIso,
      catch_up_deadline_at: deadlineIso,
      catch_up_remaining_minutes: 45,
    };
    const afterReview = editorsFromReviewCatchUp({
      due_at: dueIso,
      start_no_earlier_at: null,
      start_no_later_at: null,
      deadline_at: deadlineIso,
      remaining_minutes: 45,
      remaining_minutes_default: 35,
    });
    // Edit ONLY remaining → 50; due + deadline must still be on the wire.
    const editRemaining = buildCatchUpWireFields({
      successor: "none",
      stepCount: "1",
      editors: { ...afterReview.editors, remainingMinutes: "50" },
      baseline: afterReview.baseline,
      remainingTouched: true,
      priorCatchUpFields: prior,
    });
    assert.equal(editRemaining.ok, true);
    if (!editRemaining.ok) return;
    assert.equal(editRemaining.fields.catch_up_due_at, dueIso);
    assert.equal(editRemaining.fields.catch_up_deadline_at, deadlineIso);
    assert.equal(editRemaining.fields.catch_up_remaining_minutes, 50);
  });

  it("explicit clear stays null across refresh; omit does not resurrect", () => {
    const dueIso = "2026-10-21T15:00:45.123Z";
    const afterWithDue = editorsFromReviewCatchUp({
      due_at: dueIso,
      start_no_earlier_at: null,
      start_no_later_at: null,
      deadline_at: null,
      remaining_minutes: 35,
      remaining_minutes_default: 35,
    });
    const clearWire = buildCatchUpWireFields({
      successor: "none",
      stepCount: "1",
      editors: { ...afterWithDue.editors, dueLocal: "" },
      baseline: afterWithDue.baseline,
      remainingTouched: false,
      priorCatchUpFields: { catch_up_due_at: dueIso },
    });
    assert.equal(clearWire.ok, true);
    if (!clearWire.ok) return;
    assert.equal(clearWire.fields.catch_up_due_at, null);

    const afterClear = editorsFromReviewCatchUp({
      due_at: null,
      start_no_earlier_at: null,
      start_no_later_at: null,
      deadline_at: null,
      remaining_minutes: 35,
      remaining_minutes_default: 35,
    });
    const priorCleared = effectiveCatchUpFieldsAfterReview(clearWire.fields, {
      due_at: null,
      start_no_earlier_at: null,
      start_no_later_at: null,
      deadline_at: null,
      remaining_minutes: 35,
      remaining_minutes_default: 35,
    });
    assert.equal(priorCleared.catch_up_due_at, null);

    const refresh = buildCatchUpWireFields({
      successor: "none",
      stepCount: "1",
      editors: afterClear.editors,
      baseline: afterClear.baseline,
      remainingTouched: false,
      priorCatchUpFields: priorCleared,
    });
    assert.equal(refresh.ok, true);
    if (!refresh.ok) return;
    assert.equal(refresh.fields.catch_up_due_at, null);
  });

  it("authorize payload includes remaining after stale→refresh with override", () => {
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
      priorCatchUpFields: {},
    };
    const reviewWire = buildCatchUpWireFields(editIntent);
    assert.equal(reviewWire.ok, true);
    if (!reviewWire.ok) return;
    assert.equal(reviewWire.fields.catch_up_remaining_minutes, 45);

    const afterRefresh = editorsFromReviewCatchUp({
      due_at: null,
      start_no_earlier_at: null,
      start_no_later_at: null,
      deadline_at: null,
      remaining_minutes: 45,
      remaining_minutes_default: 60,
    });
    const prior = effectiveCatchUpFieldsAfterReview(reviewWire.fields, {
      due_at: null,
      start_no_earlier_at: null,
      start_no_later_at: null,
      deadline_at: null,
      remaining_minutes: 45,
      remaining_minutes_default: 60,
    });
    const refreshWire = buildCatchUpWireFields({
      successor: "none",
      stepCount: "1",
      editors: afterRefresh.editors,
      baseline: afterRefresh.baseline,
      remainingTouched: false,
      priorCatchUpFields: prior,
    });
    assert.equal(refreshWire.ok, true);
    if (!refreshWire.ok) return;
    assert.equal(refreshWire.fields.catch_up_remaining_minutes, 45);

    const authorizeFields = buildRecoverAuthorizeIntentFields({
      boundCatchUpFields: prior,
      boundSuccessorFields: buildSuccessorWireFields(editIntent),
    });
    assert.equal(authorizeFields.catch_up_remaining_minutes, 45);
  });
});

describe("recoverHeldUi parseWallInTimeZone gap/fold (LA)", () => {
  const LA = "America/Los_Angeles";

  it("rejects invalid walls", () => {
    assert.equal(parseWallInTimeZone("not-a-date", LA).ok, false);
    assert.equal(parseBrowserLocalWall("not-a-date").ok, false);
  });

  it("accepts an unambiguous summer wall in LA", () => {
    const parsed = parseWallInTimeZone("2026-06-15T14:30", LA);
    assert.equal(parsed.ok, true);
    if (parsed.ok) {
      assert.match(parsed.iso, /Z$/);
      assert.equal(formatWallInTimeZone(Date.parse(parsed.iso), LA), "2026-06-15T14:30");
    }
  });

  it("rejects LA spring gap (nonexistent wall)", () => {
    // 2026-03-08: LA springs forward 02:00 → 03:00; 02:30 does not exist.
    const gap = parseWallInTimeZone("2026-03-08T02:30", LA);
    assert.equal(gap.ok, false);
    if (!gap.ok) {
      assert.equal(gap.reason, "ambiguous_or_nonexistent");
    }
  });

  it("rejects LA fall fold (two valid instants)", () => {
    // 2026-11-01: LA falls back 02:00 → 01:00; 01:30 is ambiguous.
    const fold = parseWallInTimeZone("2026-11-01T01:30", LA);
    assert.equal(fold.ok, false);
    if (!fold.ok) {
      assert.equal(fold.reason, "ambiguous_or_nonexistent");
    }
  });

  it("accepts unambiguous walls on fold day outside the repeated hour", () => {
    const before = parseWallInTimeZone("2026-11-01T00:30", LA);
    assert.equal(before.ok, true);
    const after = parseWallInTimeZone("2026-11-01T03:30", LA);
    assert.equal(after.ok, true);
  });
});

describe("recoverHeldUi parseWallInTimeZone gap/fold (Lord Howe 30min)", () => {
  const LH = "Australia/Lord_Howe";

  it("rejects Lord Howe fall fold (30min repeated local hour)", () => {
    // 2026-04-05: LH ends DST; 01:45 local occurs twice.
    const fold = parseWallInTimeZone("2026-04-05T01:45", LH);
    assert.equal(fold.ok, false);
    if (!fold.ok) {
      assert.equal(fold.reason, "ambiguous_or_nonexistent");
    }
  });

  it("rejects Lord Howe spring gap (30min skipped local times)", () => {
    // 2026-10-04: LH starts DST; 02:00–02:29 standard do not exist.
    const gap = parseWallInTimeZone("2026-10-04T02:15", LH);
    assert.equal(gap.ok, false);
    if (!gap.ok) {
      assert.equal(gap.reason, "ambiguous_or_nonexistent");
    }
  });

  it("accepts unambiguous summer wall in Lord Howe", () => {
    const parsed = parseWallInTimeZone("2026-06-15T14:30", LH);
    assert.equal(parsed.ok, true);
    if (parsed.ok) {
      assert.equal(formatWallInTimeZone(Date.parse(parsed.iso), LH), "2026-06-15T14:30");
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
