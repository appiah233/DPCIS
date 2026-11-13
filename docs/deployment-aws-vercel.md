# Examination Hub — AWS & Vercel Deployment Readiness Runbook

> **Governance:** Follows `AGENTS.md` (`RULE 4`–`RULE 6`, `RULE 14`, `RULE 23`, `RULE 24`).  
> **Zero-Secret Rule:** This document contains placeholder variable names and architecture contracts ONLY — never real passwords, tokens, keys, or live database URLs.  
> **Production Safety:** Automated repository CI/build files keep backend image publishing disabled by default (`PUSH_IMAGE=false`). Vercel deploys the frontend independently from the `frontend` Root Directory.

---

## 1. Target Delivery Architecture

```text
GitHub (main / PR)
  ├── GitHub Actions (.github/workflows/ci.yml)
  │     ├── security-hygiene (env templates, secret tokens, stale Clerk scan)
  │     ├── backend (Ruff, Alembic single head + offline SQL, Pytest)
  │     ├── frontend (vercel.json parse, npm ci, lint/tsc, test, vite build, dist scan)
  │     └── docker-smoke (backend/Dockerfile build + GET /health probe)
  │
  ├── AWS CodePipeline -> AWS CodeBuild (buildspec.yml)
        ├── Quality & Security Gates (same backend, frontend, template, and container /health checks)
        └── Backend Container -> Amazon ECR (examination-hub-api)
                              -> Amazon ECS Express Mode / Fargate
                              -> managed Application Load Balancer -> FastAPI (port 8000)
  │
  └── Vercel -> Frontend SPA (Root Directory = frontend, frontend/vercel.json)
```

---

## 2. Backend Deployment Readiness (AWS CodePipeline / CodeBuild -> ECR -> ECS Express Mode)

### Container & Docker Readiness (`backend/Dockerfile` & `backend/.dockerignore`)
- Multi-stage `python:3.12-slim` image running as non-root user `appuser` (`10001:10001`).
- Copies only `alembic.ini`, `alembic/`, and `app/` (`.dockerignore` excludes `.env*`, `.venv/`, `tests/`, `*.db`, `*.sqlite*`, `.git/`, and `*.md`).
- Exposes port `8000` and runs:
  `uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips '*'`
- Includes a stdlib Python `HEALTHCHECK` against `http://127.0.0.1:${PORT:-8000}/health`.

### AWS CodeBuild (`buildspec.yml`) Configuration Notes
- Requires **Docker privileged mode** (`PrivilegedMode: true`) in the AWS CodeBuild project so `docker build` and container `/health` smoke checks can run.
- The default `PUSH_IMAGE=false` flag is non-destructive. Set it to `"true"` with `AWS_ACCOUNT_ID`, `AWS_DEFAULT_REGION`, and `IMAGE_REPO_NAME` only in an authorized backend publish stage.
- When `PUSH_IMAGE=true`, CodeBuild writes `imageDetail.json` pointing to `${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_DEFAULT_REGION}.amazonaws.com/examination-hub-api:<commit12>`.
- The verified immutable image for source revision `9e35bb41fbb7` is `examination-hub-api:9e35bb41fbb7`.
- CodeBuild does not deploy the Vercel frontend. Vercel builds the `frontend` directory independently.

### ECS Express Mode Runtime Configuration
- **Port:** `8000`
- **Health Check:** HTTP `GET /health` -> `200 OK` (`{"status": "healthy"}`)
- **Compute & Ingress:** ECS Express Mode runs the image on Fargate and manages HTTPS ingress through its load-balancing resources. Use the actual service URL returned by ECS only after the service becomes active and `/health` succeeds.
- **Secrets Injection:** Store sensitive runtime settings in **AWS Secrets Manager** (or encrypted SSM Parameter Store) and reference them through the ECS primary container `secrets` configuration. The task execution role requires scoped access to retrieve them. Never bake secrets into the image, Docker build args, CodeBuild plaintext variables, or tracked task configuration:
  - `DATABASE_URL` — Neon **pooled** (`-pooler`) PostgreSQL connection string
- **Non-Secret Runtime Environment Variables:**
  - `NEON_AUTH_BASE_URL`, `NEON_AUTH_JWKS_URL` — Neon Managed Auth JWT verification settings
  - `APP_ENV=production` (or `staging`) — enforces `https://` non-localhost `CORS_ORIGINS`, disables `/docs`, `/redoc`, and `/openapi.json`, and masks validation error internals
  - `LOG_LEVEL=INFO`
  - `CORS_ORIGINS=["https://<your-vercel-domain>"]` (JSON array; exact scheme + host, no wildcard `*`, no trailing slash)

### Current ECS Staging State
- CodePipeline and CodeBuild have successfully built and published `examination-hub-api:9e35bb41fbb7`.
- ECS Express Mode has launched the FastAPI container far enough to expose the application startup error.
- Current startup blocker: `Missing required settings for APP_ENV='staging': DATABASE_URL`.
- The earlier `CORS_ORIGINS` parsing failure is resolved by supplying the value as a JSON array.
- Do not derive, guess, or document a production API endpoint while the service is unhealthy. After `DATABASE_URL` is injected and the ECS service becomes active, verify `GET /health` through the ECS HTTPS endpoint before using that origin anywhere else.

### Pre-Deploy Database Migrations (Alembic)
- **Never** auto-run `alembic upgrade head` inside container boot (`CMD`) to avoid multi-replica startup races.
- Run migrations as an explicit, authorized pre-deploy job using `DIRECT_DATABASE_URL` (Neon **non-pooled** direct connection string):
  ```bash
  cd backend
  alembic heads
  alembic upgrade head
  ```
- Single linear Alembic chain (`RULE 4`):
  `0001_application_users -> 0002_examination_schema -> 0003_attempt_option_order -> 0004_exam_closed_at_and_indexes`

---

## 3. Frontend Deployment Readiness (Vercel SPA)

### Project & Root Directory Settings
- **Vercel Root Directory:** `frontend` (where `frontend/package.json`, `frontend/vite.config.ts`, `frontend/package-lock.json`, and `frontend/vercel.json` reside).
- **Root vs `frontend/` Dependency Isolation (Section 28):**
  - Root `package.json`, `package-lock.json`, and `neon.ts` hold `@neon/config` (`@neon/sdk`) solely for Neon project-as-code CLI metadata (`neon.ts`). Keep them separate from `frontend/` and **never** run `neon deploy` autonomously (`RULE 5`).
  - `frontend/package.json` is an independent Vite + React 19 application package using `@neondatabase/auth` for Neon Managed Auth sessions and `react-router-dom` (`BrowserRouter`).
  - Both trees have **zero** Clerk dependencies (`RULE 6`).
  - Always install frontend dependencies inside `frontend/` via `npm ci` (cleans any extraneous packages such as leftover `@neon/*` directories under `frontend/node_modules`).

### `frontend/vercel.json` Behavior
- Configures Vite build (`npm ci`, `npm run build`, output `dist`).
- **SPA Rewrite:** Rewrites non-asset client routes (`/student`, `/admin`, nested exam/attempt routes) via `/((?!assets/).*) -> /index.html` so browser refreshes never return 404.
- **Security & Cache Headers:** Sets `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: strict-origin-when-cross-origin`, `Permissions-Policy`, immutable caching on `/assets/*`, and `Cache-Control: no-cache` on `/index.html`.

### Vercel Environment Variables (Public Only)
Configure ONLY public `VITE_*` build-time variables in Vercel (never server secrets):
- `VITE_NEON_AUTH_URL` — Public Neon Managed Auth URL for the target branch
- `VITE_API_BASE_URL` — Leave unset until the ECS Express Mode service is healthy. Then set it to the actual verified ECS HTTPS API origin, with no trailing slash.

The frontend remains Vercel-only. Do not deploy FastAPI through Vercel and do not add a root Vercel configuration that proxies or hosts the backend.

---

## 4. Neon Database & Auth, GitHub Workflow Risk Notes

- **Authoritative Neon Target (`RULE 5`):** Organization **Dexta Global** (`org-weathered-mud-72902193`, tracked in `.neon`), project **DCPIS Exam Hub** (`noisy-boat-95673317`).
- **Auth / CORS Alignment:** Add the deployed Vercel origin to backend `CORS_ORIGINS`; register the deployed Vercel origin as a Neon Auth trusted domain.
- **`.github/workflows/neon_workflow.yml` Risk Notes (Tracked Baseline — Left Unmodified):**
  - **Missing `permissions:` block:** Inherits default repository token permissions instead of explicit `contents: read`.
  - **Unpinned third-party actions:** Uses mutable major tags (`tj-actions/branch-names@v8`, `neondatabase/create-branch-action@v6`, `neondatabase/delete-branch-action@v3`) rather than commit SHAs; `tj-actions/branch-names` can be replaced with built-in `${{ github.head_ref }}` with branch sanitization.
  - **Fork PR & external config risk:** Lacks a guard for fork PRs where `secrets.NEON_API_KEY` is unavailable, and relies on external GitHub repo variable `vars.NEON_PROJECT_ID` matching Dexta Global (`noisy-boat-95673317`) — verify in GitHub Settings before enabling PR preview branching.
  - **Scope:** Strictly non-production PR preview branches only; never target production data.

---

## 5. Post-Deploy Smoke Test Checklist (Authorized Staging/Prod Releases Only)

1. **Backend Health & Root:**
   - `GET https://<api-origin>/health` -> HTTP `200`, body `{"status":"healthy"}` (verify `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Cache-Control: no-store`).
   - `GET https://<api-origin>/docs` and `/openapi.json` -> HTTP `404` when `APP_ENV=production`.
2. **Frontend SPA & Deep-Link Routing:**
   - `GET https://<vercel-origin>/`, `/student`, and `/admin` -> HTTP `200` returning SPA `index.html`.
   - Set `VITE_API_BASE_URL` only after the backend health check above succeeds, then redeploy the frontend.
   - Load the Vercel frontend in a real browser and confirm its request to `<verified-api-origin>/health` returns `200` without CORS errors in DevTools. Production connectivity is not verified until this browser request succeeds.
3. **Bundle Secret Verification:**
   - Confirm no server secrets (`DATABASE_URL`, `DIRECT_DATABASE_URL`, database passwords, or provider secret keys) or Clerk artifacts exist in deployed assets.
