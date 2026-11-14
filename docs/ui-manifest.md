# Examination Hub — Frontend UI Route & Component Manifest (`STEP 0` & `PHASE A`)

> **Status:** `APPROVED` (Phase A Foundation Complete; Ready for Phase B Student Journey)
> **Scope:** Presentation-only redesign of the Examination Hub frontend (`frontend/`). Zero changes to business logic, API contracts, route paths, authentication, grading, or data shapes.

---

## 1. Frontend Stack Identification (`STEP 0.1`)

| Layer | Technology & Version | Notes / Constraints |
| --- | --- | --- |
| **Framework & Bundler** | `react` `^19.0.0`, `react-dom` `^19.0.0`, `vite` `^6.2.0`, `typescript` `~5.7.2` | Single responsive web application (`RULE 12`). No second framework or CSS-in-JS runtime allowed. |
| **Routing** | `react-router-dom` `^7.3.0` (`BrowserRouter`, `Routes`, `Route`, `Outlet`) | Defined in `frontend/src/App.tsx`. 12 `<Route>` declarations wrapped in `<AppShell />` and `<ProtectedRoute requiredRole="..." />`. |
| **Styling Approach** | `tailwindcss` `^4.0.9` via `@tailwindcss/vite` + CSS custom properties in `frontend/src/index.css` | Work strictly within Tailwind v4 `@theme inline` + `:root` semantic CSS custom properties (`frontend/src/index.css`). |
| **Component Primitives** | `@radix-ui/react-slot` `^1.1.2`, `class-variance-authority` `^0.7.1`, `clsx`, `tailwind-merge`, native HTML `<dialog>` (`showModal()`) | Located in `frontend/src/components/ui/*` (`Button`, `Badge`, `StatusPill`, `Card`, `StatCard`, `ExamCard`, `Dialog`, `ConfirmDialog`, `Tabs`, `SegmentedControl`, `SelectableListItem`, `QuestionTile`, `Toast`, `DropdownMenu`, `Tooltip`, `Checkbox`, `Switch`, `FileDropzone`, `Input`, `Select`, `Textarea`, `Label`, `Alert`, `StatePanel`, `Skeleton`, `ResponsiveTable`). Icons from `lucide-react` `^0.477.0`. |
| **Authentication Provider** | `@neondatabase/auth` `^0.6.0-beta.2` (`createAuthClient` in `frontend/src/lib/auth.ts`) + custom `AuthBoundary.tsx` & `AuthContext.tsx` | All sign-in, sign-up, Google OAuth trigger, session loading, unconfigured, and signed-in fallback cards are rendered in-app by `frontend/src/features/auth/AuthBoundary.tsx` and `ProtectedRoute.tsx` (no external hosted auth iframe/screen). |
| **Document / PDF Rendering** | `pdfjs-dist` `^5.6.205` (`extractImportText.ts`) + authenticated blob image fetching (`AuthenticatedPdfImage.tsx`, `PdfCropEditor.tsx`) | Client-side PDF text extraction & coordinate-based question crop preview/adjustment for bulk exam import. |

---

## 2. Route Manifest (`STEP 0.2`)

Every `<Route>` in `frontend/src/App.tsx` (plus role-specific states rendered at that path) is catalogued below. The Playwright visual-walk and route-coverage scripts parse the `<!-- ROUTE_MANIFEST_START -->` ... `<!-- ROUTE_MANIFEST_END -->` table directly.

<!-- ROUTE_MANIFEST_START -->
| path | file | role | layout used | states it has | dialogs/drawers it opens | status |
| --- | --- | --- | --- | --- | --- | --- |
| `/` | `src/pages/OverviewPage.tsx` | `public` | `PublicLayout` (via `AppShell`) | `loading` (session check), `success` (sign-in mode, sign-up mode), `error` (invalid credentials / auth error, backend `/health` unreachable alert, session identity verification failure, auth service unconfigured) | None | `not started` |
| `/student` | `src/pages/StudentDashboardPage.tsx` | `student` | `StudentLayout` (via `AppShell`) | `loading` (skeleton cards), `empty` (no published exams, no attempt history), `error` (dashboard API error, `403` access denied if admin, session error), `success` (populated exams + active sitting resume banner + attempt history table) | Mobile `<Dialog variant="drawer">` menu (`< 640px`) | `not started` |
| `/student/exams/:examId` | `src/pages/StudentExamInstructionsPage.tsx` | `student` | `StudentLayout` (via `AppShell`) | `loading` (instructions skeleton), `empty` (exam has no description fallback), `error` (exam not found / window closed / unavailable, `startError` alert on launch failure), `success` (`can_start` ready to begin, `active_attempt_id` resume in-progress sitting, `attempts_used >= max_attempts` locked / already submitted, `!show_result` instructor-controlled release notice) | Mobile `<Dialog variant="drawer">` menu (`< 640px`) | `not started` |
| `/student/attempts/:attemptId` | `src/pages/StudentAttemptPage.tsx` | `student` | `FocusLayout` (via `AppShell`) | `loading` (attempt workspace skeleton), `empty` (`No questions were returned for this examination attempt`), `error` (attempt load failure, `submitError` alert, `failedSave` autosave failure + retry banner, `isExpired` time-expired auto-submitting banner), `success` (active text-only question, active PDF cropped image question, autosave `idle`/`saving`/`saved`, desktop question navigator aside) | `QuestionNavigatorDialog` (`All questions` modal), `ConfirmDialog` (`Submit examination?` with unanswered question warning) | `not started` |
| `/student/results/:attemptId` | `src/pages/StudentResultPage.tsx` | `student` | `StudentLayout` (via `AppShell`) | `loading` (result skeleton), `empty` (`!result_visible` score hidden / pending release, `!show_correct_answers` question review disabled notice), `error` (`in_progress` `409` conflict state with resume CTA, API load error), `success` (graded `PASSED` summary, graded `FAILED` summary below pass mark, `TIMER_EXPIRED` auto-submitted notice, full `ResultReviewCard` breakdown) | Mobile `<Dialog variant="drawer">` menu (`< 640px`) | `not started` |
| `/admin` | `src/pages/AdminOverviewPage.tsx` | `admin` | `AdminLayout` (via `AppShell`) | `loading` (`Loading examinations...`), `empty` (`No examinations created yet.`), `error` (exam list fetch error, `403` access denied if student), `success` (4 KPI stat cards + `Recently updated` list + `Available now` published list) | Mobile `<Dialog variant="drawer">` menu (`< 1024px`) | `not started` |
| `/admin/exams` | `src/pages/AdminDashboardPage.tsx` | `admin` | `AdminLayout` (via `AppShell`) | `loading` (3 skeleton cards), `empty` (zero exams created, zero exams matching search/status filter), `error` (list load error, `actionError` publish/close/delete failure alert), `success` (populated `ResponsiveTable` with `SegmentedControl` `DRAFT`/`PUBLISHED`/`CLOSED` filters, search, `actionNotice` banner) | `ConfirmDialog` (`Delete draft examination?`), Mobile `<Dialog variant="drawer">` menu (`< 1024px`) | `not started` |
| `/admin/results` | `src/pages/AdminResultsPage.tsx` | `admin` | `AdminLayout` (via `AppShell`) | `loading` (`loadingExams` list state, `loadingResults` selected exam summary state), `empty` (no examinations available, no examination selected prompt), `error` (`examError` list failure, `resultsError` summary failure), `success` (two-column `SelectableListItem` examination selector + selected exam 4-metric summary & link to full attempt breakdown) | Mobile `<Dialog variant="drawer">` menu (`< 1024px`) | `not started` |
| `/admin/exams/new` | `src/pages/AdminExamNewPage.tsx` | `admin` | `AdminLayout` (via `AppShell`) | `loading` (`isSubmitting` create state), `empty` (initial blank `ExamSettingsForm`), `error` (client field validation errors: title, duration, pass mark, max attempts, schedule window; server `submitError` alert), `success` (valid form ready to create draft) | Mobile `<Dialog variant="drawer">` menu (`< 1024px`) | `not started` |
| `/admin/exams/:examId` | `src/pages/AdminExamEditorPage.tsx` | `admin` | `AdminLayout` (via `AppShell`) | `loading` (editor skeleton cards), `empty` (draft exam with `0` questions in `QuestionListEditor` + empty `BulkParserPanel`), `error` (exam load error, `statusError` alert, `BulkParserPanel` parse/PDF errors & block validation errors, `QuestionListEditor` validation errors), `success` (`Tabs` with `overview` tab, `questions` tab with `BulkParserPanel` PDF crop preview + `QuestionListEditor`, `settings` tab, `PUBLISHED`/`CLOSED` read-only locked state, `statusNotice` alert) | `ConfirmDialog` (`Publish`/`Close`/`Delete` exam), `ConfirmDialog` (`Replace current questions?` in `BulkParserPanel`), `ConfirmDialog` (`Merge adjacent questions?` / `Split this question?` in `BulkParserPanel`) | `not started` |
| `/admin/exams/:examId/results` | `src/pages/AdminExamResultsPage.tsx` | `admin` | `AdminLayout` (via `AppShell`) | `loading` (results skeleton cards), `empty` (zero student attempts recorded, zero attempts matching filter/search), `error` (results fetch error), `success` (5 KPI summary cards + `SegmentedControl` `ALL`/`PASSED`/`FAILED`/`IN_PROGRESS` filter pills + student search + `ResponsiveTable`) | `AttemptDetailDialog` (per-student attempt metadata & question-by-question answer breakdown), Mobile `<Dialog variant="drawer">` menu (`< 1024px`) | `not started` |
| `*` (`/404-not-found`) | `src/pages/NotFoundPage.tsx` | `public` | `PublicLayout` / `StudentLayout` / `AdminLayout` (retains active role shell when signed in) | `error` (`404` page not found state with return CTA) | Mobile `<Dialog variant="drawer">` menu (when signed in) | `not started` |
<!-- ROUTE_MANIFEST_END -->

---

## 3. Non-Route Inventory (`STEP 0.3`)

### 3.1 Layouts, Shells, Headers, Sidebars & Footers

| Item | File(s) | Phase A Status & Behavior |
| --- | --- | --- |
| **Root Application Shell & Route Titles** | `src/layouts/AppShell.tsx`, `src/layouts/routeMetadata.ts`, `tests/routeMetadata.test.mjs` | **Completed in Phase A:** Dispatches routes to `PublicLayout`, `StudentLayout`, `FocusLayout`, and `AdminLayout` (retaining `StudentLayout`/`AdminLayout` on `*` `404` when signed in). Fixed `resolveRouteMetadata` for `/admin` (`"Overview \| Examination Hub"`), `/admin/exams` (`"Examinations \| Examination Hub"`), and `/admin/results` (`"Results \| Examination Hub"`), verified by unit tests in `tests/routeMetadata.test.mjs`. |
| **Top Header & Mobile Navigation Drawer** | `src/layouts/StudentLayout.tsx`, `src/layouts/AdminLayout.tsx`, `src/components/AppHeader.tsx`, `src/components/ui/dialog.tsx` | **Completed in Phase A:** Replaced `popover="auto"` mobile menu with `<Dialog variant="drawer">`, which traps focus via native `showModal()`, restores focus to the trigger button on close, and closes on `Escape` or backdrop click. |
| **Footers & Theme Color** | `index.html`, `src/layouts/PublicLayout.tsx`, `src/layouts/StudentLayout.tsx`, `src/layouts/AdminLayout.tsx` | **Completed in Phase A:** Added `<meta name="theme-color" content="#f7f8fa" />` in `index.html` matching `--bg-canvas`. Replaced technical `"Authoritative Server Timing & Grading"` footer copy with plain student-friendly wording (`"Progress saved automatically during your sitting"` in `StudentLayout`, `"Calm & Focused Online Assessment"` in `PublicLayout`, `"Online Assessment & Examination Portal"` in `AdminLayout`). |
| **Page Header** | `src/components/PageHeader.tsx` | **Completed in Phase A:** Supports `breadcrumbs`, `eyebrow`, `title` (`h1`), `description`, `meta`, and `action`. |

### 3.2 Authentication, Password Recovery Investigation (`Addition #9`) & Error States

| Screen / State | Current File(s) | Notes & Coverage Plan |
| --- | --- | --- |
| **Sign In (`mode="sign-in"`) & Sign Up (`mode="sign-up"`)** | `src/pages/OverviewPage.tsx`, `src/features/auth/AuthBoundary.tsx` | Email + password form, password visibility toggle, `Continue with Google` button, mode switcher. Hosted in-app inside `OverviewPage`. |
| **Password Reset / Recovery Screen (`Addition #9` Report)** | `src/lib/auth.ts`, `node_modules/@neondatabase/auth` (`0.6.0-beta.2`) | **No screen exists in the app.** Inspection of `@neondatabase/auth@0.6.0-beta.2` (`dist/server-pZf5ArnA.mjs` and `dist/supabase-adapter-hYitiCZ_.mjs`) shows that the underlying Better Auth / Supabase adapter layer exposes `requestPasswordReset` and `resetPassword` (requiring backend transactional email / SMTP configuration in Neon Auth), while our frontend wrapper (`src/lib/auth.ts`) only wires `signIn.email`, `signUp.email`, `signIn.social`, `signOut`, `getSession`, and `token`. Per instruction, **we are not building a password reset screen as part of this UI redesign**. |
| **Session Loading / Identity Error / `403` Access Denied / Unconfigured** | `src/features/auth/AuthBoundary.tsx`, `src/features/auth/ProtectedRoute.tsx` | Covered and scheduled for token/component cleanup in Phase D. |

### 3.3 Core UI Primitives (`Additions #4` & `#5` — Completed in Phase A)

| Primitive | File | Status & Usage |
| --- | --- | --- |
| **`Button`** | `src/components/ui/button.tsx` | Upgraded in Phase A (`default`, `secondary`, `outline`, `ghost`, `destructive`; sizes `xs`, `sm`, `default`, `lg`, `icon`; `isLoading` spinner). |
| **`Badge` & `StatusPill`** | `src/components/ui/badge.tsx` | Upgraded in Phase A (`selected`, `info`, `success`, `warning`, `destructive`, `StatusPill` with dot/icon). |
| **`Card` & `StatCard`** | `src/components/ui/card.tsx` | Upgraded in Phase A (`StatCard` replaces `.portal-stat`). |
| **`ExamCard`** | `src/components/ui/exam-card.tsx` | **Created in Phase A** and wired into `StudentExamCard.tsx` (replaces `.portal-exam-card`). |
| **`Dialog` & `ConfirmDialog`** | `src/components/ui/dialog.tsx` | Upgraded in Phase A (`variant="modal" \| "drawer"`, focus trap, focus restoration, Escape close). |
| **`Tabs` (`TabsList`, `TabsTrigger`, `TabsContent`)** | `src/components/ui/tabs.tsx` | **Created in Phase A** and wired into `AdminExamEditorPage.tsx` (`overview` / `questions` / `settings` tabs). |
| **`SegmentedControl` (`SegmentedControlItem`)** | `src/components/ui/segmented-control.tsx` | **Created in Phase A** and wired into `AdminDashboardPage.tsx` and `AdminExamResultsPage.tsx` filter pills. |
| **`SelectableListItem`** | `src/components/ui/selectable-list-item.tsx` | **Created in Phase A** and wired into `AdminResultsPage.tsx` examination selector list. |
| **`QuestionTile`** | `src/components/ui/question-tile.tsx` | **Created in Phase A** (`variant="grid" \| "row"`) and wired into `QuestionNavigatorDialog.tsx` and `StudentAttemptPage.tsx`. |
| **`Toast` (`ToastProvider`, `useToast`, `ToastViewport`)** | `src/components/ui/toast.tsx` | **Created in Phase A** for non-blocking status notifications. |
| **`DropdownMenu` (`DropdownMenuItem`)** | `src/components/ui/dropdown-menu.tsx` | **Created in Phase A** with Escape/outside-click close and keyboard menu semantics. |
| **`Tooltip`** | `src/components/ui/tooltip.tsx` | **Created in Phase A** with `role="tooltip"` and focus/hover visibility. |
| **`Checkbox` & `Switch`** | `src/components/ui/checkbox.tsx`, `src/components/ui/switch.tsx` | **Created in Phase A** for form settings and toggles. |
| **`FileDropzone`** | `src/components/ui/file-dropzone.tsx` | **Created in Phase A** for drag-and-drop / button file selection (`BulkParserPanel`). |

---

## 4. Route × State Screenshot Coverage Table (`Additions #1` & `#2`)

All **100** screenshots below were captured cleanly in `docs/ui-screenshots/after/` (and baseline in `docs/ui-screenshots/before/`) with `0` stale files, `0` horizontal overflow failures, and `0` console/page errors.

| Route | State / Scenario | Viewport(s) | Status | Captured Filename(s) in `docs/ui-screenshots/after/` (or Reason if Not Captured) |
| --- | --- | --- | --- | --- |
| `/` | Sign-In Ready (Default) | `1440w`, `1024w`, `768w`, `390w`, **`360w`** | **Captured** | `public__root__ready__{1440,1024,768,390,360}w.png` |
| `/` | Sign-Up Mode | `1440w` | **Captured** | `public__root__signup__1440w.png` |
| `/` | Session Loading / Empty / Backend Unreachable Error | `1440w` | **Captured** | `public__root__{loading,empty,error}__1440w.png` |
| `/student` | Populated Dashboard + Active Attempt Banner + History | `1440w`, `1024w`, `768w`, `390w` | **Captured** | `student__student__ready__{1440,1024,768,390}w.png` |
| `/student` | Loading Skeletons / Empty (`0` exams) / API Error | `1440w` | **Captured** | `student__student__{loading,empty,error}__1440w.png` |
| `/student/exams/:examId` | Pre-Exam Instructions Ready (`can_start` / `active_attempt_id`) | `1440w`, `1024w`, `768w`, `390w` | **Captured** | `student__student-exams-examId__ready__{1440,1024,768,390}w.png` |
| `/student/exams/:examId` | Loading / Empty Description Fallback / API Error | `1440w` | **Captured** | `student__student-exams-examId__{loading,empty,error}__1440w.png` |
| `/student/attempts/:attemptId` | Active Attempt — **Text-Only Question (`Q1`)** | `1440w`, `1024w`, `768w`, `390w`, **`360w`** | **Captured** | `student__student-attempts-attemptId__ready__{1440,1024,768,390,360}w.png`, `student__student-attempts-attemptId__text-question__1440w.png` |
| `/student/attempts/:attemptId` | Active Attempt — **PDF Cropped Image Question (`Q3`)** | `1440w` | **Captured** | `student__student-attempts-attemptId__pdf-image-question__1440w.png` |
| `/student/attempts/:attemptId` | **Time Expired** (`now >= expires_at` warning banner & `00:00` timer) | `1440w` | **Captured** | `student__student-attempts-attemptId__time-expired__1440w.png` |
| `/student/attempts/:attemptId` | `QuestionNavigatorDialog` Open & `ConfirmDialog` (`Review & Submit`) Open | `1440w` | **Captured** | `student__student-attempts-attemptId__dialog-navigator__1440w.png`, `student__student-attempts-attemptId__dialog-submit__1440w.png` |
| `/student/attempts/:attemptId` | Loading Skeletons / Empty (`0` questions) / Load Error | `1440w` | **Captured** | `student__student-attempts-attemptId__{loading,empty,error}__1440w.png` |
| `/student/results/:attemptId` | **Passed Result** (`83.3%`, `PASSED`, full question review) | `1440w`, `1024w`, `768w`, `390w`, **`360w`** | **Captured** | `student__student-results-attemptId__ready__{1440,1024,768,390,360}w.png` |
| `/student/results/:attemptId` | **Failed Result (Below Pass Mark)** (`16.7%`, `Did not pass`, `1/6` pts) | `1440w` | **Captured** | `student__student-results-attemptId__failed-result__1440w.png` |
| `/student/results/:attemptId` | **Score Hidden** (`result_visible === false` confirmation screen) | `1440w` | **Captured** | `student__student-results-attemptId__score-hidden__1440w.png` (and `empty__1440w.png`) |
| `/student/results/:attemptId` | **Review Disabled** (`show_correct_answers === false`) | `1440w` | **Captured** | `student__student-results-attemptId__review-disabled__1440w.png` |
| `/student/results/:attemptId` | **`409` Attempt Still In Progress** (`Sitting active` + `Resume Examination` CTA) | `1440w` | **Captured** | `student__student-results-attemptId__in-progress-409__1440w.png` |
| `/student/results/:attemptId` | **Time Expired Auto-Submitted Result** (`submission_reason === "TIMER_EXPIRED"`) | `1440w` | **Captured** | `student__student-results-attemptId__time-expired-result__1440w.png` |
| `/student/results/:attemptId` | Loading / API Error | `1440w` | **Captured** | `student__student-results-attemptId__{loading,error}__1440w.png` |
| `/admin` | Admin Overview Ready / Loading / Empty / Error | `1440w`, `1024w`, `768w`, `390w` | **Captured** | `admin__admin__ready__{1440,1024,768,390}w.png`, `admin__admin__{loading,empty,error}__1440w.png` |
| `/admin/exams` | Admin Examinations List Ready (with `360px` card collapse) | `1440w`, `1024w`, `768w`, `390w`, **`360w`** | **Captured** | `admin__admin-exams__ready__{1440,1024,768,390,360}w.png` |
| `/admin/exams` | Loading / Empty / Error | `1440w` | **Captured** | `admin__admin-exams__{loading,empty,error}__1440w.png` |
| `/admin/results` | Admin Results Selector Ready / Loading / Empty / Error | `1440w`, `1024w`, `768w`, `390w` | **Captured** | `admin__admin-results__ready__{1440,1024,768,390}w.png`, `admin__admin-results__{loading,empty,error}__1440w.png` |
| `/admin/exams/new` | Create Examination Form Ready / Loading / Empty / Error | `1440w`, `1024w`, `768w`, `390w` | **Captured** | `admin__admin-exams-new__ready__{1440,1024,768,390}w.png`, `admin__admin-exams-new__{loading,empty,error}__1440w.png` |
| `/admin/exams/:examId` | Draft Exam Editor (`Overview` tab & `Questions` tab with PDF crop + list editor) | `1440w`, `1024w`, `768w`, `390w` | **Captured** | `admin__admin-exams-examId__ready__{1440,1024,768,390}w.png`, `admin__admin-exams-examId__tab-questions__1440w.png` |
| `/admin/exams/:examId` | **`PUBLISHED` Locked Read-Only State** | `1440w` | **Captured** | `admin__admin-exams-examId__published-locked__1440w.png` |
| `/admin/exams/:examId` | **`CLOSED` Locked Read-Only State** | `1440w` | **Captured** | `admin__admin-exams-examId__closed-locked__1440w.png` |
| `/admin/exams/:examId` | Loading / Empty (`0` questions) / Error | `1440w` | **Captured** | `admin__admin-exams-examId__{loading,empty,error}__1440w.png` |
| `/admin/exams/:examId/results` | Exam Results Table + `AttemptDetailDialog` Open + Loading / Empty / Error | `1440w`, `1024w`, `768w`, `390w` | **Captured** | `admin__admin-exams-examId-results__ready__{1440,1024,768,390}w.png`, `admin__admin-exams-examId-results__dialog-attempt-detail__1440w.png`, `admin__admin-exams-examId-results__{loading,empty,error}__1440w.png` |
| `*` (`/404-not-found`) | `404` Not Found State | `1440w`, `1024w`, `768w`, `390w` | **Captured** | `public__404-not-found__ready__{1440,1024,768,390}w.png`, `public__404-not-found__error__1440w.png` |

---

## 5. Automated Accessibility (`axe-core` WCAG 2.1 A/AA) Baseline & Phase A Shell Comparison (`Addition #3`)

Executed via `axe-core` across all **59** route × state combinations in `frontend/tests/ui-visual-walk.mjs` (full JSON output recorded in `docs/ui-screenshots/after/visual-walk-report.json`):

| Route | Shell Used (Phase A) | States Audited | Critical Violations | Serious Violations | Details / Remediation Target |
| --- | --- | ---: | ---: | ---: | --- |
| `/` | `PublicLayout` | `ready`, `loading`, `empty`, `error`, `signup` (`5`) | **`0`** | **`0`** | Clean (`0` serious/critical violations). |
| `/student` | `StudentLayout` | `ready`, `loading`, `empty`, `error` (`4`) | **`0`** | **`2`** (`ready`, `empty`) | Legacy `StudentDashboardPage.tsx` wraps `<dt>`/`<dd>` pairs inside `<div className="portal-stat">` inside a `<dl>` (`definition-list` / `dlitem`). **Will be eliminated in Phase B** when `.portal-stat` `<dl>` is replaced with `<StatCard>`. |
| `/student/exams/:examId` | `StudentLayout` | `ready`, `loading`, `empty`, `error` (`4`) | **`0`** | **`0`** | Clean (`0` serious/critical violations). |
| `/student/attempts/:attemptId` | `FocusLayout` | `ready`, `loading`, `empty`, `error`, `pdf-image-question`, `dialog-navigator`, `dialog-submit`, `time-expired` (`8`) | **`0`** | **`0`** | Clean (`0` serious/critical violations across all 8 states & dialogs). |
| `/student/results/:attemptId` | `StudentLayout` | `ready`, `loading`, `empty`, `error`, `failed-result`, `review-disabled`, `score-hidden`, `in-progress-409`, `time-expired-result` (`9`) | **`0`** | **`0`** | Clean (`0` serious/critical violations across all 9 result states). |
| `/admin` | `AdminLayout` | `ready`, `loading`, `empty`, `error` (`4`) | **`0`** | **`0`** | Clean (`0` serious/critical violations). |
| `/admin/exams` | `AdminLayout` | `ready`, `loading`, `empty`, `error` (`4`) | **`0`** | **`0`** | Clean (`0` serious/critical violations). |
| `/admin/results` | `AdminLayout` | `ready`, `loading`, `empty`, `error` (`4`) | **`0`** | **`0`** | Clean (`0` serious/critical violations). |
| `/admin/exams/new` | `AdminLayout` | `ready`, `loading`, `empty`, `error` (`4`) | **`0`** | **`0`** | Clean (`0` serious/critical violations). |
| `/admin/exams/:examId` | `AdminLayout` | `ready`, `loading`, `empty`, `error`, `tab-questions`, `published-locked`, `closed-locked` (`7`) | **`0`** | **`0`** | Clean (`0` serious/critical violations; fixed `aria-required-children` on `<TabsList>` during Phase A). |
| `/admin/exams/:examId/results` | `AdminLayout` | `ready`, `loading`, `empty`, `error`, `dialog-attempt-detail` (`5`) | **`0`** | **`0`** | Clean (`0` serious/critical violations). |
| `*` (`/404-not-found`) | `PublicLayout` / Role Shell | `ready`, `error` (`2`) | **`0`** | **`0`** | Clean (`0` serious/critical violations). |
| **Total Across All 59 States** | **All 4 Shells** | **59 audited states** | **`0` Critical** | **`4` Serious** (`2` unique in unmigrated `/student` page) | **`0` layout/shell violations; the single `<dl>` issue in `StudentDashboardPage.tsx` will be removed in Phase B.** |

---

## 6. Style & Token Audit Counts & Legacy Class Retirement Guard (`STEP 0.4` & `Addition #10`)

| Metric | Step 0.4 Baseline | After Phase A | Target After Phase D |
| --- | ---: | ---: | ---: |
| **Distinct non-token colors** | `65` (`21` hex + `24` `rgb()` in `index.css` + `20` Tailwind palette classes) | **`19`** (`0` hex + `0` `rgb()` outside `:root` in `index.css`; `bg-slate-50` removed by `ExamCard`) | **`0`** outside `:root` token definitions |
| **Distinct font-size declarations** | `26` | **`12`** | **`<= 12`** (8-step typographic scale) |
| **Distinct spacing values** | `133` | **`135`** | Consolidated onto `--space-1`..`--space-16` / 4px grid |
| **Legacy classes (`.portal-hero*`, `.portal-*`, `.auth-*`)** | Present in `StudentDashboardPage`, `AdminOverviewPage`, `OverviewPage`, `AuthBoundary` | `.portal-exam-card` retired via `ExamCard`; remaining `.portal-*` and `.auth-*` scheduled for Phases B–D | **`0`** (enforced by automated legacy-style guard test in Phase D; test will fail if `.portal-hero*`, `.portal-*`, or `.auth-*` exist in `src/`) |
