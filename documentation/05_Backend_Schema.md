# Backend Schema Document
## Faculty Feedback System — Complete Data Model

**Version:** 8.0 (Migration level v8)  
**Databases supported:** SQLite (development) · PostgreSQL (production)  
**Rule:** Schema evolves only through versioned migrations. No destructive changes to historical feedback data.

---

## 1. Design Principles

1. **Additive migrations only** — columns and tables are added; existing data is never dropped.
2. **Soft deletes** where history matters (`is_deleted`, `deleted_at`).
3. **Role expansion** (adding `hod`, `dean`) is performed carefully so existing users survive.
4. **Anonymity** is enforced at query time; the schema still stores the submission owner for audit and eligibility, but teacher-facing views never expose identity.
5. **Scope tables** (`user_department_scopes`, `dean_hod_assignments`) are the single source of truth for HOD/Dean visibility.

---

## 2. Core Entity Relationship Overview

```
branches 1──* timetables 1──* class_sessions
                │                    │
                *                    *
           enrollments          form_sessions
                │                    │
                *                    *
             users (student)    feedback_forms 1──* form_questions
                                      │
                                      * 
                                 submissions 1──* answers
                                      │
                                 result_publications

users (teacher) ──* class_sessions
users (hod/dean) ──* user_department_scopes ──* branches
dean ──* dean_hod_assignments ──* hod
```

---

## 3. Table Definitions

### 3.1 Academic Structure

#### `branches`
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | |
| code | TEXT UNIQUE NOT NULL | e.g. CSE, ECE |
| name | TEXT NOT NULL | |

#### `academic_years`
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | |
| name | TEXT UNIQUE NOT NULL | e.g. 2026-27 |
| is_active | INTEGER DEFAULT 0 | |

#### `semesters`
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | |
| number | INTEGER UNIQUE NOT NULL | 1, 2, 3… |
| label | TEXT NOT NULL | e.g. “III Semester” |

#### `timetables`
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | |
| branch_id | FK → branches | |
| semester_id | FK → semesters | |
| academic_year_id | FK → academic_years | nullable in some paths |
| code | TEXT NOT NULL | e.g. T1-General |
| name | TEXT NOT NULL | |
| is_deleted | INTEGER DEFAULT 0 | |
| deleted_at | TEXT | |
| UNIQUE(branch_id, semester_id, academic_year_id, code) | | |

#### `class_sessions`
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | |
| timetable_id | FK → timetables | |
| subject_code | TEXT NOT NULL | |
| subject_name | TEXT NOT NULL | |
| teacher_user_id | FK → users | |
| period_no | INTEGER | |
| is_deleted | INTEGER DEFAULT 0 | |
| deleted_at | TEXT | |
| UNIQUE(timetable_id, subject_code, teacher_user_id) | | |

#### `enrollments`
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | |
| student_user_id | FK → users | |
| timetable_id | FK → timetables | |
| semester_id | FK → semesters | |
| academic_year_id | FK → academic_years | |
| is_deleted | INTEGER DEFAULT 0 | |
| deleted_at | TEXT | |

---

### 3.2 Users & Auth

#### `users`
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | |
| role | TEXT NOT NULL | CHECK: admin, teacher, student, hod, dean |
| username | TEXT UNIQUE NOT NULL | roll or emp_code or email |
| email | TEXT | |
| name | TEXT | |
| roll | TEXT | students |
| emp_code | TEXT | teachers / hod / dean |
| password_hash | TEXT NOT NULL | |
| is_active | INTEGER DEFAULT 1 | |
| must_change_password | INTEGER DEFAULT 0 | |
| email_verified | INTEGER / flag | added in later migrations |
| onboarding_complete | INTEGER / flag | hod / dean |
| created_at | TEXT DEFAULT CURRENT_TIMESTAMP | |

Indexes: role, roll, emp_code, username.

#### `email_codes`
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | |
| user_id | FK → users | |
| purpose | TEXT | verify_email, reset_password, … |
| email | TEXT NOT NULL | |
| code_hash | TEXT NOT NULL | only hash stored |
| attempts | INTEGER DEFAULT 0 | |
| created_ts | BIGINT | |
| expires_ts | BIGINT | |

---

### 3.3 Feedback Domain

#### `feedback_forms`
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | |
| title / name | TEXT | |
| status | TEXT | draft / open / closed / published (implementation-specific values) |
| scope | TEXT DEFAULT 'session' | session \| subject |
| subject_code | TEXT | |
| subject_name | TEXT | |
| session_id | FK (legacy) | |
| category | TEXT DEFAULT 'main' | main \| second_faculty |
| second_faculty_assignment_id | FK | optional |
| created_by | FK → users | |
| created_at / updated_at | TEXT | |
| other metadata | | academic year, semester, etc. |

#### `form_questions`
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | |
| form_id | FK → feedback_forms | |
| question_text | TEXT | |
| question_type | TEXT | rating, mcq, text, … |
| sort_order | INTEGER | |
| is_required | INTEGER | |
| options / scale metadata | | via `question_options` or JSON |

#### `question_options`
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | |
| question_id | FK | |
| label | TEXT | |
| value | TEXT / INTEGER | |
| sort_order | INTEGER | |

#### `form_sessions`
| Column | Type | Notes |
|--------|------|-------|
| form_id | FK → feedback_forms | |
| session_id | FK → class_sessions | |
| PRIMARY KEY (form_id, session_id) | | |

#### `submissions`
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | |
| form_id | FK | |
| student_user_id | FK → users | kept for eligibility & audit |
| submitted_at | TEXT / TIMESTAMP | |
| UNIQUE(form_id, student_user_id) | | prevents duplicates |

#### `answers`
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | |
| submission_id | FK | |
| question_id | FK | |
| value / text_answer / option_id | | depending on type |

#### `result_publications` (or equivalent publish flag)
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | |
| form_id | FK | |
| published_by | FK → users | |
| published_at | TEXT | |
| notes | TEXT | |

Teacher-facing queries **must** join through a publication record or equivalent published flag.

---

### 3.4 Second Faculty

#### `second_faculty_assignments`
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | |
| academic_year_id | FK | |
| semester_id | FK | |
| branch_id | FK | |
| timetable_id | FK | |
| session_id | FK | |
| subject_code | TEXT NOT NULL | |
| subject_name | TEXT | |
| main_emp_code | TEXT | |
| main_teacher_user_id | FK → users | |
| second_emp_code | TEXT | |
| second_teacher_user_id | FK → users | |
| period_no | INTEGER | |
| day_label | TEXT | |
| room | TEXT | |
| status | TEXT | confirmed \| unresolved \| rejected \| conflict |
| source_batch_id | INTEGER | |

#### `second_faculty_import_batches` / `second_faculty_import_staging`
- Batch metadata and temporary staging rows for preview-before-commit imports.

---

### 3.5 HOD / Dean Governance

#### `user_department_scopes`
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | |
| user_id | FK → users | hod or dean |
| branch_id | FK → branches | |
| is_primary | INTEGER DEFAULT 0 | |
| created_at | TEXT | |
| UNIQUE(user_id, branch_id) | | |

#### `hod_allocations`
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | |
| hod_user_id | FK | |
| academic_year_id | FK | |
| branch_id | FK | |
| semester_id | FK | |
| timetable_id | FK | |
| created_by | FK | |
| UNIQUE(academic_year_id, branch_id, semester_id, timetable_id) | | |

#### `dean_hod_assignments`
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | |
| dean_user_id | FK | |
| hod_user_id | FK | |
| created_by | FK | |
| UNIQUE(dean_user_id, hod_user_id) | | |

#### `allocation_history`
- Audit of claim / release / reassign / admin_assign actions on allocations.

#### `feedback_requirements`
- Admin-defined requirements (department, year, semester, deadline) used by Dean publication monitoring.

---

### 3.6 Legacy & Support Tables

#### `assignments` / `feedback` (v1 legacy)
- Preserved for backward compatibility. New code paths use the form/answer model.

#### `timetable_imports`
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | |
| fingerprint | TEXT | |
| semester | INTEGER | |
| academic_year | TEXT | |
| filename | TEXT | |
| status | importing \| completed | |
| started_ts | BIGINT | |
| UNIQUE(fingerprint, semester, academic_year) | | |

#### `audit_log`
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | |
| actor_user_id | FK | |
| action | TEXT | e.g. user.scan_login, form.publish |
| entity_type | TEXT | |
| entity_id | INTEGER | |
| detail | TEXT | |
| created_at | TEXT | |

#### `session_students` (if present)
- Optional helper linking sessions to students for eligibility snapshots.

---

## 4. Critical Indexes

- `users(role)`, `users(roll)`, `users(emp_code)`, `users(username)`
- `class_sessions(teacher_user_id)`, `class_sessions(timetable_id)`
- `form_sessions(session_id)`
- `user_department_scopes(user_id)`, `user_department_scopes(branch_id)`
- `dean_hod_assignments(dean_user_id)`, `dean_hod_assignments(hod_user_id)`
- `email_codes(user_id, purpose)`
- `submissions(form_id, student_user_id)` unique

---

## 5. Integrity & Business Rules Enforced by Schema + Application

1. One submission per student per form (`UNIQUE`).
2. Form questions become immutable once any submission exists (application rule).
3. Role CHECK includes `hod` and `dean` after v8.
4. Second-faculty status constrained to allowed values.
5. Soft-deleted rows are excluded from eligibility queries.
6. Publication is an explicit record/flag — absence means “not visible to teacher”.

---

## 6. Migration History Summary

| Version | Purpose |
|---------|---------|
| v1 | Original assignments + feedback |
| v2 | Timetable / period context on assignments |
| v3 | Branches, years, semesters, users, timetables, sessions, enrollments, forms |
| v4–v5 | Form sessions, subject scope |
| v6 | Email verification / reset codes |
| v7 | Timetable import tracking |
| v8 | HOD/Dean scopes, second faculty, requirements, allocations, history |

---

## 7. Query Patterns (Must Respect)

**Student eligible forms**
```text
forms that are open
AND exist form_sessions linking to sessions
AND those sessions belong to timetables
AND student has active enrollment in those timetables
AND no existing submission for (student, form)
```

**Teacher visible results**
```text
sessions where teacher_user_id = current teacher
AND linked forms that have a publication record
→ aggregate answers only
```

**HOD data**
```text
branch_ids = scopes for current user
→ all queries filter by those branch_ids
```

**Dean data**
```text
hod_ids = dean_hod_assignments for current dean
branch_ids = scopes of those hods
→ filter by branch_ids
```

---

## 8. PostgreSQL Notes

- The application contains a translation layer so the same logical schema works on SQLite and PostgreSQL.
- Role CHECK expansion uses constraint replace on PostgreSQL and table rebuild on SQLite.
- Use the pooler connection string (port 6543) for serverless; direct (5432) for one-off imports/migrations if required.

---

**This schema document is the canonical reference for all data modelling decisions.**  
Any new table or column must be introduced via a new migration version and documented here.
