# Technical Requirements Document (TRD)
## Faculty Feedback System — Blueprint for Correct Implementation

**Version:** 8.0  
**Audience:** Human developers and AI coding agents  
**Purpose:** This document is the single source of truth for architecture, constraints, decision rules, and non-negotiable behaviours. Any implementation or modification **must** follow these rules.

---

## 1. System Overview

| Item | Value |
|------|-------|
| Application type | Multi-role web application |
| Framework | Flask 3.x + Jinja2 |
| Primary language | Python 3.12 |
| Database (dev) | SQLite (`feedback.db`) |
| Database (prod) | PostgreSQL (Supabase recommended) |
| Deployment target | Vercel (serverless) or any WSGI host |
| Auth model | Session-based, role-scoped |
| Frontend | Server-rendered HTML + progressive JS (scanner, forms) |
| Reports | ReportLab PDF |
| Imports | openpyxl (Excel) |

Entry point: `app.py` → `feedback_system.create_app()`.

---

## 2. Architectural Principles (Non-Negotiable)

1. **Role isolation is absolute.** A teacher must never see another teacher’s unpublished or published data. A HOD must never see outside their `user_department_scopes`. A Dean’s visibility is derived only from assigned HODs.
2. **Anonymity after submission.** Once a student submits, the link between identity and answers is broken for teacher-facing views. Aggregate only.
3. **Eligibility before visibility.** A student sees a form only if they are enrolled in a timetable that contains at least one of the form’s sessions **and** the form is open.
4. **Publication gate.** Teachers see results **only** after an explicit admin (or authorised) publish action.
5. **Never drop historical data.** Migrations only ADD. Soft-delete columns exist; hard deletes of feedback are forbidden.
6. **Default passwords are temporary.** Shared defaults exist only for bootstrap/import. Personal passwords supersede them.
7. **Idempotent imports.** Timetable and second-faculty imports use fingerprints / staging so re-running does not create duplicates.
8. **Fail closed.** Missing scope, missing eligibility, or missing publish flag → empty result or access denied, never partial leakage.

---

## 3. Technology Stack & Constraints

### 3.1 Backend
- Flask application factory pattern (`create_app`).
- Blueprints: `auth`, `admin`, `student`, `teacher`, `hod`, `dean`.
- Database access via a thin abstraction that works for both SQLite and PostgreSQL (`db.py` + `pg.py` translation layer).
- Password hashing: `werkzeug.security.generate_password_hash` / `check_password_hash`.
- CSRF protection on all state-changing forms.
- Rate limiting on login endpoints (configurable max attempts + lockout seconds).

### 3.2 Frontend
- Server-side rendered Jinja2 templates.
- Minimal client JS for ID-card scanner, form UX, and progressive enhancement.
- No SPA framework required.
- Responsive layout targeting mobile-first student use and desktop admin use.

### 3.3 Data Layer Rules
- All schema changes go through versioned migrations in `schema.py`.
- SQLite and PostgreSQL must remain compatible (use the existing translation helpers).
- Foreign keys and CHECK constraints are enforced.
- Soft-delete pattern: `is_deleted` + `deleted_at` where history matters.

### 3.4 Configuration (Environment)
Required / important variables:
- `SECRET_KEY`
- `DATABASE_URL` (empty → SQLite)
- `ADMIN_EMAIL` / `ADMIN_PASSWORD` (bootstrap only)
- `DEFAULT_TEACHER_PASSWORD` / `DEFAULT_STUDENT_PASSWORD`
- `MAIL_USER` / `MAIL_APP_PASSWORD`
- `APP_ENV` (`development` | `production`)
- `SESSION_COOKIE_SECURE`
- `AUTO_IMPORT`
- `ACADEMIC_YEAR`

Never commit real secrets. Rotate any credential that has been exposed.

---

## 4. Role Decision Matrix (AI Must Follow)

| Action | Student | Teacher | Admin | HOD | Dean |
|--------|---------|---------|-------|-----|------|
| Submit feedback | Own eligible forms only | — | — | — | — |
| View own results | — | Published only, own sessions | All | Scoped branches | Via assigned HODs |
| Create form | — | — | Yes | Scoped branches | — |
| Publish results | — | — | Yes | Limited / none (design choice) | Monitor only |
| Manage users | — | — | Yes | — | — |
| Import timetable / second faculty | — | — | Yes | Review only | — |
| Change own password | Yes | Yes | Yes | Yes | Yes |
| Access other department data | Never | Never | Yes | Never | Only via HOD chain |

**Decision rule for any new feature:**  
If the feature can expose data across roles or departments, it must include an explicit scope check using `user_department_scopes` (or equivalent) and fail closed.

---

## 5. Authentication & Session Rules

### 5.1 Login Identifiers
| Role | Identifier field | Matching rule |
|------|------------------|---------------|
| Admin | email or username | case-insensitive |
| Teacher | emp_code / username | exact (as stored) |
| Student | roll / username | exact (usually uppercased) |
| HOD | emp_code or username | uppercased |
| Dean | emp_code or username | uppercased |

### 5.2 Password Rules
- Default teacher password comes from `DEFAULT_TEACHER_PASSWORD`.
- Default student password comes from `DEFAULT_STUDENT_PASSWORD`.
- When a teacher still uses the default, set `must_change_password = 1`.
- HOD/Dean passwords are set at account creation time by Admin; no shared default.
- Password reset uses one-time email codes stored as hashes only.

### 5.3 Session Behaviour
- After successful login, redirect to role home:
  - admin → admin dashboard
  - teacher → teacher dashboard
  - student → student dashboard
  - hod → hod dashboard (or onboarding if incomplete)
  - dean → dean dashboard (or onboarding if incomplete)
- Logout clears session and returns to student login by default.
- Scan-login for students is allowed only while the student is still on the default password (configurable).

### 5.4 Lockout
- Track failures by `(role, identifier, IP)`.
- After `LOGIN_MAX_ATTEMPTS`, lock for `LOGIN_LOCKOUT_SECONDS`.

---

## 6. Core Domain Rules

### 6.1 Eligibility Algorithm (Student sees form)
A student may see/submit a form if and only if:
1. Form status = `open`
2. Student has an active enrollment in a timetable
3. That timetable contains at least one `class_session` linked to the form (via `form_sessions` or legacy `session_id`)
4. Student has not already submitted for that form

### 6.2 Publication Gate
- Results queries for teachers must join through a publication record / flag.
- Unpublished forms return empty or “not yet published” — never raw answers.

### 6.3 Form Immutability
- If a form has any submission, question structure is frozen (HTTP 409 on edit attempts).
- To change questions, create a new form.

### 6.4 Second-Faculty Eligibility
- Only `confirmed` second-faculty assignments create additional feedback targets.
- `unresolved`, `rejected`, `conflict` never grant eligibility.

### 6.5 Scope Resolution (HOD / Dean)
- HOD: `user_department_scopes` → list of `branch_id`s.
- Dean: assigned HODs → each HOD’s scopes → union of branch_ids.
- Every list/query for these roles must filter by the resolved branch set.
- Empty scope → empty dashboard (never global data).

---

## 7. Data Import Rules

1. Timetable import is fingerprint-based; same file + semester + year is not re-imported as new.
2. Teacher and student users are created with `INSERT OR IGNORE` using default password hashes.
3. Second-faculty import uses staging tables and batch records; commit only after preview/confirm.
4. Missing official Excel files must not invent data — leave mappings unresolved.

---

## 8. API / Route Conventions

- All routes live under role blueprints.
- Login routes:
  - `/` — student
  - `/teacher/login`
  - `/admin/login`
  - `/hod/login`
  - `/dean/login`
- State-changing endpoints require CSRF token.
- JSON endpoints (e.g. scan-login) still validate CSRF where applicable.
- Error responses for auth/permission failures redirect with flash or return 403.

---

## 9. Database Migration Rules

- Migrations are ordered integers (v1 … v8+).
- New migrations only ADD tables/columns/indexes.
- Role CHECK expansion for `hod`/`dean` is performed carefully (SQLite rebuild or PG constraint replace) so existing users survive.
- Every migration must be reversible in spirit (no data loss) even if a formal down-migration is not implemented.

---

## 10. Security Checklist (Must Pass)

- [ ] Passwords never stored in plain text
- [ ] CSRF on every POST that changes state
- [ ] Role decorator (`role_required`) on every protected view
- [ ] Scope filters on every HOD/Dean query
- [ ] Rate limiting on login
- [ ] Secrets only in environment / secret store
- [ ] Session cookie `HttpOnly`; `Secure` in production
- [ ] Audit log for publish, password reset, account create, import commit

---

## 11. Testing Requirements

Any change that touches auth, eligibility, publication, or scope **must** be covered by tests that prove:
- Isolation (role A cannot see role B data)
- Eligibility boundaries
- Publication gate
- Soft-delete / history preservation
- Migration upgrade path from previous version

Existing suite target: 180+ tests passing.

---

## 12. Deployment Blueprint

1. Set environment variables (never commit `.env`).
2. Point `DATABASE_URL` to PostgreSQL for production.
3. Run migrations on first boot (automatic).
4. Bootstrap admin only if no admin exists.
5. Import official timetable once (`AUTO_IMPORT` or manual).
6. Create HOD/Dean accounts and assign scopes.
7. Set `SESSION_COOKIE_SECURE=1` behind HTTPS.
8. Prefer a production WSGI server or Vercel serverless adapter.

---

## 13. Decision Guide for AI Agents

When implementing or modifying code, answer these questions in order:

1. **Which roles can perform this action?** Enforce with `role_required`.
2. **Does this expose student identity to a teacher?** If yes → reject or aggregate only after publish.
3. **Does this cross department boundaries?** If yes → apply scope filter or deny.
4. **Can this create orphaned historical answers?** If yes → freeze structure or create new form.
5. **Is the default password still in use?** Prefer forcing change rather than silent continuation.
6. **Will this work on both SQLite and PostgreSQL?** Use the existing abstraction.
7. **Is there an audit event?** Add one for sensitive actions.

If any answer is unclear, prefer the stricter interpretation (fail closed).

---

## 14. Known Technical Debt (Do Not Ignore)

- `must_change_password` is set but not always enforced as a hard redirect.
- Legacy `feedback` table still exists for backward compatibility; new code must use form/answer tables.
- Second-faculty and workload Excel files were missing from the source package — import paths exist but data is empty until supplied.
- Development server is used by default; production must use proper WSGI / serverless.

---

**This TRD is the authoritative blueprint.**  
Any generated code, refactor, or new feature that violates the rules above is incorrect by definition.
