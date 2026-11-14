import assert from "node:assert/strict";
import test from "node:test";

import { uniqueIncomingPdfQuestions } from "../src/features/admin/importDedup.ts";

test("adding the same PDF again does not double its questions", () => {
  const first = [1, 2].map((source_number) => ({ source_file_id: "pdf-a", source_number }));
  assert.deepEqual(uniqueIncomingPdfQuestions(first, first), []);
  assert.deepEqual(uniqueIncomingPdfQuestions([], [...first, ...first]), first);
});

test("a different PDF still adds questions, including matching numbers", () => {
  const existing = [{ source_file_id: "pdf-a", source_number: 1 }];
  const incoming = [{ source_file_id: "pdf-a", source_number: 1 }, { source_file_id: "pdf-b", source_number: 1 }];
  assert.deepEqual(uniqueIncomingPdfQuestions(existing, incoming), [incoming[1]]);
});
