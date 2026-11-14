# Workspace Engineering Rules — Examination Hub (`C:\Users\EricAppiahOwusu\Music\DPCIS`)

> **Scope:** Workspace-scoped governance for **Examination Hub** in `C:\Users\EricAppiahOwusu\Music\DPCIS`.  
> All Antigravity/Gemini agents working in this repository MUST follow these rules. **Cline** operates concurrently as an **external peer engineering worker**; shared coordination rules in this file and in `docs/agent-coordination.md` apply across both teams. Valid user-global rules outside this workspace remain untouched.

---

## Core Engineering & Verification Rules

### RULE 1 — INVESTIGATE BEFORE IMPLEMENTING

Every agent must understand the existing implementation, affected workflows, architecture, database consequences, tests, security implications, and concurrent workspace activity before changing code.

### RULE 2 — TEST BEFORE IMPLEMENTING

For meaningful domain logic, define expected behavior, happy paths, failure paths, edge cases, security cases, authorization cases, and concurrency cases before claiming implementation.

### RULE 3 — EVIDENCE, NOT CLAIMS

Never report `DONE`, `COMPLETE`, `FIXED`, `PASS`, or `VERIFIED` without executed evidence observed directly from tool output. When evidence is incomplete, report `PARTIAL`, `BLOCKED`, or `NOT IMPLEMENTED`.

### RULE 22 — LITERATE ENGINEERING

For important domain algorithms (e.g., MCQ question parser, deterministic grading, timer enforcement, stable option/question randomization snapshot), define problem, invariants, assumptions, edge cases, correctness, complexity where meaningful, and test strategy before final implementation.

### RULE 24 — QUALITY GATES

- **Backend:** `ruff check app tests alembic`, `pytest`, `alembic heads`, `alembic history`
- **Frontend:** clean `npm ci`, ESLint (`npm run lint`), TypeScript (`tsc -b`), configured frontend tests, production build (`vite build`)
- **UI:** actual Playwright / Chrome DevTools rendered & responsive verification across mobile, tablet, and desktop viewports (`320`, `360`, `375`, `390`, `412`, `768`, `1024`, `1280`, `1440+`).

---

## Database & Neon Safety Rules

### RULE 4 — DATABASE SAFETY

Never:

- rewrite historical migrations casually (`0001_application_users`, `0002_examination_schema`, `0003_attempt_option_order`)
- reset production
- drop production tables
- use production for automated tests
- replace migration history with schema push
- modify Neon-managed authentication tables (`neon_auth.*`) directly

Always use additive Alembic migrations. Keep a single linear Alembic head.

### RULE 5 — NEON SAFETY

- The correct Neon organization is **Dexta Global** (`org-weathered-mud-72902193`, project `DCPIS Exam Hub` / `noisy-boat-95673317`).
- The CLI previously selected the wrong organization (**Eric** / `org-raspy-sunset-55790868`), which currently matches the read-only Neon MCP key in user config.
- NEVER create another Neon project merely because the intended project cannot be accessed via MCP.
- NEVER create another Neon organization.
- NEVER run `neon deploy` against an unverified target.
- Do not expose credentials.
- If live non-production Neon branch access is unavailable or unsafe: treat `LIVE NEON = BLOCKED` and continue safely executable local/isolated test work.

---

## Authentication, Authorization & Examination Integrity

### RULE 6 — AUTHENTICATION

Authentication uses **Neon Managed Better Auth**. Clerk has been removed (`my-clerk-next-app` deletions in workspace). **Do NOT reintroduce Clerk** anywhere in backend, frontend, env templates, dependencies, or CI. Application authorization is strictly separate from authentication.

### RULE 7 — AUTHORIZATION (RBAC)

Roles are `ADMIN` and `STUDENT` (stored in `application_users.role` keyed by `auth_subject` = JWT `sub`). Backend authorization via `require_identity`, `require_student`, and `require_admin` is authoritative. Never trust roles received from React, request JSON, query strings, `localStorage`, or unverified/client-controlled token role claims.

### RULE 8 — SERVER AUTHORITY

FastAPI owns: exam eligibility, attempt ownership, attempt state, question selection, question/option ordering, timer (`started_at`, `expires_at`), expiration, grading, percentage, pass/fail, and final score. React only presents server truth.

### RULE 9 — SCORE SECURITY

Never accept authoritative `score`, `percentage`, `passed`, `correct_answers`, `points_earned`, or `is_correct` from the frontend.

### RULE 10 — ANSWER-KEY SECURITY

Active student examination APIs (list, instructions, start, load/resume, autosave) MUST NOT expose `is_correct`, `correct_option_id`, answer keys, or grading metadata. Post-submission `show_correct_answers` may only be returned after finalization when `exam.show_correct_answers` is `True`.

### RULE 11 — AUTHORITATIVE TIMER

The server sets `started_at` (UTC) and `expires_at = started_at + duration`. Browser refresh, closing/reopening, or client-side clock manipulation CANNOT reset the timer or extend `expires_at`. Mutations where `now >= expires_at` MUST reject answer changes and safely finalize the attempt via the single idempotent finalization path (`STUDENT_SUBMITTED` or `TIMER_EXPIRED`).

---

## Product, UI & Platform Rules

### RULE 12 — ONE RESPONSIVE WEB APPLICATION

There is **NO native mobile application**. Do NOT create React Native, Expo, Flutter, Android, or iOS projects. "Mobile" means **responsive mobile web** inside the single React Vite application (`frontend/`) supporting desktop, tablet, and mobile browsers seamlessly.

### RULE 13 — HUMAN-FIRST DESIGN & VISUAL DIRECTION

Use design-system-first, mobile-first, accessible, human-first engineering:

- Light neutral assessment surface, crisp dark typography, restrained red accent for active exam controls/emphasis, circular radio-style option badges (`A`–`D`), clear selected state, clear progress indicator, large readable question typography, generous spacing, minimal distraction.
- Do NOT copy irrelevant third-party survey wording, sushi content, device chrome/frames, or phone status bars.
- Require semantic HTML, full keyboard navigation, visible `:focus-visible` states, WCAG AA contrast, touch-friendly tap targets (`>= 44x44px`), responsive layouts without horizontal overflow (`320px` to `1440px+`), loading states, error states, empty/zero states, and **real backend API data only** (no fake/mocked UI datasets).

---

## Security, Secrets & Production Restrictions

### RULE 14 — PRODUCTION RESTRICTIONS

No autonomous:

- production deployment (Vercel or AWS)
- production Neon mutation or production Alembic migration
- AWS infrastructure creation/deletion, IAM mutation, or DNS mutation
- `git commit`, `git push`, `merge`, PR creation, `git reset --hard`, `git checkout .`, force push, history rewrite, or secret rotation

without explicit user authorization.

### RULE 23 — SECURITY & SECRETS

Never print or commit API keys, database URLs, passwords, OAuth secrets, JWTs, Vercel tokens, or AWS credentials (never populate `.env.example`, docs, `docs/agent-coordination.md`, logs, or final reports with live secrets). Avoid logging student answer content unnecessarily. Run pre-completion scans for secrets, bundle secret leakage, and stale Clerk references.

---

## Multi-Agent Ownership, MCP & Cline Peer Coordination

### RULE 15 — MCP RESPONSIBILITIES

Use MCPs/tools deliberately according to each subagent's scope (do not grant every subagent every MCP):

- **GitHub:** repository/CI inspection
- **Neon:** safe read-only / non-production database investigation
- **Playwright:** actual browser & E2E verification
- **Chrome DevTools:** console, network, CORS, runtime inspection
- **Vercel / AWS:** deployment/CI/CD pipeline readiness & non-destructive inspection

### RULE 16 — MULTI-AGENT FILE OWNERSHIP

Each of the 12 Antigravity subagents owns explicit files/directories. Before editing another agent's area or shared contracts, coordinate through **ArchitectAgent**. Never use destructive git operations (`git reset --hard`, force checkout, `git clean`, discard-all, force push) to resolve concurrent changes.

### RULE 17 — CLINE IS AN EXTERNAL PEER WORKER

**Cline** is actively working in this same workspace as an independent peer engineering worker (NOT an Antigravity subordinate). Treat Cline's modifications as legitimate peer work unless verified evidence proves a defect.
NEVER:

- overwrite Cline changes blindly
- revert or delete Cline files merely because they appeared unexpectedly
- reset files touched by Cline
- claim ownership of work Cline completed
- duplicate Cline work unnecessarily

If Cline modifies a file while an Antigravity agent is working on it: **STOP editing that file**, inspect the current contents/`git diff`, classify whether the change complements, overlaps, conflicts, or supersedes the task, and coordinate through **ArchitectAgent** and `docs/agent-coordination.md` before proceeding.

### RULE 18 — COORDINATION LEDGER (`docs/agent-coordination.md`)

Maintain `docs/agent-coordination.md` as the primary asynchronous coordination ledger across all 12 Antigravity subagents and **Cline**. **ArchitectAgent** normalizes this ledger with fields: `WORKSTREAM`, `OWNER`, `STATUS`, `FILES/DIRECTORIES`, `DEPENDENCIES`, `LAST UPDATE`, `BLOCKER`, `HANDOFF NOTES`.

### RULE 19 — COMMUNICATING WITH CLINE

Use repository-visible notes in `docs/agent-coordination.md` (and `docs/handoffs/` only if needed) so Cline can see active ownership and contracts without accessing secret data. Never include secrets, tokens, passwords, or database URLs in coordination files.

### RULE 20 — DETECTING CLINE ACTIVITY

Inspect `git status --short`, `git diff`, and recent file modification timestamps at logical checkpoints (before editing shared files, before creating migrations, before backend/frontend integration, before testing, before final reporting) — never in tight infinite polling loops.

### RULE 21 — CONFLICT RESOLUTION

When Antigravity and Cline produce overlapping implementations, NEVER automatically favor Antigravity's version. **ArchitectAgent** must evaluate correctness, tests, architecture, security, maintainability, design-system compliance, UX, accessibility, and integration cost, keep/integrate the stronger implementation cleanly, and never leave duplicate dead implementations side-by-side.

### RULE 25 — HANDOFF

Every workstream and interface decision must be documented clearly enough for another Antigravity agent, Cline, or the user to pick up cleanly without relying on unpersisted agent memory.
