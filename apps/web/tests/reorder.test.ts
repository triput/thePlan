import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  buildReorderSwap,
  canReorderDown,
  canReorderUp,
} from "../src/reorder.ts";

type Item = { id: string; sort_order: number };

function item(id: string, sort_order: number): Item {
  return { id, sort_order };
}

describe("buildReorderSwap", () => {
  it("swaps distinct adjacent sort_orders", () => {
    const items = [item("a", 0), item("b", 1), item("c", 2)];
    assert.deepEqual(buildReorderSwap(items, "b", "up"), [
      { id: "b", sort_order: 0 },
      { id: "a", sort_order: 1 },
    ]);
  });

  it("renumbers the sibling group when adjacent sort_orders are equal", () => {
    const items = [item("a", 0), item("b", 0), item("c", 0)];
    const updates = buildReorderSwap(items, "a", "down");
    assert.deepEqual(updates, [
      { id: "a", sort_order: 1 },
      { id: "c", sort_order: 2 },
    ]);
  });

  it("uses id tiebreak so equal sort_orders match list display order", () => {
    const items = [item("z", 0), item("m", 0), item("a", 0)];
    // Display order: a, m, z. Move m up → m, a, z; compact skips ids already at index.
    const updates = buildReorderSwap(items, "m", "up");
    assert.deepEqual(updates, [
      { id: "a", sort_order: 1 },
      { id: "z", sort_order: 2 },
    ]);
  });

  it("returns null at list edges", () => {
    const items = [item("a", 0), item("b", 0)];
    assert.equal(buildReorderSwap(items, "a", "up"), null);
    assert.equal(buildReorderSwap(items, "b", "down"), null);
    assert.equal(buildReorderSwap(items, "missing", "down"), null);
  });
});

describe("canReorderUp / canReorderDown", () => {
  it("follows id-tiebroken display order", () => {
    const items = [item("b", 0), item("a", 0)];
    assert.equal(canReorderUp(items, "a"), false);
    assert.equal(canReorderDown(items, "a"), true);
    assert.equal(canReorderUp(items, "b"), true);
    assert.equal(canReorderDown(items, "b"), false);
  });
});
