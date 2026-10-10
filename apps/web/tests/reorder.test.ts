import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  buildReorderSwap,
  canReorderDown,
  canReorderUp,
  compareBySortOrderThenName,
} from "../src/reorder.ts";

type Item = { id: string; sort_order: number };
type Named = Item & { name: string };

function item(id: string, sort_order: number): Item {
  return { id, sort_order };
}

function named(id: string, name: string, sort_order: number): Named {
  return { id, name, sort_order };
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

  it("name tiebreak matches Sidebar saved-view display (M2)", () => {
    // Display (name): Browser mixed, Pagination view, Repair label, Repair project
    // IDs intentionally reverse of name order so id-tiebreak would disagree.
    const items = [
      named("id-pagination", "Pagination view", 100),
      named("id-browser", "Browser mixed", 100),
      named("id-repair-proj", "Repair project", 100),
      named("id-repair-label", "Repair label", 100),
    ];
    assert.equal(canReorderUp(items, "id-browser", compareBySortOrderThenName), false);
    assert.equal(canReorderUp(items, "id-pagination", compareBySortOrderThenName), true);
    // Move Repair project up → swap with Repair label (name neighbor above).
    const updates = buildReorderSwap(
      items,
      "id-repair-proj",
      "up",
      compareBySortOrderThenName,
    );
    assert.ok(updates);
    // Equal ranks → renumber 0..n-1 in post-swap name order:
    // Browser, Pagination, Repair project, Repair label
    const byId = Object.fromEntries(updates.map((u) => [u.id, u.sort_order]));
    assert.equal(byId["id-browser"], 0);
    assert.equal(byId["id-pagination"], 1);
    assert.equal(byId["id-repair-proj"], 2);
    assert.equal(byId["id-repair-label"], 3);
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
