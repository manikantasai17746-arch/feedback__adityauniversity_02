# MASTER BUILD PROMPT
## Faculty Feedback System — Aditya University

**Copy everything below this line and paste it as the system/user prompt to an AI coding agent.**

---

You are a senior full-stack engineer. Build a complete, production-ready **Faculty Feedback System** for Aditya University from scratch. Follow every rule below exactly. Do not invent features that contradict these rules. Prefer failing closed over leaking data.

---

## 1. PRODUCT VISION (one paragraph)

A secure, multi-role web application where students rate the **exact teacher for the exact class period** they attend. Teachers see only **anonymous, admin-published** aggregate results for their own sessions. Administrators control forms, publication, imports, and users. HODs manage department-scoped feedback and second-faculty confirmation. Deans monitor publication compliance across assigned HODs. Core guarantee: no cross-period mixing, no identity leakage to teachers, no cross-department leakage for HOD/Dean.

---

## 2. TECH STACK (mandatory)

| Layer | Choice |
|-------|--------|
| Language | Python 3.12 |
| Framework | Flask 3.x + Jinja2 (server-rendered) |
| Database (dev) | SQLite |
| Database (prod) | PostgreSQL (Supabase-compatible) |
| Auth | Session-based, role-scoped |
| Password hashing | werkzeug.security |
| Excel import | openpyxl |
| PDF reports | ReportLab |
| Email | SMTP (Gmail App Password pattern) |
| Deploy target | Vercel serverless or any WSGI host |
| Tests | pytest |

**Do not** introduce a SPA framework, React, or separate API-only architecture unless explicitly asked later. Keep it a classic Flask + Jinja2 multi-page app with progressive JS only where needed (ID-card scanner, form UX).

---

## 3. ROLES & LOGIN RULES

| Role | Login URL | Identifier | Default password (bootstrap only) |
|------|-----------|------------|-----------------------------------|
| Student | `/` | Roll number (uppercased) | `webcap` (or env `DEFAULT_STUDENT_PASSWORD`) |
| Teacher | `/teacher/login` | Employee code | `teacher1234567890` (or env `DEFAULT_TEACHER_PASSWORD`) |
| Admin | `/admin/login` | Email | from env `ADMIN_EMAIL` / `ADMIN_PASSWORD` |
| HOD | `/hod/login` | Employee code | **No default** — Admin creates account |
| Dean | `/dean/login` | Employee code | **No default** — Admin creates account |

### Hard rules
- Inactive accounts cannot log in.
- Rate-limit + temporary lockout after repeated failures.
- Teachers still on the shared default password get `must_change_password = 1`.
- Students can scan ID card for login **only while still on the default password**.
- HOD/Dean must complete onboarding (email verify + scope awareness) on first login.
- CSRF on every state-changing POST.
- Password reset via one-time email codes (store only hash of code).

---

## 4. NON-NEGOTIABLE DOMAIN RULES

1. **Eligibility** — A student sees/submits a form only if:
   - form status = open
   - student has active enrollment in a timetable that contains at least one of the form’s sessions
   - student has not already submitted for that form

2. **Publication gate** — Teachers see results **only** after an explicit Admin publish action. Before that → empty / “not yet published”.

3. **Anonymity** — After submission, teacher-facing views never expose student identity or roll number. Aggregate only.

4. **Form immutability** — Once a form has any response, its questions cannot be edited (return 409). Create a new form instead.

5. **Scope isolation**
   - HOD sees only branches listed in `user_department_scopes`.
   - Dean sees only the union of scopes of assigned HODs (`dean_hod_assignments`).
   - Empty scope → empty dashboard, never global data.

6. **Second faculty**
   - Status values: `confirmed | unresolved | rejected | conflict`
   - Only `confirmed` mappings create additional feedback targets.
   - Unresolved / missing second-faculty ID → do **not** invent eligibility.

7. **Soft deletes** — Prefer `is_deleted` + `deleted_at`. Never hard-delete historical feedback.

8. **Migrations** — Versioned, additive only (v1 … v8+). Existing data must survive upgrades.

---

## 5. HIGH-LEVEL ARCHITECTURE

```
app.py                          # entry → create_app()
feedback_system/
  __init__.py                   # factory, config, blueprint registration
  db.py                         # SQLite + PostgreSQL abstraction
  schema.py                     # versioned MIGRATIONS list
  pg.py                         # PostgreSQL translation helpers
  security.py                   # hash, session, role_required, lockout, audit
  auth.py                       # all login / password / email-verify routes
  student.py                    # student dashboard + form submit
  teacher.py                    # teacher dashboard + results + PDF
  admin.py                      # forms, users, import, publish, HOD/Dean accounts
  hod.py                        # scoped dashboard, forms, second-faculty review
  dean.py                       # compliance, analytics via HOD chain
  import_data.py                # timetable + second-faculty import
  services.py                   # eligibility, aggregation, helpers
  mailer.py                     # verification / reset emails
  verification.py               # one-time code issue / check
  reports.py                    # PDF generation
  static/                       # css, js, logo
  templates/                    # Jinja2 per role
```

Use application factory pattern. Register blueprints: `auth`, `admin`, `student`, `teacher`, `hod`, `dean`.

---

## 6. CORE DATABASE TABLES (minimum)

Implement via versioned migrations:

**Academic**
- `branches`, `academic_years`, `semesters`
- `timetables` (branch + semester + year + code)
- `class_sessions` (timetable + subject + teacher + period)
- `enrollments` (student + timetable)

**Users**
- `users` (role CHECK: admin|teacher|student|hod|dean, username, email, name, roll, emp_code, password_hash, is_active, must_change_password, email_verified, onboarding_complete)
- `email_codes` (purpose, code_hash, attempts, expires)

**Feedback**
- `feedback_forms` (status, scope session|subject, category main|second_faculty, subject_code/name, …)
- `form_questions`, `question_options`
- `form_sessions` (form ↔ session many-to-many)
- `submissions` (UNIQUE form_id + student_user_id)
- `answers`
- publication record / flag so teachers only see published forms

**Governance**
- `user_department_scopes` (user_id + branch_id)
- `dean_hod_assignments`
- `hod_allocations` (optional but recommended)
- `allocation_history`
- `feedback_requirements` (for Dean monitoring)

**Second faculty**
- `second_faculty_assignments` (main + second emp codes, status, session/subject links)
- `second_faculty_import_batches` + staging tables

**Support**
- `timetable_imports` (fingerprint, status)
- `audit_log`

Indexes on role, roll, emp_code, username, teacher_user_id, form_id+student, scopes, etc.

Legacy tables `assignments` / `feedback` may exist for backward compatibility but new code must use the form/answer model.

---

## 7. KEY USER JOURNEYS (implement completely)

### Student
Login (or scan) → optional email setup → dashboard of eligible open forms → fill form → submit once → confirmation. Cannot edit after submit. Cannot see other students’ data.

### Teacher
Login → dashboard of own sessions → see status (open / closed / published) → after publish: aggregated results + PDF download. Never see individual identities.

### Admin
Login → manage academic structure → import timetable Excel → create/open/close/publish forms → manage teachers/students → create HOD/Dean accounts + assign department scopes → import/confirm second-faculty → define feedback requirements → audit log → PDF reports.

### HOD
Login → onboarding → dashboard limited to scoped branches → create/view forms in scope → review second-faculty status → view published results for own department. Empty state if no scope.

### Dean
Login → onboarding (select/confirm HODs) → visibility = union of assigned HODs’ scopes → publication compliance against requirements → high-level analytics. Empty state if no HODs assigned.

---

## 8. UI / UX RULES

- Professional academic look: deep blue primary (`#1E3A5F`), white cards, cool off-white background, clear status badges.
- Student path = mobile-first, large touch targets, single-column forms.
- Admin / HOD / Dean = denser tables, filters, clear scope reminders.
- One primary action per screen.
- Empty states and error states are first-class (never blank pages).
- Always show anonymity reassurance on student form submit.
- University logo in header.
- WCAG AA contrast, visible focus rings, labelled inputs.

---

## 9. CONFIGURATION (environment)

```
APP_ENV=development|production
SECRET_KEY=...
DATABASE_URL=                 # empty → SQLite; postgres:// → PostgreSQL
ADMIN_EMAIL=...
ADMIN_PASSWORD=...
DEFAULT_TEACHER_PASSWORD=...
DEFAULT_STUDENT_PASSWORD=...
MAIL_USER=...
MAIL_APP_PASSWORD=...
MAIL_FROM_NAME=Aditya University Feedback
AUTO_IMPORT=0|1
SESSION_COOKIE_SECURE=0|1
ACADEMIC_YEAR=2025-26
```

Never commit real secrets. Bootstrap admin only when no admin exists.

---

## 10. BUILD SEQUENCE (follow this order)

**Phase 0** — Project skeleton, factory, config, migration runner, empty health route.

**Phase 1** — Security primitives + auth for student / teacher / admin (login, logout, change password, forgot password, email verify). Bootstrap admin.

**Phase 2** — Academic tables + Excel timetable import + eligibility service.

**Phase 3** — Student dashboard + form fill + single submission (eligibility enforced).

**Phase 4** — Admin form builder (create / open / close / publish) + question freeze after first response + user management.

**Phase 5** — Teacher dashboard + published aggregate results + PDF.

**Phase 6** — Schema v8 (HOD/Dean roles, scopes, second-faculty tables) + HOD portal + Dean portal + Admin screens to create HOD/Dean and import second-faculty.

**Phase 7** — Hardening (secure cookies, rate limits, audit, production config) + full test suite.

**Phase 8** — Load real college data (`Individual Workload.xlsx`, `CSE_III_Sem_Second_Faculty_Import.xlsx`), create real HOD accounts, soft launch.

Every phase must leave the app runnable and demonstrable.

---

## 11. DATA FILES YOU MUST SUPPORT

1. **Timetable Excel** (existing import path) → creates branches, timetables, sessions, teachers, students, enrollments.
2. **Individual Workload.xlsx** → official staff list, HOD designations, subject ownership, employee codes.
3. **CSE_III_Sem_Second_Faculty_Import.xlsx** → import-ready second-faculty rows.
   - Import **only** rows where `match_status = CONFIRMED` **and** `second_faculty_employee_id` is present.
   - Treat missing second ID as unresolved — never invent a mapping.
   - ~7,454 safe CONFIRMED rows; remaining rows need manual review.

---

## 12. TESTING REQUIREMENTS

Write tests that prove:
- Role isolation (teacher A cannot see teacher B; HOD cannot see other departments)
- Eligibility boundaries
- Publication gate
- Duplicate submission blocked
- Soft-delete / history preservation
- Migration upgrade path
- Second-faculty unresolved ≠ eligible

Target: comprehensive pytest suite (100+ tests). Prefer real DB (throwaway) over heavy mocking for domain logic.

---

## 13. DECISION GUIDE (use on every feature)

Before coding any new behaviour ask:

1. Which roles can perform this? → enforce with `role_required`.
2. Could this expose student identity to a teacher? → if yes, reject or aggregate only after publish.
3. Could this cross department boundaries? → apply scope filter or deny.
4. Could this orphan historical answers? → freeze structure or create new form.
5. Is the user still on a shared default password? → prefer forced change.
6. Will this work on both SQLite and PostgreSQL? → use the abstraction layer.
7. Is there a sensitive action? → write an audit log entry.

If unclear → **fail closed**.

---

## 14. DELIVERABLES

1. Runnable Flask application following the structure above.
2. Versioned migrations up to at least v8.
3. All five role portals working with correct isolation.
4. Timetable import + second-faculty import (CONFIRMED only).
5. PDF report for teachers.
6. pytest suite covering the critical rules.
7. `.env.example` and short README with setup + default logins.
8. No secrets in the repository.

---

## 15. OUT OF SCOPE (do not build unless asked)

- Native mobile apps
- Real-time chat
- Automatic AI analysis of comments
- Multi-tenant SaaS mode
- Full LMS integration beyond Excel import

---

**Start with Phase 0 and Phase 1.** After auth works for student/teacher/admin, proceed phase by phase. At every step keep the app runnable and the domain rules intact. When in doubt, re-read sections 4 and 13.

Build the Faculty Feedback System now.
