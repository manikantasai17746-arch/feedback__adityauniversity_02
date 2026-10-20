# Product Requirements Document (PRD)
## Faculty Feedback System — Aditya University

**Version:** 8.0  
**Last Updated:** 19 October 2026  
**Product Owner:** Aditya University Feedback Team  
**Status:** Production-ready (with known data gaps)

---

## 1. Executive Summary

The Faculty Feedback System is a secure, role-based web application that enables students to provide structured, anonymous feedback on the specific teachers they encounter for each subject and class period. Results are visible to teachers only after administrators publish them. The system supports five distinct roles (Student, Teacher, Admin, HOD, Dean), academic hierarchy (branches → timetables → class sessions), second-faculty mapping, and department-scoped governance.

Core value proposition:
- Students rate the **exact teacher for the exact period** they attend.
- Teachers see only **anonymous, published** results for their own sessions.
- Administrators control form lifecycle, publication, and institutional data.
- HODs manage department-level feedback and second-faculty confirmation.
- Deans monitor publication compliance and multi-department analytics.

---

## 2. Problem Statement

Traditional feedback systems suffer from:
- Generic “course” ratings that do not distinguish which teacher taught which period.
- Lack of anonymity guarantees after results are released.
- No departmental ownership or second-faculty (shared teaching) handling.
- Manual collection that is slow, incomplete, and hard to audit.
- No clear separation between draft, open, closed, and published states.

This product solves these by binding feedback to **class sessions**, enforcing **eligibility**, preserving **anonymity until publication**, and providing **role-scoped portals**.

---

## 3. Goals & Success Metrics

### Primary Goals
1. Capture authentic, period-specific feedback from every enrolled student.
2. Guarantee that a student’s answers cannot be traced back after submission.
3. Allow administrators to open, close, and publish forms with full auditability.
4. Give teachers actionable, aggregated insights only after official publication.
5. Enable HODs and Deans to oversee compliance within their authorised scope.

### Success Metrics
| Metric | Target |
|--------|--------|
| Student participation rate per open form | ≥ 70 % of eligible students |
| Time from form close to teacher-visible results | ≤ 24 hours after admin publish |
| Cross-period data leakage incidents | 0 |
| Unauthorized access to unpublished results | 0 |
| Successful role-based login success rate | ≥ 99 % |

---

## 4. User Personas & Roles

### 4.1 Student
- **Identifier:** Roll number (e.g. `25B11CS015`)
- **Needs:** Quick login (including ID-card scan), clear list of pending forms, simple rating + comment UI, confirmation that feedback is anonymous.
- **Pain points:** Forgetting passwords, not knowing which forms are still open, fear of retaliation.

### 4.2 Teacher
- **Identifier:** Employee code (e.g. `6817`)
- **Needs:** View only published results for own sessions, download PDF reports, understand scores per question/period.
- **Pain points:** Seeing unfinished or unpublished data, mixing of different periods.

### 4.3 Administrator
- **Identifier:** Email address
- **Needs:** Full control over academic structure, form builder, bulk operations, user management, publication, second-faculty import, HOD/Dean account creation, audit logs.
- **Pain points:** Data import errors, accidental early publication, missing department scopes.

### 4.4 Head of Department (HOD)
- **Identifier:** Employee code
- **Needs:** Department-scoped dashboard, create/view forms for own branches, confirm second-faculty mappings, see results for own department.
- **Constraints:** Cannot see other departments; cannot act as global admin.

### 4.5 Dean
- **Identifier:** Employee code
- **Needs:** Monitor publication status against defined requirements, multi-HOD analytics, historical score trends, high-level compliance view.
- **Constraints:** Visibility derived from assigned HODs and their department scopes.

---

## 5. Functional Requirements

### 5.1 Authentication & Account Lifecycle
- FR-A1: Students log in with roll number + password (or ID-card scan when still on default password).
- FR-A2: Teachers log in with employee code + password.
- FR-A3: Admin logs in with email + password.
- FR-A4: HOD and Dean log in with employee code + password.
- FR-A5: All roles support forgot-password via email verification code.
- FR-A6: Students and teachers can set/verify a personal email on first use.
- FR-A7: Teachers on the shared default password are flagged `must_change_password`.
- FR-A8: Login rate limiting and temporary lockout after repeated failures.
- FR-A9: Session-based authentication with role-aware redirects.
- FR-A10: Inactive accounts cannot log in.

### 5.2 Academic Structure
- FR-B1: System maintains Branches, Academic Years, Semesters, Timetables, Class Sessions, Enrollments.
- FR-B2: Class sessions are unique per (timetable, subject, teacher).
- FR-B3: Students are enrolled in specific timetables; eligibility is derived from enrollments + sessions.
- FR-B4: Soft-delete support for timetables, sessions, and enrollments (history preserved).

### 5.3 Feedback Forms
- FR-C1: Admin (and HOD within scope) can create forms linked to one or more class sessions or to a whole subject.
- FR-C2: Forms support multiple question types (rating scales, multiple-choice, free text).
- FR-C3: Form lifecycle states: draft → open → closed → published (and optionally archived).
- FR-C4: Once a form has any responses, its questions cannot be edited (prevents orphaned answers).
- FR-C5: Forms can be scoped to a single session or to a subject across timetables.
- FR-C6: Forms can be categorised as `main` or `second_faculty`.
- FR-C7: Bulk form creation for multiple sessions/subjects.

### 5.4 Student Feedback Submission
- FR-D1: Student sees only forms for which they are eligible and that are currently open.
- FR-D2: Duplicate submission for the same form is blocked.
- FR-D3: Answers are stored against the submission; identity is separated from answers for anonymity after publication.
- FR-D4: Student receives clear confirmation after successful submission.
- FR-D5: Closed or ineligible forms are not shown or are clearly marked.

### 5.5 Results & Publication
- FR-E1: Results remain invisible to teachers until an administrator explicitly publishes them.
- FR-E2: Published results are aggregated and anonymous.
- FR-E3: Teachers can view results only for their own sessions.
- FR-E4: PDF report generation with filters (period, subject, date range).
- FR-E5: Admin can unpublish or re-publish under controlled conditions (audit logged).

### 5.6 Second-Faculty Support
- FR-F1: System stores main-teacher and optional second-teacher mappings per session/subject.
- FR-F2: Status values: confirmed, unresolved, rejected, conflict.
- FR-F3: Import workflow with staging and batch history.
- FR-F4: Unresolved mappings do not create false eligibility.
- FR-F5: Admin and HOD can review and resolve mappings.

### 5.7 HOD Portal
- FR-G1: Dashboard shows live counts for authorised branches only (students, faculty, forms, second-faculty status).
- FR-G2: Create and manage forms limited to scoped departments.
- FR-G3: View results for own department after publication.
- FR-G4: Onboarding wizard (email verification + scope confirmation) on first login.
- FR-G5: Empty-state messaging when no department scope is assigned.

### 5.8 Dean Portal
- FR-H1: Visibility derived from assigned HODs and their department scopes.
- FR-H2: Publication compliance monitoring against Admin-defined feedback requirements.
- FR-H3: Analytics and historical score views.
- FR-H4: Onboarding wizard (email + HOD selection).

### 5.9 Administration
- FR-I1: User management (teachers, students, HOD, Dean) with activate/deactivate and password reset.
- FR-I2: Excel/CSV import of timetable and second-faculty data with fingerprint-based deduplication.
- FR-I3: Audit log of sensitive actions.
- FR-I4: Feedback requirements configuration for Dean monitoring.
- FR-I5: Academic year and semester management.

### 5.10 Reporting & Export
- FR-J1: PDF reports for teachers and administrators.
- FR-J2: Search and filter on forms, submissions, and users.
- FR-J3: Export capabilities for audit and external analysis.

---

## 6. Non-Functional Requirements

| Category | Requirement |
|----------|-------------|
| Security | Password hashing (werkzeug), CSRF protection, session cookies, rate limiting, role isolation |
| Anonymity | Student identity separated from answers after submission; teachers never see individual responses |
| Performance | Support concurrent student submissions during open windows; cold-start friendly on serverless |
| Scalability | SQLite for local/dev; PostgreSQL (Supabase) for production |
| Availability | Deployable on Vercel as serverless function |
| Auditability | All critical actions written to audit_log |
| Data integrity | Soft deletes; versioned migrations; no dropping of historical feedback |
| Accessibility | Clear labels, keyboard-friendly forms, readable contrast |
| Browser support | Modern evergreen browsers (Chrome, Edge, Firefox, Safari) |

---

## 7. Out of Scope (Current Version)

- Real-time chat or messaging between roles.
- Mobile native apps (responsive web only).
- Automatic AI analysis of free-text comments.
- Integration with external LMS (Moodle, Canvas, etc.) beyond Excel import.
- Multi-university / multi-tenant SaaS mode.
- Forced password change redirect on every login (flag exists but enforcement is partial).

---

## 8. Assumptions & Dependencies

- Official timetable Excel is provided in the expected format.
- Second-faculty and Individual Workload Excel files will be supplied for full second-faculty coverage.
- College provides official HOD and Dean employee lists and department mappings.
- Email delivery relies on a configured Gmail App Password (or equivalent SMTP).
- Students know their roll numbers; teachers know their employee codes.

---

## 9. Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Shared default passwords | High | Force change on first login; rotate after import |
| Missing second-faculty data | Medium | System correctly treats unresolved as non-eligible |
| Accidental early publication | High | Explicit publish action + audit log |
| Scope leakage between departments | Critical | Strict `user_department_scopes` checks on every HOD/Dean query |
| Secrets in repository | Critical | `.env` git-ignored; rotate any exposed credentials |

---

## 10. Release Criteria

- All 181+ automated tests pass.
- Admin can import timetable and create a form for a real session.
- Student can submit feedback only for eligible open forms.
- Teacher sees zero results until publish.
- HOD with no scope sees empty state; HOD with scope sees only own data.
- No cross-period or cross-teacher data mixing.

---

## 11. Glossary

| Term | Definition |
|------|------------|
| Class Session | A unique combination of timetable + subject + teacher (+ period) |
| Eligibility | Student is enrolled in the timetable that contains the session of the form |
| Publication | Admin action that makes aggregated results visible to the teacher |
| Second Faculty | Additional teacher sharing responsibility for a session/subject |
| Scope | Set of branch_ids a HOD or Dean is authorised to see |

---

**Document Owner:** Product Team  
**Next Review:** After next major data import or role expansion
