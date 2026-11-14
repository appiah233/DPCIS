# Examination Hub — One-Page Design Direction Brief (`design-direction.md`)

> **Status:** `APPROVED`
> **Brand Anchor:** Deep Rose-Burgundy Brand (`#9f1239` / `--accent-primary`) on a calm, warm off-white assessment canvas (`#f7f8fa`), with a visibly distinct Warm Vermilion Danger hue (`#c2250a` / `--danger`) and a Deep Slate-Ink Selected-Answer state (`#0f172a` / `--selected-border`).

---

## 1. Core Design Principles (Tied to Research Evidence)

1. **Calm, High-Trust Assessment Focus** *(Evidence: `[DOC]` Inspera Assessment `R2`, `[SEEN]`/`[DOC]` SAT Bluebook `R5`, `[DOC]` TAO Advance `R3`)*
   - During an examination sitting, non-essential navigation links, footers, and decorative banners disappear. The candidate sees only the active question, clear option controls, quiet server-autosave confirmation, and a tabular-numeral countdown timer that alerts only at `5m`, `1m`, and `0s`.
2. **Unambiguous Hierarchy & Scannable Density** *(Evidence: `[SEEN]` Linear `07-linear-interface.png` & Stripe Dashboard `06-stripe-dashboard-docs.png`, `[DOC]` Gradescope `R7`)*
   - Every workspace page begins with a standardized `<PageHeader>` (`breadcrumbs`, `eyebrow`, `title`, `description`, `meta`, right-aligned `actions`) followed by a compact `StatCard` strip (`2–5` KPIs) and border-aligned `<Card>` or `<ResponsiveTable>` surfaces (`1px solid var(--border-default)`). Dark marketing hero banners (`.portal-hero*`) are retired from logged-in workspaces.
3. **Ergonomic, Mode-Aware Answer Selection & Non-Error Selected State** *(Evidence: `[SEEN]`/`[DOC]` SAT Bluebook `R5`, `[DOC]` Canvas New Quizzes `R1`, `[DOC]` Gradescope `R7`)*
   - **Text-only questions (`!hasImage`):** Render full-width bordered option rows (`min-height: 52px`) with circular `A`–`D` badges and a `60–70ch` measure on the question stem and option text.
   - **Image-based PDF-crop questions (`hasImage`):** Since options `A`–`D` are already inside the ~200 DPI PDF crop image, render **four large `A`–`D` selector buttons** (`min-height: 56px`, 4-across `grid-cols-4` on desktop `>= 640px`, `2x2` `grid-cols-2` on narrow screens `< 640px`) with a check icon on selection—never redundant full-width text rows.
   - **Selected-answer visual distinction:** Selected options use a **Neutral Deep Slate-Ink style** (`--selected-border: #0f172a`, `--selected-bg: #f1f5f9`, solid `#0f172a` badge with white letter + check icon `✓ Selected`) so a selected answer never looks like an error or incorrect response.
4. **Precision Authoring for Bulk Text & PDF Question Import** *(Evidence: `[DOC]` Gradescope `R7`)*
   - The Admin Exam Editor (`BulkParserPanel` + `PdfCropEditor` + `QuestionListEditor`) pairs 200 DPI PDF region crops with status pills (`Ready` vs. `Needs attention`), interactive top/bottom crop sliders, `A`–`D` answer-key pills, and merge/split controls.
5. **Single Token Source of Truth (Target Verified by Automated Guard)**
   - **Target:** Eliminate all `65` baseline non-token hard-coded colors (`21` hex, `24` `rgb(...)`, `20` raw Tailwind palette classes) outside `frontend/src/index.css` token definitions, verified continuously by the Step 6D `legacy-style` guard script.

---

## 2. Approved Layout Models & Modal/Drawer Architecture

| Layout Shell | Routes Covered | Structural Specification |
| --- | --- | --- |
| **`PublicLayout`** | `/`, and `*` (`404` when signed out) | Clean top brand header (`60px`), centered split-screen auth container (`1160px` max on `/`, `440px` auth card) or centered `640px` utility panel on `404`, minimal institutional footer. **Note:** For signed-in `STUDENT` or `ADMIN` users hitting `*` (`404`), `AppShell` preserves their active role shell (`StudentLayout` or `AdminLayout`) so navigation is never lost. |
| **`StudentLayout`** | `/student`, `/student/exams/:examId`, `/student/results/:attemptId` (plus signed-in student `404`) | Sticky `60px` top header (brand lockup, `Examinations` nav link, student identity pill + `Sign out`), `1160px` centered main container (`24px`–`32px` padding), standardized `<PageHeader>`, and footer. **Result Page = Option A** (Score Hero Card + 4-KPI strip + filterable `ResultReviewCard` feed) **plus a conditional Item-Map jump strip** inside the review section when `show_correct_answers === true`. |
| **`FocusLayout`** | `/student/attempts/:attemptId` | Distraction-free `56px` sticky top bar (`Exam Title`, autosave badge, `ExamTimerBadge`, `Submit Exam` button). **Attempt Screen = Option A on desktop (`>= 1024px`)**: `1280px` container with **`minmax(0, 920px)` question card** + `24px` gap + **`288px` sticky right Question Map rail**. **Below `1024px`:** right rail hides and a **persistent bottom bar** (`"Question X of N · Y answered"`) opens `QuestionNavigatorDialog`. |
| **`AdminLayout`** | `/admin`, `/admin/exams`, `/admin/results`, `/admin/exams/new`, `/admin/exams/:examId`, `/admin/exams/:examId/results` (plus signed-in admin `404`) | Desktop (`>= 1024px`) persistent `240px` left sidebar (`Overview`, `Examinations`, `Results`, admin identity + `Sign out`) + scrollable main work area (`1280px` max container) with `<PageHeader>`. Below `1024px`, navigation opens in a **modal drawer (`<Dialog>` with focus trap, `Escape` close, and focus restoration — NOT `popover="auto"`)**. |

- **Drawers & Navigators Rule:** Every mobile navigation drawer, `QuestionNavigatorDialog`, `AttemptDetailDialog`, `ConfirmDialog`, and image-zoom lightbox uses our native `<dialog>.showModal()` primitive (`Dialog`) with focus trapping, backdrop/Escape dismissal, and focus restoration to the trigger element (no `popover="auto"` navigation menus).

---

## 3. Color Swatches, Hue Separation & Verified WCAG Contrast Ratios

Brand Crimson (`343°` deep rose-burgundy), Danger (`9°` warm vermilion-scarlet — **26° hue separation**), and Selected-Answer (`222°` deep slate-ink) are strictly separated:

| Semantic Role | Token Name | Hex Swatch | Paired Surface / Text | Verified WCAG 2.1 Contrast Ratio | Usage Scope |
| --- | --- | --- | --- | --- | --- |
| **Brand Primary** | `--accent-primary` / `--accent-hover` | `■ #9f1239` / `■ #881337` | On `#ffffff` (`--bg-surface` / `--text-on-accent`) | **`7.49 : 1`** (AAA) / **`9.18 : 1`** (AAA) | Brand mark, primary CTAs (`Sign in`, `Start Examination`, `Next`, `Save`), active nav indicator, eyebrow kickers. |
| **Brand Subtle** | `--accent-subtle` / `--accent-border` | `■ #fff1f2` / `■ #fecdd3` | Text `#9f1239` on `#fff1f2` | **`6.92 : 1`** (AA/AAA) | Active nav pill background, subtle brand callouts. |
| **Selected Answer (Ink)** | `--selected-border` / `--selected-badge-bg` | `■ #0f172a` (`slate-900`) | `#ffffff` on `#0f172a` badge; `#0f172a` text on `--selected-bg` (`#f1f5f9`) | **`17.85 : 1`** (AAA) / **`16.12 : 1`** (AAA) | Selected MCQ option border (`2px`), solid `A`–`D` badge fill, `✓ Selected` indicator, current question tile in navigator. |
| **Danger / Error / Incorrect** | `--danger` / `--danger-hover` | `■ #c2250a` / `■ #9e1c06` | `#ffffff` on `#c2250a`; `#c2250a` text on `--danger-subtle` (`#fff4f1`) | **`5.78 : 1`** (AA) / **`5.37 : 1`** (AA) | Validation errors, destructive buttons (`Delete`), critical timer (`<= 60s`), `Incorrect` / `Failed` result badges. |
| **Success / Correct** | `--success` / `--success-subtle` | `■ #166534` / `■ #f0fdf4` | `#166534` on `#f0fdf4` (`--success-border: #86efac`) | **`6.76 : 1`** (AA) | `Passed`, `Correct answer`, `Published` status, `Saved` indicator. |
| **Warning / Caution** | `--warning` / `--warning-subtle` | `■ #92400e` / `■ #fffbeb` | `#92400e` on `#fffbeb` (`--warning-border: #fcd34d`) | **`6.68 : 1`** (AA) | Timer warning (`<= 5m`), `Auto-submitted`, parser warnings, `409` in-progress notice. |
| **Info / Neutral Active** | `--info` / `--info-subtle` | `■ #1e40af` / `■ #eff6ff` | `#1e40af` on `#eff6ff` (`--info-border: #93c5fd`) | **`6.70 : 1`** (AA) | `In progress` attempt pills, informational notices. |

---

## 4. Typography, Spacing, Radius, Shadow, Motion & State Tokens

- **Typography & `60–70ch` Rule:** `--font-sans` (`Inter, system-ui, sans-serif`) and `--font-mono` (`JetBrains Mono, ui-monospace, monospace`). Scale: `--text-xs` (`12px`/`16px`), `--text-sm` (`14px`/`20px`), `--text-base` (`16px`/`24px`), `--text-lg` (`18px`/`28px`), `--text-xl` (`20px`/`28px`), `--text-2xl` (`24px`/`32px`), `--text-3xl` (`30px`/`36px`). **The `60–70ch` line-length cap applies strictly to text-only question stems/descriptions (`!hasImage`)**; image-based questions use the full inner width of the `920px` card.
- **200 DPI PDF Crop Legibility & Tap-to-Zoom:** Full-page PDF crops (`~1400–1650px` wide at `200 DPI`) render inside the **`920px`** desktop question card (`872px` inner width = `~0.58x` scale, keeping `10pt` source text at `~16px` CSS height without zoom on `1280px` and `1440px` viewports). Clicking/tapping any `AuthenticatedPdfImage` opens a full-resolution zoomable modal `<Dialog>` (plus native pinch-zoom on mobile).
- **Spacing Scale (`4px` base):** `--space-1` (`4px`), `--space-2` (`8px`), `--space-3` (`12px`), `--space-4` (`16px`), `--space-5` (`20px`), `--space-6` (`24px`), `--space-8` (`32px`), `--space-10` (`40px`), `--space-12` (`48px`), `--space-16` (`64px`).
- **Radius, Shadow & Motion Tokens:** `--radius-sm` (`6px`), `--radius-md` (`10px`), `--radius-lg` (`14px`), `--radius-xl` (`18px`), `--radius-full` (`9999px`); `--shadow-xs` (`0 1px 2px rgb(15 23 42 / 0.05)`), `--shadow-sm` (`0 2px 6px rgb(15 23 42 / 0.06)`), `--shadow-md` (`0 8px 24px rgb(15 23 42 / 0.10)`), `--shadow-lg` (`0 20px 40px rgb(15 23 42 / 0.16)`); `--ease-standard` (`cubic-bezier(0.2, 0, 0, 1)`), `--duration-fast` (`150ms`), `--duration-normal` (`220ms`), respecting `prefers-reduced-motion: reduce`.
- **Loading / Empty / Error State Patterns & Print Stylesheet:**
  - `LoadingStatePanel` (layout-matched `Skeleton` cards with `role="status"`), `EmptyStatePanel` (centered icon badge, title, concise description, optional primary CTA), `ErrorStatePanel` (semantic `--danger` alert card with `Try Again` action).
  - `@media print` in `frontend/src/index.css` hides headers, sidebars, bottom bars, and action buttons; resets surfaces to `#ffffff` with `#000000` ink; and applies `break-inside: avoid` on `ResultReviewCard` and `StatCard` elements.

---

## 5. Explicit "Do Not Copy" Guardrail

- We synthesize structural, spatial, and interaction patterns only. Zero logos, illustrations, proprietary icon sets, palettes, or verbatim product copy from Canvas, Inspera, TAO, Moodle, College Board Bluebook, Khan Academy, Gradescope, Stripe, or Linear may be reproduced.
