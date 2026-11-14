import assert from "node:assert/strict";
import test from "node:test";

import { resolveRouteMetadata } from "../src/layouts/routeMetadata.ts";

test("resolveRouteMetadata returns a unique, accurate document.title for all 12 manifest routes", () => {
  const cases = [
    { path: "/", expectedTitle: "Sign In | Examination Hub", focus: undefined },
    { path: "/student", expectedTitle: "Examinations | Examination Hub", focus: undefined },
    { path: "/student/exams/exam-101", expectedTitle: "Exam Instructions | Examination Hub", focus: undefined },
    { path: "/student/attempts/attempt-201", expectedTitle: "Active Examination | Examination Hub", focus: true },
    { path: "/student/results/attempt-201", expectedTitle: "Examination Result | Examination Hub", focus: undefined },
    { path: "/admin", expectedTitle: "Overview | Examination Hub", focus: undefined },
    { path: "/admin/exams", expectedTitle: "Examinations | Examination Hub", focus: undefined },
    { path: "/admin/results", expectedTitle: "Results | Examination Hub", focus: undefined },
    { path: "/admin/exams/new", expectedTitle: "Create Examination | Examination Hub", focus: undefined },
    { path: "/admin/exams/exam-101", expectedTitle: "Manage Examination | Examination Hub", focus: undefined },
    { path: "/admin/exams/exam-101/results", expectedTitle: "Examination Results | Examination Hub", focus: undefined },
    { path: "/404-not-found", expectedTitle: "Page Not Found | Examination Hub", focus: undefined },
  ];

  for (const { path, expectedTitle, focus } of cases) {
    const meta = resolveRouteMetadata(path);
    assert.equal(meta.title, expectedTitle, `Unexpected title for ${path}`);
    assert.equal(meta.examFocusMode, focus, `Unexpected examFocusMode for ${path}`);
    assert.ok(meta.announcement.length > 0, `Empty announcement for ${path}`);
  }
});
