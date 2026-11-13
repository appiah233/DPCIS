# Examination Hub

Examination Hub is a responsive web application for creating, taking, and grading timed multiple-choice examinations. Administrators prepare questions and exam rules; students take focused, one-question-at-a-time sittings with saved answers and a server-controlled timer. Final scores appear only after an attempt ends and only when the administrator enables results.

**Project status:** The core authoring, exam delivery, grading, and role-based access flows are implemented. Live deployment connectivity and authenticated browser journeys still require end-to-end verification.

---

## 1. What the project does

- **Build exams:** Administrators set duration, questions per attempt, pass mark, retake limit, question and option order, and result visibility.
- **Import questions:** Paste MCQ text or choose or drop a `.txt`/`.md` file, preview the parsed questions, correct them, and save them before publishing.
- **Publish to students:** Published exams appear for all students. Administrators can close an exam to stop new attempts and review participant results.
- **Take timed sittings:** Students move between questions, see only answered/unanswered progress, and can resume a saved attempt. FastAPI enforces the timer and final submission.
- **Grade securely:** The server grades answers and controls score and answer-key disclosure after finalization. The browser never decides correctness or the final score.
- **Separate access roles:** Neon Managed Auth handles sign-in; Neon PostgreSQL stores the authoritative `STUDENT` and `ADMIN` roles checked by FastAPI.

---

## 2. Architecture Overview

The repository separates API logic, responsive browser UI, identity, database persistence, and CI/CD deployment concerns:

- **Backend (`backend/`):** Python 3.12 + FastAPI application (`app.main:create_app`) with environment-driven Pydantic v2 settings, strict security headers, sanitized error responses (`X-Request-ID`), SQLAlchemy 2.x + Alembic linear migrations, RBAC dependencies (`require_identity`, `require_student`, `require_admin`), deterministic MCQ parser (`app/exams/parser.py`), transactional attempt engine (`app/attempts/service.py`), and pure `Decimal` grading/expiry logic (`app/attempts/grading.py`).
- **Frontend (`frontend/`):** React 19 + TypeScript + Vite + Tailwind CSS v4 + accessible UI primitives, `BrowserRouter` SPA routes (`/`, `/student/*`, `/admin/*`), Neon Managed Better Auth session integration (`@neondatabase/auth`), fail-closed `ProtectedRoute` guards, and Vercel SPA rewrite configuration (`frontend/vercel.json`).
- **Authentication (Neon Managed Better Auth):** Owned externally by Neon Managed Better Auth. FastAPI verifies EdDSA Bearer JWTs via JWKS and resolves/upserts local PostgreSQL roles in `application_users` keyed by the immutable JWT subject (`auth_subject` / `sub`), never relying on email addresses or client-supplied role claims.
- **Database:** Neon PostgreSQL managed via SQLAlchemy 2.x and Alembic migrations. Runtime traffic uses `DATABASE_URL` (pooled Neon endpoint recommended in deployed environments), while Alembic uses `DIRECT_DATABASE_URL` (falling back to `DATABASE_URL` when unset).

---

## 3. Tools and technologies

| Area | Tools | How they are used |
|---|---|---|
| Web interface | React 19, TypeScript, Vite, Tailwind CSS v4, React Router, accessible UI components | One responsive application for student and administrator workflows |
| API and exam engine | Python 3.12, FastAPI, Pydantic, SQLAlchemy, `psycopg` | Exam authoring, question delivery, autosave, timer enforcement, grading, and authorization |
| Accounts and data | Neon Managed Better Auth, Neon PostgreSQL | Account sessions and the database-backed `STUDENT`/`ADMIN` role and exam records |
| Database changes | Alembic | Versioned, additive schema migrations |
| Authentication checks | PyJWT and Neon JWKS | Verification of signed bearer tokens before API access |
| Quality checks | pytest, Ruff, ESLint, TypeScript, GitHub Actions | Backend tests, static checks, frontend build, and CI |
| Delivery | Docker, AWS CodePipeline/CodeBuild, Amazon ECR, Amazon ECS Express Mode, Vercel, CloudWatch | Backend build and hosting pipeline, separate frontend hosting, and logs; live connectivity is still being verified |

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
│   └── deployment-aws-vercel.md  # Zero-secret AWS CodePipeline/CodeBuild/ECS Express Mode + Vercel SPA deployment runbook
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
2. Local development defaults work out of the box for `/health` and unauthenticated checks (`VITE_API_BASE_URL` defaults to `http://127.0.0.1:8000` when unset, and development `CORS_ORIGINS` allows both `http://localhost:5173` and `http://127.0.0.1:5173`, keeping explicit `VITE_API_BASE_URL` requests with no Vite proxy). When configuring database or Neon Managed Auth locally:
   - Copy `backend/.env.example` to `backend/.env`
   - Put dev-only frontend overrides in `frontend/.env.development.local` (applies to `npm run dev` only, avoiding polluting local `npm run build` / `dist/`), or use gitignored `frontend/.env.local` strictly for public `VITE_*` frontend auth/API config when testing local `dev` and `preview` builds (never run `vercel deploy --prebuilt` locally while `frontend/.env.local` exists). In Vercel/production, configure `VITE_API_BASE_URL` explicitly in project environment variables.
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

python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

FastAPI binds loopback IPv4 (`http://127.0.0.1:8000`) for local `--reload` development, matching the frontend `VITE_API_BASE_URL` default and local `/health` checks.

### Frontend (from `frontend/`)

```bash
npm ci
npm run dev
```

Vite serves the frontend on `http://localhost:5173` by default; local backend development `CORS_ORIGINS` permits both `http://localhost:5173` (primary) and `http://127.0.0.1:5173`.

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
GitHub -> AWS CodePipeline -> AWS CodeBuild (buildspec.yml) -> Amazon ECR (examination-hub-api)
                                                            -> Amazon ECS Express Mode / Fargate
                                                            -> managed Application Load Balancer -> FastAPI (port 8000)

GitHub -> Vercel SPA (Root Directory = frontend, frontend/vercel.json)
```

See the full deployment, security, and coordination documentation:
- [`docs/deployment-aws-vercel.md`](docs/deployment-aws-vercel.md) — AWS CodePipeline/CodeBuild, ECS Express Mode, Vercel SPA, Neon Dexta Global, and post-deploy smoke test runbook
- [`docs/agent-coordination.md`](docs/agent-coordination.md) — Multi-agent & peer engineering ownership ledger and locked API contract

---

## 12. Security Notes

- **Secret Protection:** `.gitignore` ignores `.env` and `.env.*` (preserving `.env.example` templates). `backend/.dockerignore` excludes `.env*`, test files, and local `.db`/`.sqlite*` files from container images.
- **Production Hardening:** FastAPI disables `/docs`, `/redoc`, and `/openapi.json` when `APP_ENV=production`, attaches `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy`, and `Cache-Control: no-store`, and masks unhandled exception stack traces behind a `request_id`.
- **Examination Integrity:** `question_options.is_correct` is excluded from student SQL projections and active attempt DTOs, attempts and results enforce per-student `user_id` isolation, deadlines enforce server-side UTC `expires_at`, and grading runs exclusively on the backend using deterministic `Decimal` arithmetic.
