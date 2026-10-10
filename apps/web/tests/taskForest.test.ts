import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { orderTasksForest } from "../src/taskForest.ts";

type T = { id: string; parent_task_id: string | null; sort_order: number; title: string };

describe("orderTasksForest peerOrder stable (M1)", () => {
  it("keeps server peer order instead of sort_order for roots", () => {
    // API -title order: Alpha only, then Alpha and beta (Z–A).
    // Manual sort_order would put "Alpha and beta" first.
    const items: T[] = [
      { id: "1", parent_task_id: null, sort_order: 2, title: "Alpha only" },
      { id: "2", parent_task_id: null, sort_order: 1, title: "Alpha and beta" },
    ];
    const ordered = orderTasksForest(items, { peerOrder: "stable" });
    assert.deepEqual(
      ordered.map((t) => t.title),
      ["Alpha only", "Alpha and beta"],
    );
    const manual = orderTasksForest(items);
    assert.deepEqual(
      manual.map((t) => t.title),
      ["Alpha and beta", "Alpha only"],
    );
  });

  it("still nests children under parents while preserving peer order", () => {
    const items: T[] = [
      { id: "p2", parent_task_id: null, sort_order: 0, title: "Parent B" },
      { id: "c1", parent_task_id: "p1", sort_order: 0, title: "Child A" },
      { id: "p1", parent_task_id: null, sort_order: 1, title: "Parent A" },
      { id: "c2", parent_task_id: "p1", sort_order: 1, title: "Child B" },
    ];
    const ordered = orderTasksForest(items, { peerOrder: "stable" });
    assert.deepEqual(
      ordered.map((t) => t.id),
      ["p2", "p1", "c1", "c2"],
    );
  });
});
