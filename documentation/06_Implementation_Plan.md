# Implementation Plan
## Faculty Feedback System — Step-by-Step Build Sequence

**Version:** 8.0  
**Goal:** Produce a working, secure, role-complete system that matches the PRD, TRD, App Flow, UI/UX Brief, and Schema.

**Principle:** Build in vertical slices that are always demonstrable. Never leave auth or eligibility half-done.

---

## Phase 0 — Project Foundation (Day 0–1)

### Step 0.1 — Repository & Environment
1. Create project structure:
   ```
   app.py
   feedback_system/
     __init__.py
     auth.py
     admin.py
     student.py
     teacher.py
     hod.py
     dean.py
     db.py
     schema.py
     security.py
     import_data.py
     services.py
     mailer.py
     verification.py
     reports.py
     pg.py
     static/
     templates/
   requirements.txt
   .env.example
   tests/
   ```
2. Pin dependencies: Flask, werkzeug, openpyxl, reportlab, python-dotenv, psycopg (or equivalent), pytest.
3. Create `.env.example` with all variables listed in the TRD; keep real `.env` out of git.
4. Implement application factory `create_app()` that loads config from environment.

### Step 0.2 — Database Abstraction
5. Implement `db.py` with connection handling for SQLite (default) and PostgreSQL (when `DATABASE_URL` set).
6. Implement versioned migration runner that applies `MIGRATIONS` from `schema.py` in order.
7. Write migration v1–v3 (users, branches, timetables, sessions, enrollments, basic forms).
8. Smoke-test: empty DB → run app → tables exist.

**Exit criteria:** App starts, migrations run, health/ping route responds.

---

## Phase 1 — Authentication & Users (Day 1–3)

### Step 1.1 — Security Primitives
1. Password hashing helpers.
2. Session login / logout / `current_user`.
3. `role_required` decorator.
4. Login failure tracking + lockout.
5. CSRF protection on forms.
6. Audit log helper.

### Step 1.2 — Auth Routes
7. Student login `/`
8. Teacher login `/teacher/login`
9. Admin login `/admin/login`
10. Logout, change-password, forgot-password + reset (email code flow).
11. Email setup + verification for student/teacher.

### Step 1.3 — Bootstrap Admin
12. On first run, if no admin and `ADMIN_EMAIL`/`ADMIN_PASSWORD` present → create admin.
13. Default password constants for teacher/student used only at import time.

### Step 1.4 — Tests
14. Login success/failure for each role.
15. Lockout behaviour.
16. Inactive user blocked.
17. CSRF present on POSTs.

**Exit criteria:** All three core roles can log in and out securely; admin exists after bootstrap.

---

## Phase 2 — Academic Data & Import (Day 3–5)

### Step 2.1 — Schema Completion (v3–v5)
1. Full timetable, session, enrollment, form, question, submission, answer tables.
2. `form_sessions` and subject-scope support.
3. Soft-delete columns.

### Step 2.2 — Excel Import
4. Parse official timetable workbook.
5. Create branches, years, semesters, timetables, sessions, teachers, students, enrollments.
6. Use `INSERT OR IGNORE` + fingerprint table (v7) to make import idempotent.
7. Apply `DEFAULT_TEACHER_PASSWORD` / `DEFAULT_STUDENT_PASSWORD` hashes.

### Step 2.3 — Eligibility Service
8. Function: given student + form → boolean eligible (enrollment ∩ form sessions ∩ open status ∩ no prior submission).

**Exit criteria:** Importing the sample timetable produces correct users and sessions; eligibility returns true only for the right students.

---

## Phase 3 — Student Feedback Path (Day 5–7)

### Step 3.1 — Student Dashboard & Form
1. List only eligible open forms.
2. Render questions (rating, MCQ, text).
3. Submit → create submission + answers; enforce uniqueness.
4. Block closed / duplicate / ineligible attempts with clear messages.

### Step 3.2 — Scan Login (optional but present)
5. JSON endpoint that logs student in when still on default password.

### Step 3.3 — UI
6. Mobile-first student templates matching UI/UX brief.
7. Success and empty states.

### Step 3.4 — Tests
8. Eligible student can submit once.
9. Ineligible student never sees form.
10. Second submission rejected.

**Exit criteria:** End-to-end student can log in, see correct form, submit once, and see confirmation.

---

## Phase 4 — Form Lifecycle & Admin (Day 7–10)

### Step 4.1 — Admin Form Builder
1. Create form (session or subject scope).
2. Add / order questions.
3. Open / close form.
4. Freeze questions after first response (409).
5. Bulk create helper.

### Step 4.2 — Publication
6. Explicit publish action → write publication record / flag.
7. Audit log entry.

### Step 4.3 — Admin User Management
8. List / activate / deactivate teachers & students.
9. Password reset (sets must_change_password).

### Step 4.4 — Tests
10. Publish gate: teacher sees nothing before publish.
11. Question edit blocked after response.

**Exit criteria:** Admin can create, open, close, publish a form; student submissions appear only after publish for the teacher.

---

## Phase 5 — Teacher Portal (Day 10–11)

### Step 5.1 — Dashboard & Results
1. List own sessions/forms with status.
2. Aggregated results view (no student identity).
3. PDF report generation (ReportLab).

### Step 5.2 — Tests
4. Teacher A cannot see Teacher B data.
5. Unpublished forms show empty / “not available”.

**Exit criteria:** Teacher sees only own published anonymous aggregates and can download PDF.

---

## Phase 6 — HOD & Dean (Day 11–14)

### Step 6.1 — Schema v8
1. Expand role CHECK to include hod, dean.
2. `user_department_scopes`, `second_faculty_assignments`, import batches/staging.
3. `feedback_requirements`, `hod_allocations`, `dean_hod_assignments`, `allocation_history`.

### Step 6.2 — HOD Portal
4. Login + onboarding (email + scope awareness).
5. Dashboard filtered by scopes.
6. Scoped form list / create.
7. Second-faculty status view.
8. Empty state when no scope.

### Step 6.3 — Dean Portal
9. Login + onboarding (email + HOD selection).
10. Visibility derived from assigned HODs.
11. Publication compliance against requirements.
12. High-level analytics / history views.

### Step 6.4 — Admin Support Screens
13. `/admin/accounts/hod-dean` + CSV template.
14. `/admin/second-faculty` + import workflow.
15. `/admin/requirements`.

### Step 6.5 — Tests
16. HOD isolation between departments.
17. Dean sees only through HOD chain.
18. Unresolved second-faculty does not grant eligibility.

**Exit criteria:** HOD and Dean portals function with correct isolation; Admin can provision accounts and scopes.

---

## Phase 7 — Hardening & Production (Day 14–16)

### Step 7.1 — Security & Config
1. Force `SESSION_COOKIE_SECURE` in production.
2. Review rate limits and lockout values.
3. Ensure no secrets in repository.
4. Rotate any credentials that appeared in shared zips.

### Step 7.2 — Mail
5. Verification and reset emails working with configured App Password.

### Step 7.3 — Deployment
6. Supabase / PostgreSQL connection (pooler for serverless).
7. Vercel (or chosen host) environment variables.
8. Run migrations on deploy.
9. One-time admin bootstrap and timetable import in production.

### Step 7.4 — Full Test Suite
10. Run entire pytest suite (target 180+ passing).
11. Manual checklist from PRD release criteria.

**Exit criteria:** Production URL serves all roles; tests green; secrets rotated.

---

## Phase 8 — Data Completion & Soft Launch (Day 16+)

1. Obtain and import official second-faculty / workload Excel files.
2. Create real HOD and Dean accounts with correct department scopes.
3. Define feedback requirements for the current semester.
4. Soft-launch with one department → monitor participation and errors.
5. Collect feedback on UI friction; adjust microcopy and empty states.
6. Full institutional rollout.

---

## Build Sequence Checklist (Quick Reference)

| # | Deliverable | Depends on |
|---|-------------|------------|
| 1 | App factory + config + migrations runner | — |
| 2 | Users + auth for student/teacher/admin | 1 |
| 3 | Academic tables + Excel import | 2 |
| 4 | Eligibility engine | 3 |
| 5 | Student submit path | 4 |
| 6 | Admin form builder + publish | 5 |
| 7 | Teacher results + PDF | 6 |
| 8 | Schema v8 + HOD/Dean portals | 7 |
| 9 | Second-faculty import + requirements | 8 |
| 10 | Production deploy + hardening | 9 |
| 11 | Real data + soft launch | 10 |

---

## Definition of Done (Every Phase)

- Code follows TRD decision rules (role isolation, publication gate, fail closed).
- New routes appear in App Flow document.
- Schema changes are migrated and documented.
- Tests cover the new behaviour.
- UI matches the Design Brief for the affected role.
- No secrets committed.
- Manual smoke test of the happy path for the roles touched.

---

## Risk Buffer

- Missing Excel files → keep second-faculty in “unresolved” state; do not invent data.
- Partial `must_change_password` enforcement → implement hard redirect as a fast follow-up.
- Serverless cold starts → keep import optional (`AUTO_IMPORT=0` after first load).

---

**Follow this sequence in order.**  
Skipping eligibility or publication gates will produce incorrect product behaviour even if the UI looks complete.
