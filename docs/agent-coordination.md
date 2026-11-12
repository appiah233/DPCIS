# Examination Hub — Multi-Agent & Cline Coordination Ledger

> **Workspace:** `C:\Users\EricAppiahOwusu\Music\DPCIS`  
> **Governance:** Canonical rules live in `AGENTS.md`. Both the 12 Antigravity subagents and **Cline (`EXTERNAL PEER AGENT`)** MUST inspect this ledger before modifying shared files, migrations, API contracts, or frontend auth/routes.  
> **Security Rule (`RULE 23`):** NEVER place database URLs, passwords, JWTs, API keys, OAuth secrets, AWS credentials, or Clerk references in this file.

---

## 1. Non-Overlapping Ownership Map

| Agent / Peer | Role & Scope | Owned Files / Directories |
|---|---|---|
| **Cline (`EXTERNAL PEER AGENT`)** | Independent peer engineering worker (`RULE 17`) | Active/prior shared backend & auth contributions: `backend/alembic/versions/0002_examination_schema.py`, `0003_attempt_option_order.py`, `backend/app/exams/{models.py,schemas.py,service.py,parser.py}`, `backend/app/attempts/{models.py,schemas.py,service.py}`, `backend/app/auth/{__init__.py,dependencies.py}`, `backend/app/database/__init__.py`, `frontend/src/lib/{auth.ts,api.ts}`, `frontend/src/features/auth/{AuthBoundary.tsx,ProtectedRoute.tsx}`, `frontend/src/App.tsx` |
| **ArchitectAgent** | Architecture governance, cross-stack contract verification, conflict resolution (`RULE 21`), ledger normalization | `AGENTS.md`, `GEMINI.md`, `docs/agent-coordination.md`, `docs/handoffs/*`, shared API & schema contracts |
| **DatabaseAgent** | SQLAlchemy `Base`, session management, `application_users` model, additive Alembic migrations (`0004+`), DB indexes | `backend/app/database/*`, `backend/app/users/models.py`, `backend/alembic/env.py`, `backend/alembic/versions/0004_exam_closed_at_and_indexes.py`+ (never rewrite `0001`–`0004`) |
| **AuthSecurityAgent** | Neon Managed Better Auth JWKS verification, `AuthIdentity`, RBAC dependencies, `/auth/me`, frontend `AuthProvider` & fail-closed guards | `backend/app/auth/*`, `backend/app/users/service.py`, `backend/app/config.py`, `frontend/src/lib/auth.ts`, `frontend/src/features/auth/*` |
| **QuestionParserAgent** | Pure deterministic MCQ text parser & parser validation rules/tests | `backend/app/exams/parser.py`, `backend/tests/test_parser.py` |
| **ExaminationBackendAgent** | Admin exam CRUD, question persistence, publish/close state machine, student exam listing DTOs | `backend/app/exams/{models.py,schemas.py,service.py,router.py}` (excluding `parser.py`), `backend/tests/test_exams.py` |
| **AttemptEngineAgent** | Attempt lifecycle (`start`, `resume`, `delivery`, `autosave`, `submit`, history), concurrency locks, `attempt_questions` & `student_answers` | `backend/app/attempts/{models.py,schemas.py,service.py,router.py}`, `backend/tests/test_attempts.py` |
| **GradingTimerAgent** | Pure deterministic MCQ grading, server-authoritative UTC expiry math, idempotent finalization, `show_result`/`show_correct_answers` gating, admin result summaries | `backend/app/attempts/grading.py`, grading/timer sections of `backend/app/attempts/service.py`, `backend/tests/test_grading_timer.py` |
| **StudentWebAgent** | Student dashboard, exam instructions, timed MCQ runner (`useAttemptRunner`), autosave UX, isolated result view | `frontend/src/features/student/*`, student route pages (`StudentDashboardPage.tsx`, `StudentExamInstructionsPage.tsx`, `StudentAttemptPage.tsx`, `StudentResultPage.tsx`), `frontend/src/types/studentExam.ts` |
| **AdminWebAgent** | Admin exam builder, raw-text parser preview UI, publish/close controls, results oversight tables & attempt breakdown modal | `frontend/src/features/admin/*`, admin route pages (`AdminDashboardPage.tsx`, `AdminExamNewPage.tsx`, `AdminExamEditorPage.tsx`, `AdminExamResultsPage.tsx`), `frontend/src/types/adminExam.ts` |
| **ResponsiveDesignAgent** | `RULE 13` design system tokens, accessible shared UI primitives, keyboard navigation, `320px`–`1440px+` layout integrity | `frontend/src/index.css`, `frontend/src/components/*`, `frontend/src/layouts/*`, `frontend/src/types/foundation.ts` |
| **DevOpsDeploymentAgent** | Env templates sanitization, Docker, GitHub Actions CI, `buildspec.yml`, `vercel.json`, AWS CodePipeline/App Runner/ECR & Vercel readiness | `.env.example`, `backend/.env.example`, `frontend/.env.example`, `.gitignore`, `README.md`, `backend/Dockerfile`, `backend/.dockerignore`, `.github/workflows/ci.yml`, `buildspec.yml`, `frontend/vercel.json`, `docs/deployment-aws-vercel.md` |
| **TestingVerificationAgent** | Independent adversarial verification: Ruff/Pytest/Alembic checks, Playwright/Chrome DevTools responsive & E2E verification, security & secret/Clerk scans | `backend/tests/*` (`conftest.py`, `test_config.py`, `test_database_foundation.py`, `test_health_and_root.py`, `test_auth.py`, `test_parser.py`, `test_exams.py`, `test_attempts.py`, `test_grading_timer.py`, `test_security_auth_rbac.py`, `test_security_idor_and_leakage.py`, `test_security_timer_and_concurrency.py`, `test_e2e_workflows_and_grading.py`), future `frontend` Vitest & Playwright suites |

---

## 2. Active Workstream Coordination Ledger

| WORKSTREAM | OWNER | STATUS | FILES/DIRECTORIES | DEPENDENCIES | LAST UPDATE | BLOCKER | HANDOFF NOTES |
|---|---|---|---|---|---|---|---|
| **Architecture & Ledger Governance** | `ArchitectAgent` | `VERIFIED` | `docs/agent-coordination.md`, `AGENTS.md`, `GEMINI.md`, `backend/app/main.py` | Stage 12 cross-stack audit; Stage 13–14 security/concurrency/UI fixes | 2026-11-12 | None | Cross-stack contract, HTTP middleware ordering (`CORSMiddleware` outer + HTTP 500 security/CORS header retention), `ApiClientError` (`code`/`payload`), and ledger normalized cleanly. |
| **Examination DB Schema & Migrations** | `DatabaseAgent` + `Cline (EXTERNAL PEER AGENT)` | `VERIFIED_OFFLINE` | `backend/alembic/versions/{0001..0004}`, `backend/alembic/env.py`, `backend/app/database/*`, `backend/app/users/models.py` | Dexta Global Neon project (`noisy-boat-95673317`) | 2026-11-12 | **`LIVE NEON = BLOCKED`**: Dexta Global `noisy-boat-95673317` currently has only the `production` branch, and active Neon MCP key maps to personal org. | `0001`–`0004` linear chain (`0004_exam_closed_at_and_indexes.py`) verified offline via `alembic heads`, `alembic history`, `alembic upgrade head --sql`, and `test_database_foundation.py`. **Do NOT rewrite `0001`–`0004`.** |
| **Auth, Identity & RBAC Boundary** | `AuthSecurityAgent` + `Cline (EXTERNAL PEER AGENT)` | `VERIFIED` | `backend/app/auth/*`, `backend/app/users/service.py`, `backend/app/config.py`, `backend/app/main.py` (`/auth/me`), `frontend/src/lib/auth.ts`, `frontend/src/features/auth/*` | `application_users` table; Neon Managed Better Auth | 2026-11-12 | Live Neon Auth smoke test deferred until non-prod `testing` Neon branch is created. | Includes `AuthIdentity.user_id: UUID`, atomic `upsert_application_user`, `STUDENT` auto-provisioning in `require_student`, fail-closed `require_admin` & `ProtectedRoute.tsx`, and `createInternalNeonAuth` 3-segment JWT extraction fix in `frontend/src/lib/auth.ts`. |
| **Exams Authoring & Admin API** | `ExaminationBackendAgent` + `Cline (EXTERNAL PEER AGENT)` | `VERIFIED` | `backend/app/exams/{models.py,schemas.py,service.py,router.py}`, `backend/tests/test_exams.py` | `DatabaseAgent`; `AuthSecurityAgent`; `QuestionParserAgent` | 2026-11-12 | None | Full `/api/admin/exams*` CRUD + `publish`/`close` lifecycle + `_get_exam_or_404(..., for_update=True)` Postgres `FOR UPDATE` row locks across all 8 mutating exam operations + student `/api/exams*` discovery verified. |
| **Deterministic MCQ Parser** | `QuestionParserAgent` + `Cline (EXTERNAL PEER AGENT)` | `VERIFIED` | `backend/app/exams/parser.py`, `backend/tests/test_parser.py` | `backend/app/exams/schemas.py` | 2026-11-12 | None | Literate Engineering spec + state-machine parser (no answer guessing, ReDoS-safe, decimal/orphan/duplicate-answer handling) verified via `test_parser.py`. |
| **Attempt Delivery & Autosave Engine** | `AttemptEngineAgent` + `Cline (EXTERNAL PEER AGENT)` | `VERIFIED` | `backend/app/attempts/{models.py,schemas.py,service.py,router.py}`, `backend/tests/test_attempts.py` | `AuthSecurityAgent`; `DatabaseAgent`; `GradingTimerAgent` | 2026-11-12 | None | Row-locked `start_attempt` (`ApplicationUser FOR UPDATE` + `Exam FOR SHARE`, `resumed` support), frozen option snapshot (`option_order` + normalized `A`–`D`), dialect-safe autosave upsert, and `409` conflict payloads (`ATTEMPT_EXPIRED` / `ATTEMPT_ALREADY_GRADED`) verified. |
| **Server Timer & Deterministic Grading** | `GradingTimerAgent` | `VERIFIED` | `backend/app/attempts/grading.py`, `backend/app/attempts/service.py`, `backend/tests/test_grading_timer.py` | `AttemptEngineAgent`; `RULE 8–11` & `RULE 22` | 2026-11-12 | None | UTC deadline math (`_ensure_utc`), idempotent `finalize_attempt_locked`, immutable `GRADED` records, `show_result`/`show_correct_answers` gating, and aggregate summary stats verified via `test_grading_timer.py`. |
| **Student Examination Web UI** | `StudentWebAgent` | `VERIFIED` | `frontend/src/features/student/*`, `frontend/src/pages/Student*`, `frontend/src/types/studentExam.ts`, `frontend/src/lib/api.ts` | `/api/exams*` & `/api/attempts*`; `AuthSecurityAgent`; `ResponsiveDesignAgent` | 2026-11-12 | Live Neon Auth E2E deferred (`LIVE NEON = BLOCKED`). | Verified via post-edit Playwright Chromium real-browser E2E against real FastAPI + ephemeral SQLite + mocked Neon Better Auth responses using real Ed25519 JWT signing. Includes `ApiClientError` `code`/`payload` 409 handling in `useAttemptRunner.ts`. |
| **Admin Examination Web UI** | `AdminWebAgent` | `VERIFIED` | `frontend/src/features/admin/*`, `frontend/src/pages/Admin*`, `frontend/src/types/adminExam.ts` | `/api/admin/exams*` & `/api/admin/attempts/*`; `AuthSecurityAgent`; `ResponsiveDesignAgent` | 2026-11-12 | Live Neon Auth E2E deferred (`LIVE NEON = BLOCKED`). | Verified via post-edit Playwright Chromium real-browser E2E (draft settings, bulk parser preview, editor save, publish/close, results table, attempt detail modal) using real FastAPI + ephemeral SQLite + real Ed25519 JWTs. |
| **Design System & Responsive Shell** | `ResponsiveDesignAgent` | `VERIFIED` | `frontend/src/index.css`, `frontend/src/components/*`, `frontend/src/layouts/*`, `frontend/src/types/foundation.ts` | `AGENTS.md` `RULE 12` & `RULE 13` | 2026-11-12 | None | Light neutral surface + restrained `#b91c1c` accent, unoccluded static `McqQuestionCard` footer, `.visually-hidden:not(.skip-link)` radio clipping, `Dialog` `[data-dialog-initial-focus]` safe cancel focus, `>=44px` tap targets, and `0` horizontal overflows verified across `72` Playwright checks (`9` viewports × `8` routes). |
| **Secrets, Docker, CI & Deployment Readiness** | `DevOpsDeploymentAgent` | `PARTIAL_BLOCKED` | `.env.example`, `backend/.env.example`, `frontend/.env.example`, `.gitignore`, `README.md`, `backend/Dockerfile`, `frontend/vercel.json`, `frontend/package-lock.json`, `.github/workflows/ci.yml`, `buildspec.yml`, `docs/deployment-aws-vercel.md` | User rotation of previously exposed Neon password (`RULE 14`); Linux Docker / CodeBuild runtime | 2026-11-12 | **`Local Docker runtime = BLOCKED`** on Windows host; user must rotate previously exposed Neon password (`RULE 14`); `.github/workflows/neon_workflow.yml` has pre-existing unpinned actions & missing `permissions: contents: read` (flagged in `docs/deployment-aws-vercel.md`). | Env templates sanitized (placeholders only); `frontend/package-lock.json` fixed for clean `npm ci`; `PUSH_IMAGE=false` & `DEPLOY_VERCEL=false` safe defaults in `buildspec.yml`; zero Clerk dependencies remain. |
| **Testing & Verification Gates** | `TestingVerificationAgent` | `VERIFIED_LOCAL` | `backend/tests/*`, `frontend/package.json` | Non-prod Neon branch & Linux Docker daemon for live/container E2E | 2026-11-12 | `LIVE NEON = BLOCKED`; `Local Docker runtime = BLOCKED`; no dedicated Vite Vitest unit-test script configured yet in `frontend/package.json`. | Independent post-edit verification passed: `220` pytest passing across `12` test modules + `ruff` + `alembic` offline Postgres SQL + `npm ci` / `npm run lint` / `npm run build` + post-edit Playwright Chromium E2E & `72` responsive/a11y checks (`9` viewports × `8` routes). |

---

## 3. Canonical Backend API Contract (Implemented & Verified)

Root health & identity routes reside at `/`, and all domain routes are mounted under **`/api`**:

- **Public & Identity (`backend/app/main.py`):**
  - `GET /` -> `{name, version, environment, status}`
  - `GET /health` -> `{"status": "healthy"}`
  - `GET /auth/me` (`require_identity`) -> atomically upserts `application_users` by `auth_subject` (defaults new subjects to `STUDENT`, preserves existing DB `role`), returns `{user_id, auth_subject, email, display_name, role}`
- **Admin Examinations & Results (`require_admin` — `backend/app/exams/router.py` & `backend/app/attempts/router.py`):**
  - `POST /api/admin/exams` -> `ExamAdminOut` (`201`)
  - `GET /api/admin/exams` (`?status=DRAFT|PUBLISHED|CLOSED`) -> `list[ExamAdminOut]`
  - `POST /api/admin/exams/parse-questions` (`ParseQuestionsRequest {raw_text}`) -> `ParseQuestionsResponse` (stateless preview, zero DB writes; matched before `/{exam_id}`)
  - `GET /api/admin/exams/{exam_id}` -> `ExamWithQuestionsAdmin`
  - `PATCH /api/admin/exams/{exam_id}` (`ExamUpdate`, `extra="forbid"`, `status` excluded) -> `ExamAdminOut` (`DRAFT` only)
  - `DELETE /api/admin/exams/{exam_id}` -> `204` (`DRAFT` without attempts only)
  - `PUT /api/admin/exams/{exam_id}/questions` (`SaveQuestionsRequest {questions} | list[QuestionCreate]`) -> `ExamWithQuestionsAdmin` (`DRAFT` only; transactional replace)
  - `POST /api/admin/exams/{exam_id}/questions` (`QuestionCreate`) -> `201 QuestionAdminOut` (`DRAFT` only)
  - `PUT /api/admin/exams/{exam_id}/questions/{question_id}` (`QuestionCreate`) -> `QuestionAdminOut` (`DRAFT` only)
  - `DELETE /api/admin/exams/{exam_id}/questions/{question_id}` -> `204` (`DRAFT` only; re-sequences positions)
  - `POST /api/admin/exams/{exam_id}/publish` -> `ExamAdminOut` (`DRAFT -> PUBLISHED`; returns `400 {"detail": {"message": "exam failed validation", "errors": [...]}}` on invalid exam/questions)
  - `POST /api/admin/exams/{exam_id}/close` -> `ExamAdminOut` (`PUBLISHED -> CLOSED`, stamps `closed_at`, idempotent if already `CLOSED`, `409` on `DRAFT`)
  - `GET /api/admin/exams/{exam_id}/results` -> `ExamAdminResultsResponse` (`{exam_id, exam_title, pass_mark, total_attempts, summary, attempts}`)
  - `GET /api/admin/attempts/{attempt_id}` -> `AttemptResultOut` (full admin breakdown including `student_user_id`, `student_email`, `student_display_name`, and `question_review` when graded)
- **Student Examinations & Attempts (`require_student` — `backend/app/exams/router.py` & `backend/app/attempts/router.py`):**
  - `GET /api/exams` -> `list[ExamStudentOut]` (`PUBLISHED` exams, `question_count`, `attempts_used`, `active_attempt_id`, `can_start`, ZERO `is_correct`)
  - `GET /api/exams/{exam_id}` -> `ExamStudentOut` (`PUBLISHED` only; instructions, duration, `pass_mark`, `question_count`, `attempts_used`, `active_attempt_id`, `can_start`, ZERO `is_correct`)
  - `POST /api/exams/{exam_id}/attempts` (`AttemptStartRequest`, `extra="forbid"`) -> `AttemptStartResponse` (`201` new or `200` `resumed=True`; `ApplicationUser` `FOR UPDATE` + `Exam` `FOR SHARE`, auto-expires stale `IN_PROGRESS` attempts past `expires_at`)
  - `GET /api/attempts/{attempt_id}` -> `AttemptDelivery` (`IN_PROGRESS` questions, frozen `option_order` with normalized `A`–`D` labels, `saved_answers`, `started_at`, `expires_at`, `server_now`, ZERO `is_correct`; if expired/finalized, returns `409` `{detail, code: "ATTEMPT_EXPIRED" | "ATTEMPT_ALREADY_GRADED", attempt_id, status: "GRADED"}`)
  - `PUT /api/attempts/{attempt_id}/answers/{question_id}` (`AnswerSaveRequest {selected_option_id}`, `extra="forbid"`) -> `AnswerSaveResponse` (atomic upsert under `ExamAttempt` row lock; rejects with `409` `{detail, code, attempt_id, status}` after finalizing if already graded or `now >= expires_at`)
  - `POST /api/attempts/{attempt_id}/submit` (`AttemptSubmitRequest {confirm}`, `extra="forbid"`) -> `AttemptResultOut | AttemptSubmittedHiddenOut` (idempotent finalization: `TIMER_EXPIRED` if `now >= expires_at` else `STUDENT_SUBMITTED`; returns immutable persisted score/review per `exam.show_result` & `exam.show_correct_answers`)
  - `GET /api/attempts/{attempt_id}/result` -> `AttemptResultOut | AttemptSubmittedHiddenOut` (owner-isolated; auto-finalizes if expired, returns `409` if still `IN_PROGRESS` & unexpired, enforces `show_result` & post-finalization `show_correct_answers`)
  - `GET /api/student/attempts` -> `list[StudentAttemptSummary]` (caller's attempts across exams; withholds numerical score fields when `result_visible === false`)

---

## 4. Handoff Rules for Cline (`EXTERNAL PEER AGENT`)

1. **Immutable Historical Migrations:** Do NOT edit `0001_application_users.py`, `0002_examination_schema.py`, `0003_attempt_option_order.py`, or `0004_exam_closed_at_and_indexes.py`. All future schema changes MUST go into additive `0005_*`+ Alembic migrations without modifying `neon_auth.*` (`RULE 4`).
2. **Authoritative Identity Key:** Always reference `application_users.id` (`identity.user_id: UUID`), never `identity.subject` (`auth_subject` string) or client-supplied role claims (`RULE 7`).
3. **Preserve Error & Auth Contracts:** Frontend callers rely on `ApiClientError` preserving `status`, `detail`, `code`, and `payload` (`frontend/src/lib/api.ts`) and `createInternalNeonAuth` (`neonAuth.getJWTToken()`) in `frontend/src/lib/auth.ts`. Update this ledger rather than duplicating routes, hooks, or UI primitives (`RULE 17`, `RULE 18`).
4. **Security & Secrets (`RULE 23`):** Never write database URLs, passwords, tokens, live keys, or Clerk references into any code, template, or documentation file.

---

## 5. Phase 3 Next Handoff Priorities

1. **Non-Production Neon Branch & Credential Rotation (User-Authorized — `RULE 5`, `RULE 14`):**
   - Create a non-production `testing` (or `staging`) branch inside **Dexta Global** (`org-weathered-mud-72902193`, project `noisy-boat-95673317`).
   - Rotate the previously exposed Neon PostgreSQL password in Neon Console / Secrets Manager immediately.
2. **Live Neon Schema & Managed Better Auth Verification:**
   - Run `alembic heads` and `alembic upgrade head` using `DIRECT_DATABASE_URL` against the non-production Neon `testing` branch.
   - Execute a live end-to-end authentication & exam flow against real Neon Managed Better Auth (email/password + Google OAuth callback + live EdDSA JWKS verification) and real Neon PostgreSQL (`DATABASE_URL` pooled).
3. **Container & AWS CodeBuild / ECR Verification:**
   - Run `docker build -f backend/Dockerfile` and `/health` smoke probe in a Linux / AWS CodeBuild environment (blocked locally on Windows host) prior to enabling `PUSH_IMAGE=true`.
4. **Hardening `.github/workflows/neon_workflow.yml`:**
   - Add explicit `permissions: contents: read`, pin third-party actions (`tj-actions/branch-names`, `neondatabase/create-branch-action`, `neondatabase/delete-branch-action`) to commit SHAs (or replace branch-name lookup with `${{ github.head_ref }}`), add fork PR guards, and verify `vars.NEON_PROJECT_ID` points to Dexta Global `noisy-boat-95673317`.
5. **Committed Frontend Unit & E2E Test Suites (`TestingVerificationAgent`):**
   - Configure Vitest + React Testing Library (`npm test` in `frontend/package.json`) covering `lib/api.ts` (`ApiClientError` `code`/`payload` 409 parsing), `lib/auth.ts` (`getNeonAuthToken` JWT validation), `useAttemptRunner.ts`, `ExamTimerBadge.tsx`, and `adminUtils.ts`.
   - Commit a Playwright Chromium E2E + responsive/a11y suite into the repository so CI executes it automatically.
6. **Phase 3 Feature Backlog:**
   - Deliver verified Google OAuth + optional phone-number auth (per Neon Auth config), exam-to-student roster/cohort assignment, timer & reconnect UX polish, and AWS App Runner / CloudWatch structured observability.
