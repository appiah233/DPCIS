# Examination Hub

> **Current Stage:** Phase 2 Vertical Slice Implemented (Authoring, Timed Delivery, Grading & Deployment Readiness).  
> The platform delivers end-to-end **Administrator** exam authoring, deterministic bulk MCQ parsing, preview/editing, publish/close lifecycle, and results oversight alongside **Student** discovery, timed exam delivery with server-authoritative countdown & autosave, idempotent submission/expiry, backend `Decimal` grading, answer-key isolation, and PostgreSQL RBAC (`application_users` keyed by `auth_subject`), plus Docker, CI, AWS CodeBuild, and Vercel SPA readiness.

---

## 1. Product Purpose

Examination Hub is a responsive web examination platform (`320px`–`1440px+`) designed around two server-enforced roles (`ADMIN` and `STUDENT` in `application_users`):

- **Students:** Sign in via Neon Managed Better Auth, browse published examinations (`/student`), inspect exam instructions and attempt limits (`/student/exams/:examId`), start or resume timed MCQ attempts (`/student/attempts/:attemptId`) with server-authoritative UTC `started_at`/`expires_at` countdowns and autosave, submit manually or automatically upon timer expiry, and view backend-graded scores (`/student/results/:attemptId`) gated by `show_result` and post-finalization `show_correct_answers`.
- **Administrators:** Sign in via Neon Managed Better Auth, create and manage draft examinations (`/admin`, `/admin/exams/new`, `/admin/exams/:examId`), paste raw MCQ text into the deterministic Python parser for live preview and editing, configure duration, pass mark, question limits, randomization, and result visibility, publish or close exams, and review participant results and attempt breakdowns (`/admin/exams/:examId/results`).

---

## 2. Architecture Overview

The repository separates API logic, responsive browser UI, identity, database persistence, and CI/CD deployment concerns:

- **Backend (`backend/`):** Python 3.12 + FastAPI application (`app.main:create_app`) with environment-driven Pydantic v2 settings, strict security headers, sanitized error responses (`X-Request-ID`), SQLAlchemy 2.x + Alembic linear migrations, RBAC dependencies (`require_identity`, `require_student`, `require_admin`), deterministic MCQ parser (`app/exams/parser.py`), transactional attempt engine (`app/attempts/service.py`), and pure `Decimal` grading/expiry logic (`app/attempts/grading.py`).
- **Frontend (`frontend/`):** React 19 + TypeScript + Vite + Tailwind CSS v4 + accessible UI primitives, `BrowserRouter` SPA routes (`/`, `/student/*`, `/admin/*`), Neon Managed Better Auth session integration (`@neondatabase/auth`), fail-closed `ProtectedRoute` guards, and Vercel SPA rewrite configuration (`frontend/vercel.json`).
- **Authentication (Neon Managed Better Auth):** Owned externally by Neon Managed Better Auth. FastAPI verifies EdDSA Bearer JWTs via JWKS and resolves/upserts local PostgreSQL roles in `application_users` keyed by the immutable JWT subject (`auth_subject` / `sub`), never relying on email addresses or client-supplied role claims.
- **Database:** Neon PostgreSQL managed via SQLAlchemy 2.x and Alembic migrations. Runtime traffic uses `DATABASE_URL` (pooled Neon endpoint recommended in deployed environments), while Alembic uses `DIRECT_DATABASE_URL` (falling back to `DATABASE_URL` when unset).

---

## 3. Approved Technology Stack

- **Backend:** Python 3.12, FastAPI, Pydantic v2 (`pydantic-settings`), SQLAlchemy 2.x, `psycopg[binary]` (v3), Alembic, PyJWT (`EdDSA`), pytest, Ruff
- **Frontend:** React 19, TypeScript, Vite, Tailwind CSS v4, shadcn/ui-compatible components, React Router, `@neondatabase/auth`
- **Authentication:** Neon Managed Better Auth (Google OAuth / email-password)
- **Database:** Neon PostgreSQL
- **Deployment / CI:** Docker (`python:3.12-slim`), GitHub Actions, AWS CodePipeline, AWS CodeBuild (`buildspec.yml`), Amazon ECR (`examination-hub-api`), AWS App Runner, Vercel (`frontend/vercel.json`), Amazon CloudWatch

---

## 4. Repository Structure

```text
.
├── .github/
│   └── workflows/
│       ├── ci.yml                # CI: security hygiene, Ruff, Alembic head/SQL, pytest, frontend lint/test/build, Docker /health
│       └── neon_workflow.yml     # Non-production Neon PR preview branch workflow (see deployment doc for risk notes)
├── backend/
│   ├── alembic/
│   │   ├── versions/             # Linear chain: 0001_application_users -> 0002_examination_schema -> 0003_attempt_option_order -> 0004_exam_closed_at_and_indexes
│   │   ├── env.py                # Reads DIRECT_DATABASE_URL / DATABASE_URL; excludes neon_auth schema
│   │   └── script.py.mako
│   ├── app/
│   │   ├── auth/                 # Neon Managed Auth EdDSA JWT verification & fail-closed RBAC dependencies
│   │   ├── attempts/             # Attempt models, schemas, router, row-locked delivery/autosave, and pure Decimal grading
│   │   ├── database/             # SQLAlchemy 2.x Base, naming conventions, engine/session helpers
│   │   ├── exams/                # Exam/question/option models, schemas, router, service, and deterministic MCQ parser
│   │   ├── users/                # application_users ORM model and upsert/role lookup service
│   │   ├── config.py             # Pydantic Settings & environment validation
│   │   └── main.py               # FastAPI factory, CORS, security headers, /, /health, /auth/me, and /api routers
│   ├── tests/                    # Config, auth/RBAC, parser, grading/timer, exams, attempts, IDOR, leakage, concurrency & E2E tests
│   ├── .dockerignore
│   ├── .env.example
│   ├── .python-version
│   ├── alembic.ini
│   ├── Dockerfile
│   ├── pyproject.toml
│   ├── requirements-dev.txt
│   └── requirements.txt
├── docs/
│   ├── agent-coordination.md     # Multi-agent & external peer (Cline) coordination ledger and API contract
│   └── deployment-aws-vercel.md  # Zero-secret AWS CodePipeline/CodeBuild/App Runner + Vercel SPA deployment runbook
├── frontend/
│   ├── public/
│   ├── src/
│   │   ├── components/           # Shared layout/health components, exam runner widgets (exam/), and accessible UI primitives (ui/)
│   │   ├── features/             # Auth context/guards, student dashboard/runner/history, and admin authoring/parser/results
│   │   ├── hooks/                # Custom hooks (useHealthCheck)
│   │   ├── layouts/              # Responsive AppShell with skip link, landmarks, and error boundary
│   │   ├── lib/                  # Public env reader, typed multi-verb API client, Neon Auth client, cn() utility
│   │   ├── pages/                # Route pages (Overview, Student Dashboard/Instructions/Attempt/Result, Admin Dashboard/New/Editor/Results)
│   │   ├── types/                # Shared TypeScript interfaces for foundation, admin, and student workflows
│   │   ├── App.tsx
│   │   ├── index.css
│   │   └── main.tsx
│   ├── components.json
│   ├── eslint.config.js
│   ├── index.html
│   ├── package-lock.json
│   ├── package.json
│   ├── tsconfig.json
│   ├── vercel.json               # Vercel SPA rewrite & security/cache headers (Root Directory = frontend)
│   └── vite.config.ts
├── .env.example
├── .gitignore
├── buildspec.yml                 # AWS CodeBuild gates (security hygiene, Ruff/Alembic/pytest, frontend lint/build, Docker /health, opt-in ECR/Vercel)
├── neon.ts                       # Neon CLI project-as-code config (separate from frontend/ runtime deps)
├── package-lock.json
├── package.json
└── README.md
```

---

## 5. Implemented API & Frontend Surfaces

### Backend Endpoints (`backend/app/`)
- **Public & Identity:**
  - `GET /` — Application metadata (`name`, `version`, `environment`, `status`)
  - `GET /health` — Returns `{"status": "healthy"}` (`200`) with zero secrets or infrastructure details
  - `GET /auth/me` — Requires valid Bearer JWT (`require_identity`), upserts `application_users` keyed by `auth_subject`, and returns `{user_id, auth_subject, email, display_name, role}`
- **Admin Endpoints (`require_admin`, `/api/admin/*`):**
  - `POST /api/admin/exams`, `GET /api/admin/exams`, `GET /api/admin/exams/{exam_id}`, `PATCH /api/admin/exams/{exam_id}`, `DELETE /api/admin/exams/{exam_id}`
  - `POST /api/admin/exams/parse-questions` — Stateless deterministic MCQ parser preview
  - `PUT /api/admin/exams/{exam_id}/questions`, `POST /api/admin/exams/{exam_id}/questions`, `PUT /api/admin/exams/{exam_id}/questions/{question_id}`, `DELETE /api/admin/exams/{exam_id}/questions/{question_id}`
  - `POST /api/admin/exams/{exam_id}/publish`, `POST /api/admin/exams/{exam_id}/close`
  - `GET /api/admin/exams/{exam_id}/results`, `GET /api/admin/attempts/{attempt_id}`
- **Student Endpoints (`require_student`, `/api/exams/*`, `/api/attempts/*`, `/api/student/attempts`):**
  - `GET /api/exams`, `GET /api/exams/{exam_id}` — `PUBLISHED` exams only, excluding `is_correct`
  - `POST /api/exams/{exam_id}/attempts` — Row-locked start/resume with frozen question & option snapshots
  - `GET /api/attempts/{attempt_id}` — Active `IN_PROGRESS` delivery, saved answers, and UTC `expires_at`/`server_now` (auto-finalizes if expired)
  - `PUT /api/attempts/{attempt_id}/answers/{question_id}` — Idempotent autosave rejecting mutations when `now >= expires_at`
  - `POST /api/attempts/{attempt_id}/submit` — Idempotent finalization (`STUDENT_SUBMITTED` or `TIMER_EXPIRED`) and backend `Decimal` grading
  - `GET /api/attempts/{attempt_id}/result` — Owner-isolated result view enforcing `show_result` & post-finalization `show_correct_answers`
  - `GET /api/student/attempts` — Authenticated caller's attempt history

### Frontend Routes (`frontend/src/App.tsx`)
- `/` — Platform overview, health check, and Neon Managed Better Auth sign-in/session card
- `/student/*` (`STUDENT` role): `/student`, `/student/exams/:examId`, `/student/attempts/:attemptId`, `/student/results/:attemptId`
- `/admin/*` (`ADMIN` role): `/admin`, `/admin/exams/new`, `/admin/exams/:examId`, `/admin/exams/:examId/results`

---

## 6. Environment Variable Setup

Never commit `.env`, `.env.local`, or real credentials.

1. Inspect the placeholder-only templates:
   - Root overview: `.env.example`
   - Backend-only variables: `backend/.env.example`
   - Frontend public variables: `frontend/.env.example`
2. Create local env files when running locally:
   - Copy `backend/.env.example` to `backend/.env`
   - Copy `frontend/.env.example` to `frontend/.env.local`
3. Only variables prefixed with `VITE_` are exposed to browser JavaScript bundles. Never place `DATABASE_URL`, `DIRECT_DATABASE_URL`, or server-only credentials into any `VITE_*` variable.

### Environment-Aware Backend Validation

- **`APP_ENV=development` or `test`:** `DATABASE_URL` and Neon Managed Auth JWT variables may remain unset at boot so local smoke checks (`GET /health`) work immediately. Invoking database or Neon Managed Auth verification without configuration raises `ConfigurationError`.
- **`APP_ENV=staging` or `production`:** Startup requires `DATABASE_URL`, `NEON_AUTH_BASE_URL`, `NEON_AUTH_JWKS_URL`, and `https://` non-localhost `CORS_ORIGINS`. OAuth provider secrets remain inside Neon Managed Auth's hosted project configuration.

---

## 7. Local Backend & Frontend Setup

### Backend (from `backend/`)

```bash
python -m venv .venv
# Windows PowerShell: .venv\Scripts\Activate.ps1
# macOS/Linux:        source .venv/bin/activate

pip install --upgrade pip
pip install -r requirements.txt -r requirements-dev.txt

uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend (from `frontend/`)

```bash
npm ci
npm run dev
```

Vite serves the frontend on `http://localhost:5173` by default.

---

## 8. Neon PostgreSQL Configuration & Migrations

- **Driver & URL Normalization:** SQLAlchemy 2.x uses `psycopg` v3 (`psycopg[binary]`). Standard connection strings are normalized internally to `postgresql+psycopg://` without logging credentials.
- **Pooled vs Direct URLs:**
  - Set `DATABASE_URL` to your Neon pooled connection string for runtime API traffic.
  - Set `DIRECT_DATABASE_URL` to your Neon direct (non-`-pooler`) connection string for Alembic migrations.
- **Linear Migration Chain & Safety Rules:**
  - `alembic.ini` intentionally leaves `sqlalchemy.url` blank.
  - Maintain a single linear head (`0001_application_users -> 0002_examination_schema -> 0003_attempt_option_order -> 0004_exam_closed_at_and_indexes`).
  - Never rewrite historical migrations (`0001`–`0003`), never modify `neon_auth.*` tables directly, and never reset, drop, or run `Base.metadata.create_all()` against production databases.

```bash
# From backend/
alembic heads
alembic history
alembic revision --autogenerate -m "describe_change"
alembic upgrade head
```

---

## 9. Neon Managed Better Auth Configuration

- **Hosted Auth Authority:** Authentication is managed externally by Neon Managed Better Auth (`VITE_NEON_AUTH_URL` on the frontend; `NEON_AUTH_JWKS_URL`, `NEON_AUTH_BASE_URL`, and optional `NEON_AUTH_AUDIENCE` on the backend).
- **RBAC Isolation:** Application roles (`STUDENT`, `ADMIN`) live exclusively in PostgreSQL `application_users` keyed by `auth_subject`. Frontend routes enforce fail-closed guards when auth is unconfigured or unauthenticated, while FastAPI remains the sole authorization authority.

---

## 10. Testing & Lint Commands

### Backend (from `backend/`)

```bash
ruff check app tests alembic
alembic heads
alembic history
pytest
```

### Frontend (from `frontend/`)

```bash
npm ci
npm run lint
npm test --if-present
npm run build
```

---

## 11. Docker, CI/CD & Deployment Readiness

Build from repository root using `backend/` as the build context (never copies `.env*` files):

```bash
docker build -f backend/Dockerfile -t examination-hub-api:local backend/
docker run --rm -p 8000:8000 examination-hub-api:local
curl -i http://127.0.0.1:8000/health
```

Target delivery pipeline (prepared in repository; production publishing disabled by default):

```text
GitHub -> AWS CodePipeline -> AWS CodeBuild (buildspec.yml) -> Amazon ECR (examination-hub-api) -> AWS App Runner (FastAPI, port 8000)
                                                            └-> Vercel SPA (Root Directory = frontend, frontend/vercel.json)
```

See the full deployment, security, and coordination documentation:
- [`docs/deployment-aws-vercel.md`](docs/deployment-aws-vercel.md) — AWS CodePipeline/CodeBuild, App Runner, Vercel SPA, Neon Dexta Global, and post-deploy smoke test runbook
- [`docs/agent-coordination.md`](docs/agent-coordination.md) — Multi-agent & peer engineering ownership ledger and locked API contract

---

## 12. Security Notes

- **Secret Protection:** `.gitignore` ignores `.env` and `.env.*` (preserving `.env.example` templates). `backend/.dockerignore` excludes `.env*`, test files, and local `.db`/`.sqlite*` files from container images.
- **Production Hardening:** FastAPI disables `/docs`, `/redoc`, and `/openapi.json` when `APP_ENV=production`, attaches `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy`, and `Cache-Control: no-store`, and masks unhandled exception stack traces behind a `request_id`.
- **Examination Integrity:** `question_options.is_correct` is excluded from student SQL projections and active attempt DTOs, attempts and results enforce per-student `user_id` isolation, deadlines enforce server-side UTC `expires_at`, and grading runs exclusively on the backend using deterministic `Decimal` arithmetic.
