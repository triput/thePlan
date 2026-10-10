/**
 * Board accumulator merge, including F7 W3 saved-view load-more (B-F7-2).
 *
 * Run the web suite from apps/web:
 *   npm test
 *   node --experimental-strip-types --test tests/*.test.ts
 */
import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  accumEffectDepsChanged,
  mergeAccumPage,
  restoreAccumAfterMoveClear,
} from "../src/boardAccum.ts";

/** TaskList saved views page by 200; TaskBoard saved views page by 500. */
const SAVED_LIST_PAGE = 200;
const SAVED_BOARD_PAGE = 500;

describe("mergeAccumPage", () => {
  it("replaces when offset is 0", () => {
    const prev = [{ id: "stale" }];
    const page = [{ id: "a" }, { id: "b" }];
    assert.deepEqual(mergeAccumPage(prev, page, 0), page);
  });

  it("appends unseen ids when offset > 0", () => {
    const prev = [{ id: "a" }];
    const page = [{ id: "a" }, { id: "b" }];
    assert.deepEqual(mergeAccumPage(prev, page, 20), [{ id: "a" }, { id: "b" }]);
  });

  it("saved-view list continuation appends at offset 200 and keeps the first copy", () => {
    const first = [
      { id: "a", title: "A" },
      { id: "b", title: "B" },
    ];
    const loaded = mergeAccumPage([], first, 0);
    const next = mergeAccumPage(
      loaded,
      [
        { id: "b", title: "B rewritten" },
        { id: "c", title: "C" },
      ],
      SAVED_LIST_PAGE,
    );
    assert.deepEqual(
      next.map((task) => task.id),
      ["a", "b", "c"],
    );
    assert.equal(next[1].title, "B");
  });

  it("saved-view board continuation appends at offset 500", () => {
    const first = [{ id: "p1" }, { id: "p2" }];
    const loaded = mergeAccumPage([], first, 0);
    const next = mergeAccumPage(loaded, [{ id: "p2" }, { id: "p3" }], SAVED_BOARD_PAGE);
    assert.deepEqual(
      next.map((task) => task.id),
      ["p1", "p2", "p3"],
    );
  });

  it("offset 0 replaces an already loaded accumulator", () => {
    const loaded = mergeAccumPage(mergeAccumPage([], [{ id: "a" }], 0), [{ id: "b" }], SAVED_LIST_PAGE);
    assert.deepEqual(mergeAccumPage(loaded, [{ id: "fresh" }], 0), [{ id: "fresh" }]);
  });

  it("an empty continuation page does not drop accumulated rows", () => {
    const loaded = mergeAccumPage([], [{ id: "a" }, { id: "b" }], 0);
    assert.deepEqual(mergeAccumPage(loaded, [], SAVED_LIST_PAGE), loaded);
  });
});

describe("accum reset after move (Dex P2)", () => {
  it("Done: unchanged query data + offset 0 stays blank without reset gen", () => {
    const cachedPage = [{ id: "done-1" }, { id: "done-2" }];
    const dataRef = { items: cachedPage, total: 2 };
    // Clear accumulators; invalidate refetch returns same data reference.
    assert.equal(
      accumEffectDepsChanged({
        prevDataRef: dataRef,
        nextDataRef: dataRef,
        prevOffset: 0,
        nextOffset: 0,
        prevResetGen: 0,
        nextResetGen: 0,
      }),
      false,
    );
    assert.deepEqual(
      restoreAccumAfterMoveClear({
        cachedPage,
        prevDataRef: dataRef,
        nextDataRef: dataRef,
        prevOffset: 0,
        nextOffset: 0,
        prevResetGen: 0,
        nextResetGen: 0,
      }),
      [],
    );
  });

  it("Done: reset gen bump restores first page from retained cache", () => {
    const cachedPage = [{ id: "done-1" }, { id: "done-2" }];
    const dataRef = { items: cachedPage, total: 2 };
    assert.deepEqual(
      restoreAccumAfterMoveClear({
        cachedPage,
        prevDataRef: dataRef,
        nextDataRef: dataRef,
        prevOffset: 0,
        nextOffset: 0,
        prevResetGen: 0,
        nextResetGen: 1,
      }),
      cachedPage,
    );
  });

  it("Today/Upcoming smart-open: unchanged due page stays blank without reset gen", () => {
    const duePage = [{ id: "due-a" }, { id: "due-b" }];
    const dataRef = { items: duePage, total: 2 };
    // Move a scheduled-only card; due-task query content unchanged.
    assert.deepEqual(
      restoreAccumAfterMoveClear({
        cachedPage: duePage,
        prevDataRef: dataRef,
        nextDataRef: dataRef,
        prevOffset: 0,
        nextOffset: 0,
        prevResetGen: 3,
        nextResetGen: 3,
      }),
      [],
    );
  });

  it("Today/Upcoming smart-open: reset gen restores unrelated due tasks", () => {
    const duePage = [{ id: "due-a" }, { id: "due-b" }];
    const dataRef = { items: duePage, total: 2 };
    assert.deepEqual(
      restoreAccumAfterMoveClear({
        cachedPage: duePage,
        prevDataRef: dataRef,
        nextDataRef: dataRef,
        prevOffset: 0,
        nextOffset: 0,
        prevResetGen: 3,
        nextResetGen: 4,
      }),
      duePage,
    );
  });
});
