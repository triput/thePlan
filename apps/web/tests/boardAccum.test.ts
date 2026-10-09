import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  accumEffectDepsChanged,
  mergeAccumPage,
  restoreAccumAfterMoveClear,
} from "../src/boardAccum.ts";

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
