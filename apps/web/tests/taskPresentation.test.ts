/**
 * F7 W3 presentation sort allowlist (B-F7-2).
 *
 * Run the web suite from apps/web:
 *   npm test
 *   node --experimental-strip-types --test tests/*.test.ts
 */
import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { mergeAccumPage } from "../src/boardAccum.ts";
import {
  draftFromPredicate,
  predicateFromDraft,
} from "../src/savedViewPredicate.ts";
import { orderTasksForest } from "../src/taskForest.ts";
import {
  SAVED_VIEW_SORT_KEYS,
  SAVED_VIEW_SORT_OPTIONS,
  boardViewSupported,
  isSavedViewSortKey,
  mergeSavedViewPresentationMode,
  savedViewPresentationMode,
  savedViewPresentationPayload,
  savedViewPresentationSort,
} from "../src/taskPresentation.ts";

const ALLOWED = [
  "sort_order",
  "created_at",
  "-created_at",
  "due_at",
  "-due_at",
  "priority",
  "-priority",
  "title",
  "-title",
] as const;

describe("saved-view sort allowlist", () => {
  it("matches the API presentation sort keys and the filter-modal options", () => {
    assert.deepEqual([...SAVED_VIEW_SORT_KEYS], [...ALLOWED]);
    assert.deepEqual(
      SAVED_VIEW_SORT_OPTIONS.map((opt) => opt.value),
      [...SAVED_VIEW_SORT_KEYS],
    );
    const labels = new Set(SAVED_VIEW_SORT_OPTIONS.map((opt) => opt.label));
    assert.equal(labels.size, SAVED_VIEW_SORT_KEYS.length);
  });

  it("accepts only exact allowlisted strings", () => {
    for (const key of SAVED_VIEW_SORT_KEYS) {
      assert.equal(isSavedViewSortKey(key), true);
      assert.equal(savedViewPresentationSort({ sort: key }), key);
    }
    for (const bad of ["", "  ", "title ", "-TITLE", "nope", "board_rank", "created_at desc"]) {
      assert.equal(isSavedViewSortKey(bad), false);
      assert.equal(savedViewPresentationSort({ sort: bad }), "sort_order");
    }
    assert.equal(savedViewPresentationSort(null), "sort_order");
    assert.equal(savedViewPresentationSort(undefined), "sort_order");
    assert.equal(savedViewPresentationSort({}), "sort_order");
  });
});

describe("saved-view presentation mode", () => {
  it("reads list and board and ignores anything else", () => {
    assert.equal(savedViewPresentationMode({ mode: "list" }), "list");
    assert.equal(savedViewPresentationMode({ mode: "board" }), "board");
    assert.equal(savedViewPresentationMode({ mode: "Board" }), null);
    assert.equal(savedViewPresentationMode({}), null);
    assert.equal(savedViewPresentationMode(null), null);
    assert.equal(boardViewSupported({ type: "saved", id: "view-1" }), true);
  });
});

describe("presentation save payload and mode-only merge", () => {
  it("round-trips an allowlisted sort with the current layout mode", () => {
    const stored = { mode: "list", sort: "-title", density: "compact" };
    const sort = savedViewPresentationSort(stored);
    assert.deepEqual(savedViewPresentationPayload("board", sort), {
      mode: "board",
      sort: "-title",
    });
  });

  it("drops a non-allowlisted sort instead of writing it back", () => {
    const sort = savedViewPresentationSort({ mode: "list", sort: "nope" });
    assert.deepEqual(savedViewPresentationPayload("list", sort), {
      mode: "list",
      sort: "sort_order",
    });
    assert.deepEqual(savedViewPresentationPayload("list", "board_rank"), {
      mode: "list",
      sort: "sort_order",
    });
  });

  it("mode-only toggle keeps sort and extra presentation keys", () => {
    const stored = { mode: "list" as const, sort: "-due_at", density: "compact" };
    const merged = mergeSavedViewPresentationMode(stored, "board");
    assert.equal(merged.mode, "board");
    assert.equal(merged.sort, "-due_at");
    assert.equal(merged.density, "compact");
    assert.deepEqual(mergeSavedViewPresentationMode(null, "list"), { mode: "list" });
  });

  it("filter edit round-trips the predicate without rewriting presentation sort", () => {
    const pred = {
      v: 1 as const,
      dimensions: {
        completion: "open" as const,
        labels: { ids: ["label-1"], match: "any" as const },
      },
    };
    const presentation = { mode: "list", sort: "-title" };
    const draft = draftFromPredicate(pred, { userTimezone: "America/Los_Angeles" });
    const next = predicateFromDraft(
      { ...draft, inbox: true },
      { userTimezone: "America/Los_Angeles" },
    );
    assert.equal(next.dimensions.inbox, true);
    assert.equal(next.dimensions.completion, "open");
    assert.deepEqual(next.dimensions.labels, { ids: ["label-1"], match: "any" });
    assert.deepEqual(savedViewPresentationPayload("list", savedViewPresentationSort(presentation)), {
      mode: "list",
      sort: "-title",
    });
  });
});

describe("saved list load-more keeps presentation peer order (M1)", () => {
  it("appends the next page, then forest-orders without resorting by sort_order", () => {
    const page1 = [
      { id: "1", parent_task_id: null, sort_order: 2, title: "Alpha only" },
    ];
    const page2 = [
      { id: "2", parent_task_id: null, sort_order: 1, title: "Alpha and beta" },
    ];
    const accum = mergeAccumPage(mergeAccumPage([], page1, 0), page2, 200);
    const ordered = orderTasksForest(accum, { peerOrder: "stable" });
    assert.deepEqual(
      ordered.map((task) => task.title),
      ["Alpha only", "Alpha and beta"],
    );
  });
});
