import { spawn } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const repoRoot = path.resolve(__dirname, "..", "..");
const frontendRoot = path.resolve(__dirname, "..");
const manifestPath = path.join(repoRoot, "docs", "ui-manifest.md");

function loadPlaywright() {
  const requireFromHere = createRequire(import.meta.url);
  const candidates = [frontendRoot, repoRoot];
  const npxCache = path.join(process.env.LOCALAPPDATA || "", "npm-cache", "_npx");
  if (fs.existsSync(npxCache)) {
    for (const entry of fs.readdirSync(npxCache)) {
      const nm = path.join(npxCache, entry, "node_modules");
      if (fs.existsSync(path.join(nm, "playwright"))) {
        candidates.push(nm);
      }
    }
  }
  for (const base of candidates) {
    try {
      const resolved = requireFromHere.resolve("playwright", { paths: [base] });
      return requireFromHere(resolved);
    } catch {
      // continue
    }
  }
  throw new Error("Could not resolve 'playwright' from workspace or local npx cache.");
}

function loadAxeSource() {
  const requireFromHere = createRequire(import.meta.url);
  const candidates = [frontendRoot, repoRoot];
  const npxCache = path.join(process.env.LOCALAPPDATA || "", "npm-cache", "_npx");
  if (fs.existsSync(npxCache)) {
    for (const entry of fs.readdirSync(npxCache)) {
      const nm = path.join(npxCache, entry, "node_modules");
      if (fs.existsSync(path.join(nm, "axe-core"))) {
        candidates.push(nm);
      }
    }
  }
  for (const base of candidates) {
    try {
      const resolved = requireFromHere.resolve("axe-core/axe.min.js", { paths: [base] });
      return fs.readFileSync(resolved, "utf8");
    } catch {
      // continue
    }
  }
  return null;
}

export function parseRouteManifest(markdownText) {
  const startMarker = "<!-- ROUTE_MANIFEST_START -->";
  const endMarker = "<!-- ROUTE_MANIFEST_END -->";
  const startIdx = markdownText.lastIndexOf(startMarker);
  const endIdx = markdownText.lastIndexOf(endMarker);
  if (startIdx === -1 || endIdx === -1 || endIdx <= startIdx) {
    throw new Error("Could not locate ROUTE_MANIFEST_START/END markers in docs/ui-manifest.md");
  }
  const block = markdownText.slice(startIdx + startMarker.length, endIdx).trim();
  const lines = block
    .split("\n")
    .map((line) => line.trim())
    .filter((line) => line.startsWith("|"));
  if (lines.length < 3) {
    throw new Error("Route manifest table in docs/ui-manifest.md has no data rows.");
  }

  return lines.slice(2).map((line) => {
    const cells = line
      .split("|")
      .slice(1, -1)
      .map((cell) => cell.trim().replace(/^`|`$/g, ""));
    const [rawPath, file, role, layoutUsed, states, dialogs, status] = cells;
    const routePattern = rawPath.startsWith("*") ? "/404-not-found" : rawPath.split(" ")[0];
    return {
      rawPath,
      routePattern,
      file,
      role,
      layoutUsed,
      states,
      dialogs,
      status,
    };
  });
}

function concreteUrlPath(routePattern) {
  return routePattern
    .replace(":examId", "exam-101")
    .replace(":attemptId", "attempt-201");
}

function slugifyRoute(routePattern, role) {
  const clean =
    routePattern === "/"
      ? "root"
      : routePattern
          .replace(/^\//, "")
          .replace(/:([a-zA-Z0-9_]+)/g, "$1")
          .replace(/[^a-zA-Z0-9_-]+/g, "-");
  return `${role}__${clean}`;
}

const SAMPLE_QUESTION_SVG = `<svg xmlns="http://www.w3.org/2000/svg" width="760" height="180" viewBox="0 0 760 180">
  <rect width="760" height="180" rx="8" fill="#ffffff" stroke="#dfe4e8"/>
  <text x="24" y="38" font-family="system-ui, sans-serif" font-size="16" font-weight="600" fill="#18181b">
    Q1. Consider the network topology diagram below. Which link carries VLAN 20 trunk traffic?
  </text>
  <rect x="24" y="56" width="160" height="52" rx="6" fill="#f6f7f8" stroke="#991b1b"/>
  <text x="48" y="87" font-family="system-ui, sans-serif" font-size="14" fill="#18181b">Core Switch A</text>
  <line x1="184" y1="82" x2="310" y2="82" stroke="#b91c1c" stroke-width="3"/>
  <text x="215" y="72" font-family="system-ui, sans-serif" font-size="12" fill="#b91c1c">Link Gi0/1</text>
  <rect x="310" y="56" width="170" height="52" rx="6" fill="#f6f7f8" stroke="#4b5563"/>
  <text x="330" y="87" font-family="system-ui, sans-serif" font-size="14" fill="#18181b">Distribution B</text>
  <text x="24" y="142" font-family="system-ui, sans-serif" font-size="13" fill="#4b5563">
    A. Link Gi0/1    B. Link Fa0/2    C. Loopback0    D. Management0
  </text>
</svg>`;

const SEED_STUDENT_EXAMS = [
  {
    id: "exam-101",
    title: "Data Protection & Cybersecurity Fundamentals",
    description:
      "Core assessment covering encryption standards, access control models, incident response, and regulatory compliance.",
    instructions:
      "Read each multiple-choice question carefully before selecting your answer.\nAll selections are saved automatically to the examination server.\nOnce your timer expires, your sitting is finalized automatically.",
    duration_minutes: 45,
    pass_mark: 70,
    question_limit: 20,
    randomize_questions: true,
    randomize_options: true,
    max_attempts: 2,
    show_result: true,
    question_count: 20,
    attempts_used: 0,
    active_attempt_id: "attempt-201",
    can_start: true,
    published_at: "2026-11-10T09:00:00Z",
  },
  {
    id: "exam-102",
    title: "Cloud Infrastructure & Network Security",
    description:
      "Practical evaluation of VPC segmentation, zero-trust identity boundaries, and TLS certificate lifecycle management.",
    instructions: "Answer all 15 questions within 30 minutes.",
    duration_minutes: 30,
    pass_mark: 75,
    question_limit: 15,
    randomize_questions: true,
    randomize_options: false,
    max_attempts: 1,
    show_result: true,
    question_count: 15,
    attempts_used: 0,
    active_attempt_id: null,
    can_start: true,
    published_at: "2026-11-11T10:30:00Z",
  },
  {
    id: "exam-103",
    title: "Secure Software Development Lifecycle",
    description:
      "OWASP Top 10 mitigation, threat modeling, dependency auditing, and secure authentication session handling.",
    instructions: "Single sitting assessment.",
    duration_minutes: 60,
    pass_mark: 80,
    question_limit: 25,
    randomize_questions: false,
    randomize_options: false,
    max_attempts: 1,
    show_result: false,
    question_count: 25,
    attempts_used: 1,
    active_attempt_id: null,
    can_start: false,
    published_at: "2026-11-05T14:00:00Z",
  },
];

const SEED_STUDENT_ATTEMPTS = [
  {
    attempt_id: "attempt-201",
    exam_id: "exam-101",
    exam_title: "Data Protection & Cybersecurity Fundamentals",
    status: "IN_PROGRESS",
    submission_reason: null,
    started_at: "2026-11-14T02:15:00Z",
    expires_at: "2026-11-14T03:00:00Z",
    submitted_at: null,
    total_questions: 4,
    result_visible: true,
    points_earned: null,
    points_available: null,
    percentage: null,
    passed: null,
  },
  {
    attempt_id: "attempt-200",
    exam_id: "exam-102",
    exam_title: "Cloud Infrastructure & Network Security",
    status: "GRADED",
    submission_reason: "STUDENT_SUBMITTED",
    started_at: "2026-11-12T14:00:00Z",
    expires_at: "2026-11-12T14:30:00Z",
    submitted_at: "2026-11-12T14:24:18Z",
    total_questions: 15,
    result_visible: true,
    points_earned: 13,
    points_available: 15,
    percentage: 86.67,
    passed: true,
  },
  {
    attempt_id: "attempt-199",
    exam_id: "exam-103",
    exam_title: "Secure Software Development Lifecycle",
    status: "SUBMITTED",
    submission_reason: "TIMER_EXPIRED",
    started_at: "2026-11-08T09:00:00Z",
    expires_at: "2026-11-08T10:00:00Z",
    submitted_at: "2026-11-08T10:00:00Z",
    total_questions: 25,
    result_visible: false,
    points_earned: null,
    points_available: null,
    percentage: null,
    passed: null,
  },
];

const SEED_ATTEMPT_DELIVERY = {
  attempt_id: "attempt-201",
  exam_id: "exam-101",
  exam_title: "Data Protection & Cybersecurity Fundamentals",
  duration_minutes: 45,
  status: "IN_PROGRESS",
  started_at: "2026-11-14T02:15:00Z",
  expires_at: "2026-11-14T02:48:30Z",
  server_now: "2026-11-14T02:30:00Z",
  total_questions: 4,
  questions: [
    {
      id: "q-1",
      display_order: 1,
      question_text:
        "Which cryptographic control guarantees both confidentiality and message integrity in TLS 1.3 record protection?",
      points: 2,
      options: [
        { id: "opt-1a", label: "A", option_text: "AES-GCM authenticated encryption (AEAD)" },
        { id: "opt-1b", label: "B", option_text: "Static RSA key exchange without ephemeral Diffie-Hellman" },
        { id: "opt-1c", label: "C", option_text: "Unkeyed SHA-256 message digest alone" },
        { id: "opt-1d", label: "D", option_text: "3DES in Electronic Codebook (ECB) mode" },
      ],
    },
    {
      id: "q-2",
      display_order: 2,
      question_text:
        "Under the principle of least privilege, how should role-based authorization be enforced in a multi-tenant web application?",
      points: 1,
      options: [
        { id: "opt-2a", label: "A", option_text: "By trusting role flags stored in browser localStorage" },
        { id: "opt-2b", label: "B", option_text: "On the backend API against verified server-side identity records" },
        { id: "opt-2c", label: "C", option_text: "By hiding admin links in the CSS stylesheet only" },
        { id: "opt-2d", label: "D", option_text: "By passing ?role=ADMIN in the request query string" },
      ],
    },
    {
      id: "q-3",
      display_order: 3,
      question_text:
        "Refer to the network topology diagram. Which interface carries tagged VLAN 20 trunk traffic?",
      image_urls: ["/api/exams/sources/src-1/questions/1/image"],
      points: 2,
      options: [
        { id: "opt-3a", label: "A", option_text: "Link Gi0/1" },
        { id: "opt-3b", label: "B", option_text: "Link Fa0/2" },
        { id: "opt-3c", label: "C", option_text: "Loopback0" },
        { id: "opt-3d", label: "D", option_text: "Management0" },
      ],
    },
    {
      id: "q-4",
      display_order: 4,
      question_text:
        "What is the primary security benefit of storing short-lived session tokens with HttpOnly and Secure attributes?",
      points: 1,
      options: [
        { id: "opt-4a", label: "A", option_text: "Mitigates token theft via cross-site scripting (XSS) and unencrypted transport" },
        { id: "opt-4b", label: "B", option_text: "Compresses HTTP response payloads automatically" },
        { id: "opt-4c", label: "C", option_text: "Eliminates the need for server-side token signature verification" },
        { id: "opt-4d", label: "D", option_text: "Allows third-party scripts to read the session token" },
      ],
    },
  ],
  saved_answers: {
    "q-1": "opt-1a",
    "q-2": "opt-2b",
    "q-3": null,
    "q-4": null,
  },
};

const SEED_ATTEMPT_RESULT = {
  attempt_id: "attempt-201",
  exam_id: "exam-101",
  exam_title: "Data Protection & Cybersecurity Fundamentals",
  status: "GRADED",
  submission_reason: "STUDENT_SUBMITTED",
  started_at: "2026-11-14T02:00:00Z",
  expires_at: "2026-11-14T02:45:00Z",
  submitted_at: "2026-11-14T02:34:12Z",
  total_questions: 4,
  correct_answers: 3,
  incorrect_answers: 1,
  unanswered_questions: 0,
  points_earned: 5,
  points_available: 6,
  percentage: 83.33,
  pass_mark: 70,
  passed: true,
  result_visible: true,
  show_correct_answers: true,
  student_user_id: "student-1",
  student_email: "ama.mensah@dpcis.edu",
  student_display_name: "Ama Mensah",
  question_review: [
    {
      question_id: "q-1",
      display_order: 1,
      question_text:
        "Which cryptographic control guarantees both confidentiality and message integrity in TLS 1.3 record protection?",
      selected_option_id: "opt-1a",
      correct_option_id: "opt-1a",
      is_correct: true,
      points_earned: 2,
      points_available: 2,
      options: [
        { id: "opt-1a", label: "A", option_text: "AES-GCM authenticated encryption (AEAD)", is_correct: true },
        { id: "opt-1b", label: "B", option_text: "Static RSA key exchange without ephemeral Diffie-Hellman", is_correct: false },
        { id: "opt-1c", label: "C", option_text: "Unkeyed SHA-256 message digest alone", is_correct: false },
        { id: "opt-1d", label: "D", option_text: "3DES in Electronic Codebook (ECB) mode", is_correct: false },
      ],
    },
    {
      question_id: "q-2",
      display_order: 2,
      question_text:
        "Under the principle of least privilege, how should role-based authorization be enforced in a multi-tenant web application?",
      selected_option_id: "opt-2a",
      correct_option_id: "opt-2b",
      is_correct: false,
      points_earned: 0,
      points_available: 1,
      options: [
        { id: "opt-2a", label: "A", option_text: "By trusting role flags stored in browser localStorage", is_correct: false },
        { id: "opt-2b", label: "B", option_text: "On the backend API against verified server-side identity records", is_correct: true },
        { id: "opt-2c", label: "C", option_text: "By hiding admin links in the CSS stylesheet only", is_correct: false },
        { id: "opt-2d", label: "D", option_text: "By passing ?role=ADMIN in the request query string", is_correct: false },
      ],
    },
  ],
};

const SEED_ADMIN_EXAMS = [
  {
    id: "exam-101",
    title: "Data Protection & Cybersecurity Fundamentals",
    description:
      "Core assessment covering encryption standards, access control models, incident response, and regulatory compliance.",
    instructions:
      "Read each multiple-choice question carefully before selecting your answer.",
    duration_minutes: 45,
    pass_mark: 70,
    question_limit: 20,
    randomize_questions: true,
    randomize_options: true,
    max_attempts: 2,
    show_result: true,
    show_correct_answers: true,
    status: "DRAFT",
    created_by: "admin-1",
    created_at: "2026-11-09T08:30:00Z",
    updated_at: "2026-11-13T16:45:00Z",
    published_at: null,
    closed_at: null,
    question_count: 3,
  },
  {
    id: "exam-102",
    title: "Cloud Infrastructure & Network Security",
    description:
      "Practical evaluation of VPC segmentation, zero-trust identity boundaries, and TLS certificate lifecycle management.",
    instructions: "Answer all 15 questions within 30 minutes.",
    duration_minutes: 30,
    pass_mark: 75,
    question_limit: 15,
    randomize_questions: true,
    randomize_options: false,
    max_attempts: 1,
    show_result: true,
    show_correct_answers: true,
    status: "PUBLISHED",
    created_by: "admin-1",
    created_at: "2026-11-10T10:00:00Z",
    updated_at: "2026-11-12T11:20:00Z",
    published_at: "2026-11-11T10:30:00Z",
    closed_at: null,
    question_count: 15,
  },
  {
    id: "exam-103",
    title: "Secure Software Development Lifecycle",
    description:
      "OWASP Top 10 mitigation, threat modeling, dependency auditing, and secure authentication session handling.",
    instructions: "Single sitting assessment.",
    duration_minutes: 60,
    pass_mark: 80,
    question_limit: 25,
    randomize_questions: false,
    randomize_options: false,
    max_attempts: 1,
    show_result: false,
    show_correct_answers: false,
    status: "CLOSED",
    created_by: "admin-1",
    created_at: "2026-11-01T09:00:00Z",
    updated_at: "2026-11-08T18:00:00Z",
    published_at: "2026-11-05T14:00:00Z",
    closed_at: "2026-11-08T18:00:00Z",
    question_count: 25,
  },
];

const SEED_ADMIN_EXAM_DETAIL = {
  ...SEED_ADMIN_EXAMS[0],
  questions: [
    {
      id: "q-1",
      question_text:
        "Which cryptographic control guarantees both confidentiality and message integrity in TLS 1.3 record protection?",
      position: 1,
      points: 2,
      options: [
        { id: "opt-1a", label: "A", option_text: "AES-GCM authenticated encryption (AEAD)", is_correct: true, position: 1 },
        { id: "opt-1b", label: "B", option_text: "Static RSA key exchange without ephemeral Diffie-Hellman", is_correct: false, position: 2 },
        { id: "opt-1c", label: "C", option_text: "Unkeyed SHA-256 message digest alone", is_correct: false, position: 3 },
        { id: "opt-1d", label: "D", option_text: "3DES in Electronic Codebook (ECB) mode", is_correct: false, position: 4 },
      ],
    },
    {
      id: "q-2",
      question_text:
        "Refer to the network topology diagram. Which interface carries tagged VLAN 20 trunk traffic?",
      source_file_id: "src-1",
      source_number: 1,
      image_urls: ["/api/exams/sources/src-1/questions/1/image"],
      image_regions: [{ page: 1, bbox: [36, 120, 560, 290] }],
      position: 2,
      points: 2,
      options: [
        { id: "opt-2a", label: "A", option_text: "Link Gi0/1", is_correct: true, position: 1 },
        { id: "opt-2b", label: "B", option_text: "Link Fa0/2", is_correct: false, position: 2 },
        { id: "opt-2c", label: "C", option_text: "Loopback0", is_correct: false, position: 3 },
        { id: "opt-2d", label: "D", option_text: "Management0", is_correct: false, position: 4 },
      ],
    },
  ],
};

const SEED_ADMIN_RESULTS = {
  exam_id: "exam-101",
  exam_title: "Data Protection & Cybersecurity Fundamentals",
  pass_mark: 70,
  total_attempts: 3,
  summary: {
    completed_attempts: 2,
    average_percentage: 79.17,
    highest_percentage: 91.67,
    lowest_percentage: 66.67,
    pass_rate: 50,
  },
  attempts: [
    {
      attempt_id: "attempt-201",
      user_id: "student-1",
      email: "ama.mensah@dpcis.edu",
      display_name: "Ama Mensah",
      status: "GRADED",
      submission_reason: "STUDENT_SUBMITTED",
      started_at: "2026-11-14T02:00:00Z",
      expires_at: "2026-11-14T02:45:00Z",
      submitted_at: "2026-11-14T02:34:12Z",
      total_questions: 12,
      correct_answers: 11,
      incorrect_answers: 1,
      unanswered_questions: 0,
      points_earned: 11,
      points_available: 12,
      percentage: 91.67,
      passed: true,
    },
    {
      attempt_id: "attempt-202",
      user_id: "student-2",
      email: "kofi.owusu@dpcis.edu",
      display_name: "Kofi Owusu",
      status: "GRADED",
      submission_reason: "TIMER_EXPIRED",
      started_at: "2026-11-13T15:00:00Z",
      expires_at: "2026-11-13T15:45:00Z",
      submitted_at: "2026-11-13T15:45:00Z",
      total_questions: 12,
      correct_answers: 8,
      incorrect_answers: 3,
      unanswered_questions: 1,
      points_earned: 8,
      points_available: 12,
      percentage: 66.67,
      passed: false,
    },
    {
      attempt_id: "attempt-203",
      user_id: "student-3",
      email: "esther.adjei@dpcis.edu",
      display_name: "Esther Adjei",
      status: "IN_PROGRESS",
      submission_reason: null,
      started_at: "2026-11-14T02:20:00Z",
      expires_at: "2026-11-14T03:05:00Z",
      submitted_at: null,
      total_questions: 12,
      correct_answers: 0,
      incorrect_answers: 0,
      unanswered_questions: 7,
      points_earned: 0,
      points_available: 12,
      percentage: 0,
      passed: false,
    },
  ],
};

function installMockApi(page, stateRef) {
  const jwt = "eyJhbGciOiJub25lIn0.eyJzdWIiOiJ1c2VyLTEifQ.mocksignature";

  return page.route("**/*", async (route) => {
    const { role, scenario = "ready" } = stateRef;
    const req = route.request();
    const url = new URL(req.url());
    const pathname = url.pathname;

    // 1. Mock Neon Auth endpoints (neondb.io or /neon-auth)
    if (
      url.hostname.includes("neon.tech") ||
      url.hostname.includes("neondb") ||
      pathname.includes("/neondb/auth") ||
      pathname.endsWith("/get-session") ||
      pathname.endsWith("/token")
    ) {
      if (pathname.endsWith("/get-session")) {
        if (role === "public") {
          return route.fulfill({
            status: 200,
            contentType: "application/json",
            body: JSON.stringify(null),
          });
        }
        return route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            session: {
              id: "sess-100",
              userId: role === "admin" ? "admin-1" : "student-1",
              token: jwt,
              expiresAt: "2099-01-01T00:00:00.000Z",
            },
            user: {
              id: role === "admin" ? "admin-1" : "student-1",
              name: role === "admin" ? "Dr. Kwame Mensah" : "Ama Mensah",
              email: role === "admin" ? "kwame.mensah@dpcis.edu" : "ama.mensah@dpcis.edu",
            },
          }),
        });
      }
      if (pathname.endsWith("/token")) {
        return route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({ token: role === "public" ? null : jwt }),
        });
      }
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ ok: true }),
      });
    }

    // Only intercept backend API calls
    const isApiCall =
      pathname === "/health" ||
      pathname === "/auth/me" ||
      pathname === "/api/v1/auth/me" ||
      pathname.startsWith("/api/");
    if (!isApiCall) {
      return route.continue();
    }

    if (
      scenario === "loading" &&
      pathname !== "/auth/me" &&
      pathname !== "/api/v1/auth/me" &&
      pathname !== "/health"
    ) {
      await new Promise((r) => setTimeout(r, 600));
    }

    if (pathname === "/health") {
      if (scenario === "error" && role === "public") {
        return route.fulfill({ status: 503, contentType: "application/json", body: JSON.stringify({ detail: "Service unavailable" }) });
      }
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ status: "ok", service: "examination-hub-api", timestamp: "2026-11-14T02:30:00Z" }),
      });
    }

    if (pathname === "/auth/me" || pathname === "/api/v1/auth/me") {
      if (role === "public") {
        return route.fulfill({ status: 401, contentType: "application/json", body: JSON.stringify({ detail: "Not authenticated" }) });
      }
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          user_id: role === "admin" ? "admin-1" : "student-1",
          auth_subject: role === "admin" ? "admin-1" : "student-1",
          email: role === "admin" ? "kwame.mensah@dpcis.edu" : "ama.mensah@dpcis.edu",
          display_name: role === "admin" ? "Dr. Kwame Mensah" : "Ama Mensah",
          role: role === "admin" ? "ADMIN" : "STUDENT",
        }),
      });
    }

    if (scenario === "error") {
      return route.fulfill({
        status: 500,
        contentType: "application/json",
        body: JSON.stringify({ detail: "Unable to communicate with the examination service. Please try again." }),
      });
    }

    // Cropped PDF question image endpoint
    if (pathname.endsWith("/image")) {
      return route.fulfill({
        status: 200,
        contentType: "image/svg+xml",
        body: SAMPLE_QUESTION_SVG,
      });
    }

    // Student endpoints
    if (pathname === "/api/exams") {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(scenario === "empty" ? [] : SEED_STUDENT_EXAMS),
      });
    }

    if (pathname === "/api/student/attempts") {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(scenario === "empty" ? [] : SEED_STUDENT_ATTEMPTS),
      });
    }

    if (pathname.startsWith("/api/exams/") && !pathname.endsWith("/attempts")) {
      const exam =
        scenario === "empty"
          ? { ...SEED_STUDENT_EXAMS[0], description: null, instructions: null, active_attempt_id: null }
          : SEED_STUDENT_EXAMS[0];
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(exam),
      });
    }

    if (pathname.startsWith("/api/attempts/") && pathname.endsWith("/result")) {
      if (scenario === "in-progress-409") {
        return route.fulfill({
          status: 409,
          contentType: "application/json",
          body: JSON.stringify({
            detail: "This examination attempt is still in progress and has not been finalized yet.",
          }),
        });
      }
      if (scenario === "empty" || scenario === "score-hidden") {
        return route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            attempt_id: "attempt-201",
            exam_id: "exam-101",
            exam_title: "Data Protection & Cybersecurity Fundamentals",
            status: "SUBMITTED",
            submission_reason: "STUDENT_SUBMITTED",
            started_at: "2026-11-14T02:00:00Z",
            expires_at: "2026-11-14T02:45:00Z",
            submitted_at: "2026-11-14T02:34:12Z",
            total_questions: 20,
            result_visible: false,
            show_correct_answers: false,
            message: "Your submission has been recorded. Results will be released by your instructor.",
          }),
        });
      }
      if (scenario === "failed-result") {
        return route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            ...SEED_ATTEMPT_RESULT,
            correct_answers: 1,
            incorrect_answers: 3,
            unanswered_questions: 0,
            points_earned: 1,
            points_available: 6,
            percentage: 16.67,
            passed: false,
            show_correct_answers: true,
          }),
        });
      }
      if (scenario === "review-disabled") {
        return route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            ...SEED_ATTEMPT_RESULT,
            show_correct_answers: false,
            question_review: [],
          }),
        });
      }
      if (scenario === "time-expired-result") {
        return route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            ...SEED_ATTEMPT_RESULT,
            submission_reason: "TIMER_EXPIRED",
            correct_answers: 1,
            incorrect_answers: 2,
            unanswered_questions: 1,
            points_earned: 1,
            points_available: 6,
            percentage: 16.67,
            passed: false,
          }),
        });
      }
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(SEED_ATTEMPT_RESULT),
      });
    }

    if (pathname.startsWith("/api/attempts/")) {
      if (scenario === "time-expired") {
        return route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            ...SEED_ATTEMPT_DELIVERY,
            expires_at: "2026-11-14T02:30:00Z",
            server_now: "2026-11-14T02:30:05Z",
          }),
        });
      }
      const delivery =
        scenario === "empty"
          ? { ...SEED_ATTEMPT_DELIVERY, total_questions: 0, questions: [], saved_answers: {} }
          : SEED_ATTEMPT_DELIVERY;
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(delivery),
      });
    }

    // Admin endpoints
    if (pathname === "/api/admin/exams") {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(scenario === "empty" ? [] : SEED_ADMIN_EXAMS),
      });
    }

    if (pathname === "/api/admin/exams/parse-questions") {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          valid_questions: [
            {
              question_text: "Which protocol operates at Layer 4 of the OSI model to provide reliable byte-stream delivery?",
              position: 1,
              points: 1,
              options: [
                { label: "A", option_text: "Transmission Control Protocol (TCP)" },
                { label: "B", option_text: "Internet Protocol (IP)" },
                { label: "C", option_text: "Address Resolution Protocol (ARP)" },
                { label: "D", option_text: "Internet Control Message Protocol (ICMP)" },
              ],
              answer_label: "A",
              valid: true,
              errors: [],
            },
          ],
          invalid_questions: [],
          errors: [],
          total_blocks: 1,
          valid_count: 1,
          error_count: 0,
        }),
      });
    }

    if (pathname.startsWith("/api/admin/exams/") && pathname.endsWith("/results")) {
      const results =
        scenario === "empty"
          ? {
              ...SEED_ADMIN_RESULTS,
              total_attempts: 0,
              summary: {
                completed_attempts: 0,
                average_percentage: null,
                highest_percentage: null,
                lowest_percentage: null,
                pass_rate: null,
              },
              attempts: [],
            }
          : SEED_ADMIN_RESULTS;
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(results),
      });
    }

    if (pathname.startsWith("/api/admin/exams/")) {
      if (scenario === "published-locked") {
        return route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            ...SEED_ADMIN_EXAM_DETAIL,
            status: "PUBLISHED",
            published_at: "2026-11-11T10:30:00Z",
          }),
        });
      }
      if (scenario === "closed-locked") {
        return route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            ...SEED_ADMIN_EXAM_DETAIL,
            status: "CLOSED",
            published_at: "2026-11-05T14:00:00Z",
            closed_at: "2026-11-08T18:00:00Z",
          }),
        });
      }
      const detail =
        scenario === "empty"
          ? { ...SEED_ADMIN_EXAM_DETAIL, question_count: 0, questions: [] }
          : SEED_ADMIN_EXAM_DETAIL;
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(detail),
      });
    }

    if (pathname.startsWith("/api/admin/attempts/")) {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(SEED_ATTEMPT_RESULT),
      });
    }

    return route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({}),
    });
  });
}

async function startViteServer(port = 5179) {
  process.env.VITE_API_BASE_URL = "http://127.0.0.1:8000";
  process.env.VITE_NEON_AUTH_URL = "https://mock-auth.neon.tech/neondb/auth";
  const requireFromFrontend = createRequire(path.join(frontendRoot, "package.json"));
  const viteEntry = requireFromFrontend.resolve("vite");
  const viteMod = await import(
    new URL(`file:///${viteEntry.replace(/\\/g, "/")}`).href
  );
  const distDir = path.join(frontendRoot, "node_modules", ".vite-visual-walk-dist");
  await viteMod.build({
    root: frontendRoot,
    configFile: path.join(frontendRoot, "vite.config.ts"),
    logLevel: "error",
    define: {
      "import.meta.env.VITE_API_BASE_URL": JSON.stringify("http://127.0.0.1:8000"),
      "import.meta.env.VITE_NEON_AUTH_URL": JSON.stringify("https://mock-auth.neon.tech/neondb/auth"),
    },
    build: {
      outDir: distDir,
      emptyOutDir: true,
    },
  });

  const http = await import("node:http");
  const mimeTypes = {
    ".html": "text/html; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".json": "application/json",
    ".woff2": "font/woff2",
  };

  const server = http.createServer((req, res) => {
    const reqUrl = new URL(req.url || "/", `http://127.0.0.1:${port}`);
    const safeRel = path.normalize(decodeURIComponent(reqUrl.pathname)).replace(/^(\.\.(\/|\\|$))+/, "");
    let filePath = path.join(distDir, safeRel);
    if (!fs.existsSync(filePath) || fs.statSync(filePath).isDirectory()) {
      filePath = path.join(distDir, "index.html");
    }
    const ext = path.extname(filePath).toLowerCase();
    res.writeHead(200, { "Content-Type": mimeTypes[ext] || "application/octet-stream" });
    fs.createReadStream(filePath).pipe(res);
  });

  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  const address = server.address();
  const boundPort = typeof address === "object" && address ? address.port : port;
  const baseUrl = `http://127.0.0.1:${boundPort}`;
  return {
    server: {
      close: () => new Promise((resolve) => server.close(() => resolve())),
    },
    baseUrl,
  };
}

async function main() {
  const modeArg = process.argv.find((a) => a.startsWith("--mode="));
  const mode = modeArg ? modeArg.split("=")[1] : "before";
  const outDir = path.join(repoRoot, "docs", "ui-screenshots", mode);
  if (fs.existsSync(outDir)) {
    for (const f of fs.readdirSync(outDir)) {
      fs.unlinkSync(path.join(outDir, f));
    }
  } else {
    fs.mkdirSync(outDir, { recursive: true });
  }

  const manifestText = fs.readFileSync(manifestPath, "utf8");
  const routes = parseRouteManifest(manifestText);
  console.log(`Parsed ${routes.length} routes from docs/ui-manifest.md -> outputting to ${outDir}`);

  const { chromium } = loadPlaywright();
  const axeSource = loadAxeSource();
  const { server: viteServer, baseUrl } = await startViteServer(5179);

  const viewports = [
    { width: 1440, height: 900 },
    { width: 1024, height: 800 },
    { width: 768, height: 900 },
    { width: 390, height: 844 },
  ];
  const routesWith360 = new Set([
    "/",
    "/student/attempts/:attemptId",
    "/student/results/:attemptId",
    "/admin/exams",
  ]);

  const report = {
    mode,
    capturedAt: new Date().toISOString(),
    routesCount: routes.length,
    screenshots: [],
    overflowFailures: [],
    consoleErrors: [],
    axeAudit: [],
  };

  async function runAxeAudit(page, routePattern, stateLabel) {
    if (!axeSource) return;
    try {
      await page.addScriptTag({ content: axeSource });
      const results = await page.evaluate(async () => {
        // @ts-ignore
        const res = await window.axe.run(document, {
          runOnly: { type: "tag", values: ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"] },
        });
        return res.violations.map((v) => ({
          id: v.id,
          impact: v.impact,
          description: v.description,
          nodes: v.nodes.length,
        }));
      });
      const seriousOrCritical = results.filter(
        (v) => v.impact === "serious" || v.impact === "critical",
      );
      report.axeAudit.push({
        route: routePattern,
        state: stateLabel,
        seriousCount: seriousOrCritical.filter((v) => v.impact === "serious").length,
        criticalCount: seriousOrCritical.filter((v) => v.impact === "critical").length,
        totalViolations: results.length,
        violations: seriousOrCritical,
      });
    } catch (err) {
      report.axeAudit.push({
        route: routePattern,
        state: stateLabel,
        seriousCount: 0,
        criticalCount: 0,
        error: String(err),
      });
    }
  }

  const browser = await chromium.launch({
    headless: true,
    executablePath: "C:/Program Files/Google/Chrome/Application/chrome.exe",
  });
  try {
    const stateRef = { role: "public", scenario: "ready" };
    const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
    const page = await context.newPage();
    page.on("pageerror", (err) => {
      report.consoleErrors.push({ route: stateRef.currentRoute, error: String(err) });
    });
    await installMockApi(page, stateRef);

    for (const entry of routes) {
      const urlPath = concreteUrlPath(entry.routePattern);
      const slug = slugifyRoute(entry.routePattern, entry.role);
      stateRef.currentRoute = entry.routePattern;
      console.log(`Capturing route ${entry.routePattern} (${entry.role})...`);

      // 1. Capture all required viewports in ready/default state (+ 360w where specified)
      const routeViewports = routesWith360.has(entry.routePattern)
        ? [...viewports, { width: 360, height: 800 }]
        : viewports;
      for (const vp of routeViewports) {
        stateRef.role = entry.role;
        stateRef.scenario = "ready";
        await page.setViewportSize(vp);
        await page.goto(`${baseUrl}${urlPath}`, { waitUntil: "domcontentloaded" });
        await page.waitForTimeout(250);

        const metrics = await page.evaluate(() => ({
          scrollWidth: document.documentElement.scrollWidth,
          innerWidth: window.innerWidth,
        }));
        if (metrics.scrollWidth > metrics.innerWidth + 1) {
          report.overflowFailures.push({
            route: entry.routePattern,
            state: "ready",
            viewport: vp.width,
            scrollWidth: metrics.scrollWidth,
            innerWidth: metrics.innerWidth,
          });
        }

        const fileName = `${slug}__ready__${vp.width}w.png`;
        const filePath = path.join(outDir, fileName);
        await page.screenshot({ path: filePath, fullPage: true });
        report.screenshots.push(fileName);
        if (vp.width === 1440) {
          await runAxeAudit(page, entry.routePattern, "ready");
        }
      }

      // 2. Capture loading, empty, and error states at 1440w
      await page.setViewportSize({ width: 1440, height: 900 });
      for (const state of ["loading", "empty", "error"]) {
        if (entry.routePattern === "/404-not-found" && state !== "error") {
          continue;
        }
        stateRef.role = entry.role;
        stateRef.scenario = state;
        await page.goto(`${baseUrl}${urlPath}`, { waitUntil: "domcontentloaded" });
        await page.waitForTimeout(state === "loading" ? 120 : 250);

        const fileName = `${slug}__${state}__1440w.png`;
        await page.screenshot({ path: path.join(outDir, fileName), fullPage: true });
        report.screenshots.push(fileName);
        await runAxeAudit(page, entry.routePattern, state);
      }

      // 3. Route-specific interactive states / dialogs / domain states at 1440w
      stateRef.role = entry.role;
      stateRef.scenario = "ready";
      if (entry.routePattern === "/") {
        await page.goto(`${baseUrl}/`, { waitUntil: "domcontentloaded" });
        await page.waitForTimeout(250);
        const signUpToggle = page.getByRole("button", { name: /create one/i });
        if (await signUpToggle.count()) {
          await signUpToggle.click();
          await page.waitForTimeout(120);
          const fileName = `${slug}__signup__1440w.png`;
          await page.screenshot({ path: path.join(outDir, fileName), fullPage: true });
          report.screenshots.push(fileName);
          await runAxeAudit(page, entry.routePattern, "signup");
        }
      }

      if (entry.routePattern === "/student/attempts/:attemptId") {
        await page.goto(`${baseUrl}${urlPath}`, { waitUntil: "domcontentloaded" });
        await page.waitForTimeout(250);
        // Text-only question (Q1) explicit state capture
        const textOnlyFile = `${slug}__text-question__1440w.png`;
        await page.screenshot({ path: path.join(outDir, textOnlyFile), fullPage: true });
        report.screenshots.push(textOnlyFile);

        // Navigate to Q3 (PDF cropped image question)
        const q3Btn = page.getByRole("button", { name: /Question 3/i }).first();
        if (await q3Btn.count()) {
          await q3Btn.click();
          await page.waitForTimeout(250);
          const pdfQFile = `${slug}__pdf-image-question__1440w.png`;
          await page.screenshot({ path: path.join(outDir, pdfQFile), fullPage: true });
          report.screenshots.push(pdfQFile);
          await runAxeAudit(page, entry.routePattern, "pdf-image-question");
        }

        const allQBtn = page.getByRole("button", { name: /question navigator|all questions/i }).first();
        if (await allQBtn.count()) {
          await allQBtn.click();
          await page.waitForTimeout(120);
          const navFile = `${slug}__dialog-navigator__1440w.png`;
          await page.screenshot({ path: path.join(outDir, navFile) });
          report.screenshots.push(navFile);
          await runAxeAudit(page, entry.routePattern, "dialog-navigator");
          await page.keyboard.press("Escape");
          await page.waitForTimeout(100);
        }
        const submitBtn = page.getByRole("button", { name: /review & submit|submit exam/i }).first();
        if (await submitBtn.count()) {
          await submitBtn.click();
          await page.waitForTimeout(120);
          const submitFile = `${slug}__dialog-submit__1440w.png`;
          await page.screenshot({ path: path.join(outDir, submitFile) });
          report.screenshots.push(submitFile);
          await runAxeAudit(page, entry.routePattern, "dialog-submit");
        }

        // Time expired attempt banner
        stateRef.scenario = "time-expired";
        await page.goto(`${baseUrl}${urlPath}`, { waitUntil: "domcontentloaded" });
        await page.waitForTimeout(250);
        const expiredFile = `${slug}__time-expired__1440w.png`;
        await page.screenshot({ path: path.join(outDir, expiredFile), fullPage: true });
        report.screenshots.push(expiredFile);
        await runAxeAudit(page, entry.routePattern, "time-expired");
      }

      if (entry.routePattern === "/student/results/:attemptId") {
        for (const subScenario of [
          "failed-result",
          "review-disabled",
          "score-hidden",
          "in-progress-409",
          "time-expired-result",
        ]) {
          stateRef.scenario = subScenario;
          await page.goto(`${baseUrl}${urlPath}`, { waitUntil: "domcontentloaded" });
          await page.waitForTimeout(250);
          const subFile = `${slug}__${subScenario}__1440w.png`;
          await page.screenshot({ path: path.join(outDir, subFile), fullPage: true });
          report.screenshots.push(subFile);
          await runAxeAudit(page, entry.routePattern, subScenario);
        }
      }

      if (entry.routePattern === "/admin/exams/:examId") {
        await page.goto(`${baseUrl}${urlPath}`, { waitUntil: "domcontentloaded" });
        await page.waitForTimeout(250);
        const questionsTab = page.getByRole("tab", { name: /questions/i }).or(page.getByRole("button", { name: /questions/i })).first();
        if (await questionsTab.count()) {
          await questionsTab.click();
          await page.waitForTimeout(200);
          const qTabFile = `${slug}__tab-questions__1440w.png`;
          await page.screenshot({ path: path.join(outDir, qTabFile), fullPage: true });
          report.screenshots.push(qTabFile);
          await runAxeAudit(page, entry.routePattern, "tab-questions");
        }

        for (const lockScenario of ["published-locked", "closed-locked"]) {
          stateRef.scenario = lockScenario;
          await page.goto(`${baseUrl}${urlPath}`, { waitUntil: "domcontentloaded" });
          await page.waitForTimeout(250);
          const lockFile = `${slug}__${lockScenario}__1440w.png`;
          await page.screenshot({ path: path.join(outDir, lockFile), fullPage: true });
          report.screenshots.push(lockFile);
          await runAxeAudit(page, entry.routePattern, lockScenario);
        }
      }

      if (entry.routePattern === "/admin/exams/:examId/results") {
        await page.goto(`${baseUrl}${urlPath}`, { waitUntil: "domcontentloaded" });
        await page.waitForTimeout(250);
        const viewBtn = page.getByRole("button", { name: /view breakdown|view details/i }).first();
        if (await viewBtn.count()) {
          await viewBtn.click();
          await page.waitForTimeout(200);
          const dlgFile = `${slug}__dialog-attempt-detail__1440w.png`;
          await page.screenshot({ path: path.join(outDir, dlgFile) });
          report.screenshots.push(dlgFile);
          await runAxeAudit(page, entry.routePattern, "dialog-attempt-detail");
        }
      }
    }
    await context.close();
  } finally {
    await browser.close();
    await viteServer.close();
  }

  const summaryPath = path.join(outDir, "visual-walk-report.json");
  fs.writeFileSync(summaryPath, JSON.stringify(report, null, 2));
  console.log(`Captured ${report.screenshots.length} screenshots in ${outDir}`);
  console.log(`Overflow failures: ${report.overflowFailures.length}, Page errors: ${report.consoleErrors.length}`);
}

if (process.argv[1] && path.resolve(process.argv[1]) === __filename) {
  main().catch((err) => {
    console.error(err);
    process.exit(1);
  });
}
