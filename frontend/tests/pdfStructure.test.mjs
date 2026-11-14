import assert from "node:assert/strict";
import { test } from "node:test";

import { mergeRegions, renumberAnswers, splitRegions } from "../src/features/admin/pdfStructure.ts";

test("merge joins same-page bounds and retains ordered later pages", () => {
  const merged = mergeRegions(
    [{ page: 1, bbox: [0, 100, 600, 300] }],
    [{ page: 1, bbox: [0, 300, 600, 500] }, { page: 2, bbox: [0, 0, 600, 120] }],
  );
  assert.deepEqual(merged, [
    { page: 1, bbox: [0, 100, 600, 500] },
    { page: 2, bbox: [0, 0, 600, 120] },
  ]);
});

test("split keeps page order and enforces minimum height", () => {
  const [first, second] = splitRegions(
    [{ page: 1, bbox: [0, 100, 600, 300] }, { page: 2, bbox: [0, 0, 600, 150] }],
    200,
  );
  assert.deepEqual(first, [{ page: 1, bbox: [0, 100, 600, 200] }]);
  assert.deepEqual(second, [
    { page: 1, bbox: [0, 200, 600, 300] },
    { page: 2, bbox: [0, 0, 600, 150] },
  ]);
  assert.throws(() => splitRegions(first, 110), /at least 30 pt/);
});

test("renumber shifts following answer-key positions", () => {
  const result = renumberAnswers([
    { position: 1, answer_label: "B" },
    { position: 3, answer_label: null },
    { position: 4, answer_label: "C" },
  ]);
  assert.deepEqual(result.questions.map((q) => q.position), [1, 2, 3]);
  assert.equal(result.normalizedKey, "1. B, 3. C");
});
