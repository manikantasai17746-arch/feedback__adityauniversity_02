# App Flow Document
## Faculty Feedback System — Complete Head-to-Tail Journeys

**Version:** 8.0  
**Rule:** Every possible path from entry to exit for every role is documented. No screen or decision is omitted.

---

## 0. Global Entry Points

| URL | Purpose |
|-----|---------|
| `/` | Student login (default landing) |
| `/teacher/login` | Teacher login |
| `/admin/login` | Admin login |
| `/hod/login` | HOD login |
| `/dean/login` | Dean login |
| `/forgot-password` | Password recovery (all roles that have email) |
| `/logout` | Clears session → redirects to student login |
| `/change-password` | Authenticated password change |
| `/setup/email` | First-time email capture (student/teacher) |
| `/setup/email/verify` | Email verification code entry |

Unauthenticated access to any protected page → redirect to the appropriate login with `next` preserved where safe.

---

## 1. STUDENT COMPLETE FLOW

### 1.1 Arrival & Login
1. User opens `/`.
2. System shows student login form (Roll Number + Password).
3. Optional: ID-card scanner active (if enabled).
4. **Path A — Manual login**
   - Enter roll (normalised to upper case).
   - Enter password.
   - Submit.
   - System looks up `users` where `role='student'` and `username=roll` and `is_active=1`.
   - Verify password hash.
   - On success → create session → redirect to student dashboard (or email setup if required).
   - On failure → increment failure counter; possible lockout message.
5. **Path B — Scan login** (`POST /scan-login`)
   - Scanner sends code.
   - If student still on default password → direct login.
   - If student has personal password → return roll number only (fallback to manual password entry).
   - Unknown card → error + fallback.

### 1.2 First-Time / Incomplete Setup
6. If student has no verified email → forced or prompted to `/setup/email`.
7. Enter email → system sends 6-digit code → `/setup/email/verify`.
8. Correct code → email stored & verified → continue.
9. (Optional future) Force password change if still on default.

### 1.3 Student Dashboard
10. Dashboard lists:
    - Open forms the student is eligible for (not yet submitted).
    - Already submitted forms (read-only status).
    - Closed / ineligible forms (hidden or clearly marked unavailable).
11. Each open form shows subject, teacher (if visible), period, deadline if any.
12. Student selects a form → form filling page.

### 1.4 Filling & Submitting Feedback
13. Form page renders questions in order (rating, MCQ, text).
14. Client-side basic validation (required fields).
15. Submit → server re-checks:
    - Form still open
    - Student still eligible
    - No prior submission for this form
16. On success:
    - Create `submission` record linked to student + form.
    - Store answers (identity separated for later anonymity).
    - Flash success → return to dashboard.
17. On failure (closed / duplicate / ineligible) → clear error message, no partial save.

### 1.5 Post-Submission
18. Submitted form disappears from “pending” or shows “Submitted” badge.
19. Student cannot edit answers.
20. Student can log out or continue with other open forms.
21. Password change available at any time via `/change-password`.

### 1.6 Forgot Password (Student)
22. `/forgot-password` → enter roll or email.
23. If account exists and has email → send code.
24. Enter code + new password → password updated → login.

### 1.7 Exit
25. Logout → session cleared → back to `/`.

---

## 2. TEACHER COMPLETE FLOW

### 2.1 Login
1. Open `/teacher/login`.
2. Enter Employee Code + Password.
3. System resolves user with `role='teacher'`.
4. If password matches default → set `must_change_password=1`.
5. Success → teacher dashboard.
6. Failure → lockout logic same as student.

### 2.2 First-Time Setup
7. Email setup + verification (same pattern as student) if not done.
8. Prefer password change if still on default.

### 2.3 Teacher Dashboard
9. Shows list of class sessions / subjects the teacher owns.
10. For each, status of associated forms:
    - No form yet
    - Form open (students can submit)
    - Form closed (awaiting publish)
    - Results published (clickable)
11. Teacher **cannot** see individual student answers at any time.
12. Teacher **cannot** see results until Admin (or authorised party) publishes.

### 2.4 Viewing Published Results
13. Click published form/session.
14. Aggregated scores per question, distribution, optional comments (anonymous).
15. Filters: period, date range if available.
16. Download PDF report.
17. Empty state if no responses or not yet published.

### 2.5 Password & Account
18. Change password at `/change-password`.
19. Logout.

### 2.6 Edge Cases
- Teacher with no sessions → empty dashboard with explanatory message.
- Form exists but unpublished → “Results not yet available”.
- Second-faculty confirmed session → teacher may see additional form category if configured.

---

## 3. ADMIN COMPLETE FLOW

### 3.1 Login
1. `/admin/login` → Email + Password.
2. Match against admin role (email or username, case-insensitive).
3. Success → Admin dashboard.

### 3.2 Bootstrap (First Run Only)
4. If no admin exists and `ADMIN_EMAIL` / `ADMIN_PASSWORD` set → create admin.
5. Optional auto-import of timetable Excel when `AUTO_IMPORT=1` and DB empty.

### 3.3 Academic Structure Management
6. Manage Branches, Academic Years, Semesters.
7. View Timetables and Class Sessions created by import or manually.
8. Soft-delete / restore where supported.

### 3.4 User Management
9. List Teachers / Students.
10. Activate / deactivate accounts.
11. Reset password (sets temporary password + `must_change_password` flag).
12. Create HOD and Dean accounts (`/admin/accounts/hod-dean`):
    - Upload CSV or manual entry (employee code, name, email, departments).
    - Assign department scopes (`user_department_scopes`).
13. Assign Dean ↔ HOD relationships.

### 3.5 Form Lifecycle
14. Create form:
    - Choose scope (single session or subject-wide).
    - Select sessions / subject.
    - Add questions (rating scale, options, text).
    - Set category (`main` / `second_faculty`).
    - Save as draft or open immediately.
15. Bulk form creation for multiple sessions.
16. Open form → students become eligible to see it.
17. Close form → no new submissions.
18. Publish form → teachers can see aggregated results.
19. Cannot edit questions after first response (409). Create new form instead.
20. Track submission counts per form.

### 3.6 Second-Faculty Management
21. `/admin/second-faculty` — view mapping status (confirmed / unresolved / conflict).
22. Import second-faculty Excel → staging → preview → commit batch.
23. Resolve conflicts manually.
24. Unresolved mappings never grant student eligibility.

### 3.7 Feedback Requirements (for Dean monitoring)
25. Define required feedback items (department, year, semester, deadline).
26. Dean portal uses these to show compliance.

### 3.8 Reports & Audit
27. Generate institutional PDF reports.
28. Search submissions, users, forms.
29. View audit log (publish actions, imports, password resets, account creates).

### 3.9 Exit
30. Logout.

---

## 4. HOD COMPLETE FLOW

### 4.1 Login
1. `/hod/login` → Employee Code + Password.
2. Success → if onboarding incomplete → onboarding wizard; else dashboard.

### 4.2 Onboarding (First Login)
3. Verify / set email (code flow).
4. Confirm or view assigned department scopes.
5. Mark onboarding complete.
6. Proceed to dashboard.

### 4.3 HOD Dashboard
7. Live counts **only for authorised branches**:
   - Students
   - Faculty
   - Open / closed / published forms
   - Second-faculty confirmed vs unresolved
8. If no scopes assigned → empty state with clear message (“Contact Admin”).

### 4.4 Forms (Scoped)
9. List forms belonging to scoped departments.
10. Create new form limited to own branches/sessions.
11. View results for own department after publication.

### 4.5 Second-Faculty Review
12. See mapping status for own department.
13. Confirm or flag issues (depending on permissions granted).

### 4.6 Exit
14. Logout → student login page (or dedicated landing).

---

## 5. DEAN COMPLETE FLOW

### 5.1 Login
1. `/dean/login` → Employee Code + Password.
2. Onboarding if incomplete (email + select/confirm HODs).

### 5.2 Dean Dashboard
3. Visibility = union of all assigned HODs’ department scopes.
4. High-level KPIs: publication compliance, pending requirements, score trends.
5. Empty state if no HODs assigned.

### 5.3 Publication Monitoring
6. List feedback requirements defined by Admin.
7. Show which departments/forms have met the requirement (published on time).
8. Drill into specific HOD / department.

### 5.4 Analytics & History
9. Aggregated scores over time.
10. Comparison across periods/semesters (within authorised scope).
11. Export or PDF where implemented.

### 5.5 Exit
12. Logout.

---

## 6. CROSS-CUTTING FLOWS

### 6.1 Password Change (Any Authenticated User)
1. Navigate to `/change-password`.
2. Enter current password + new password (with confirmation).
3. Validate strength / match.
4. Update hash; clear `must_change_password` if set.
5. Flash success.

### 6.2 Session Timeout / Concurrent Login
- Server-side session expiry follows Flask config.
- No explicit multi-device kill switch in current version; new login creates new session.

### 6.3 Error & Lockout Paths
- Invalid credentials → generic “Invalid credentials” (no user enumeration).
- Too many failures → “Try again in X seconds”.
- Inactive account → treated as invalid credentials.
- CSRF failure → 400 / form re-display.
- 403 on role mismatch → redirect or forbidden page.

### 6.4 Soft-Delete Impact
- Soft-deleted timetable/session/enrollment → student loses eligibility for related forms.
- Historical submissions remain for audit and published reports.

---

## 7. END-TO-END HAPPY PATH (Reference Scenario)

1. Admin imports III-semester timetable Excel.
2. System creates branches, timetables, sessions, teachers, students, enrollments.
3. Admin creates a feedback form for period-3 ADSA taught by teacher 6817.
4. Admin opens the form.
5. Student `25B11CS015` (enrolled in that timetable) logs in, sees the form, submits ratings.
6. Another student not in that timetable never sees the form.
7. Admin closes the form.
8. Teacher 6817 still sees “not published”.
9. Admin publishes.
10. Teacher 6817 now sees anonymous aggregated results and can download PDF.
11. HOD of the same department (with scope) can also view department-level summary.
12. Dean (linked to that HOD) sees compliance against requirements.

---

## 8. STATE MACHINE SUMMARY

**Form states:**  
`draft` → `open` → `closed` → `published` (optional archive)

**User flags:**  
`is_active`, `must_change_password`, `email_verified`, `onboarding_complete`

**Second-faculty status:**  
`unresolved` | `confirmed` | `rejected` | `conflict`

Transitions are explicit admin/HOD actions except automatic eligibility derived from data.

---

**This document is exhaustive.**  
Any new screen or branch must be added here before implementation.
