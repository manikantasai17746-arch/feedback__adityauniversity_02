"""Validate the generated PostgreSQL against the real PostgreSQL parser.

Uses ``pglast`` (libpg_query bindings).  This proves that the translated DDL and
the representative DML/queries are valid PostgreSQL — without needing a running
server.  Skipped if ``pglast`` is not installed.
"""
import pytest

from feedback_system import pg
from feedback_system.schema import MIGRATIONS

pglast = pytest.importorskip('pglast')


def _assert_parseable(sql):
    # ``%s`` is a psycopg placeholder, not SQL; stand in a literal for the parser.
    normalized = pg.to_postgres(sql).replace('%s', 'NULL')
    pglast.parse_sql(normalized)


MIGRATION_STATEMENTS = [s for _v, _d, stmts in MIGRATIONS for s in stmts]


@pytest.mark.parametrize('statement', MIGRATION_STATEMENTS)
def test_migration_sql_is_valid_postgres(statement):
    _assert_parseable(statement)


# Representative DML/queries copied from the application, covering the trickiest
# translators: qmark placeholders, ILIKE, IN-lists, GROUP BY, LIMIT/OFFSET,
# INSERT OR IGNORE, and the anonymous view.
REPRESENTATIVE_SQL = [
    "INSERT OR IGNORE INTO form_sessions(form_id, session_id) VALUES(?,?)",
    ("INSERT OR IGNORE INTO form_sessions(form_id, session_id) "
     "SELECT id, session_id FROM feedback_forms WHERE session_id IS NOT NULL"),
    ("INSERT INTO submissions(form_id, session_id, student_user_id, submitted_at) "
     "VALUES(?,?,?,?)"),
    ("SELECT f.*, cs.period_no, t.code AS timetable, b.code AS branch, "
     "s.number AS semester, ay.name AS academic_year, u.name AS teacher_name, "
     "u.emp_code AS teacher_emp FROM feedback_forms f "
     "LEFT JOIN class_sessions cs ON cs.id=f.session_id "
     "LEFT JOIN timetables t ON t.id=f.timetable_id "
     "LEFT JOIN branches b ON b.id=f.branch_id "
     "LEFT JOIN semesters s ON s.id=f.semester_id "
     "LEFT JOIN academic_years ay ON ay.id=f.academic_year_id "
     "LEFT JOIN users u ON u.id=cs.teacher_user_id "
     "WHERE f.is_deleted=0 AND (f.title LIKE ? OR f.subject_name LIKE ?) "
     "ORDER BY f.id DESC LIMIT ? OFFSET ?"),
    ("SELECT u.id, u.roll, u.name, sb.submitted_at, t.code AS timetable "
     "FROM submissions sb JOIN users u ON u.id=sb.student_user_id "
     "LEFT JOIN class_sessions cs ON cs.id=sb.session_id "
     "LEFT JOIN timetables t ON t.id=cs.timetable_id "
     "WHERE sb.form_id=? ORDER BY u.roll"),
    ("SELECT option_id, COUNT(*) AS n FROM anonymous_answers "
     "WHERE question_id=? AND session_id IN (?,?,?) GROUP BY option_id"),
    ("SELECT COUNT(DISTINCT student_user_id) c FROM session_students "
     "WHERE session_id IN (SELECT session_id FROM form_sessions WHERE form_id=?)"),
    ("UPDATE feedback_forms SET scope=?, subject_code=?, subject_name=? WHERE id=?"),
    ("SELECT COALESCE(f.subject_code, cs.subject_code) AS sc FROM feedback_forms f "
     "LEFT JOIN class_sessions cs ON cs.id=f.session_id WHERE f.id=?"),
    # student dashboard: GROUP BY the form PK, aggregate the joined session columns
    ("SELECT f.*, MIN(cs.period_no) AS period_no, MIN(t.code) AS timetable, "
     "MIN(b.code) AS branch, MIN(s.number) AS semester, MIN(u.name) AS teacher_name, "
     "(SELECT s2.id FROM submissions s2 WHERE s2.form_id=f.id AND s2.student_user_id=?) "
     "AS submission_id, (SELECT s2.submitted_at FROM submissions s2 WHERE s2.form_id=f.id "
     "AND s2.student_user_id=?) AS submitted_at FROM feedback_forms f "
     "JOIN form_sessions fs ON fs.form_id=f.id "
     "JOIN session_students ss ON ss.session_id=fs.session_id AND ss.student_user_id=? "
     "JOIN class_sessions cs ON cs.id=fs.session_id JOIN timetables t ON t.id=cs.timetable_id "
     "JOIN branches b ON b.id=t.branch_id JOIN semesters s ON s.id=t.semester_id "
     "LEFT JOIN users u ON u.id=cs.teacher_user_id "
     "WHERE f.is_deleted=0 AND f.status<>'draft' GROUP BY f.id "
     "ORDER BY (f.status='open') DESC, period_no, f.subject_code"),
    # teacher dashboard: same PK grouping, result-publication columns disambiguated
    ("SELECT f.*, MIN(cs.period_no) AS period_no, MIN(t.code) AS timetable, "
     "MIN(b.code) AS branch, MIN(s.number) AS semester, MIN(ay.name) AS academic_year, "
     "MAX(rp.published_at) AS results_published_at, MAX(rp.is_published) AS is_published "
     "FROM feedback_forms f JOIN form_sessions fs ON fs.form_id=f.id "
     "JOIN class_sessions cs ON cs.id=fs.session_id JOIN timetables t ON t.id=cs.timetable_id "
     "JOIN branches b ON b.id=t.branch_id JOIN semesters s ON s.id=t.semester_id "
     "LEFT JOIN academic_years ay ON ay.id=t.academic_year_id "
     "JOIN result_publications rp ON rp.form_id=f.id AND rp.is_published=1 "
     "WHERE cs.teacher_user_id=? AND f.is_deleted=0 AND f.status<>'draft' GROUP BY f.id "
     "ORDER BY f.subject_name, MIN(b.code), MIN(cs.period_no)"),
    # inserts whose column names are close to PostgreSQL keywords (role/position/text)
    "INSERT OR IGNORE INTO users(role, username, name, emp_code, password_hash) "
    "VALUES('teacher', ?, ?, ?, ?)",
    "INSERT OR IGNORE INTO users(role, username, name, roll, password_hash) "
    "VALUES('student', ?, ?, ?, ?)",
    ("INSERT OR IGNORE INTO assignments(roll, dept, course_code, course_name, emp_code, "
     "emp_name, timetable, period_no, semester, academic_year) VALUES(?,?,?,?,?,?,?,?,?,?)"),
    ("INSERT OR IGNORE INTO class_sessions(timetable_id, subject_code, subject_name, "
     "teacher_user_id, period_no) VALUES(?,?,?,?,?)"),
    ("INSERT OR IGNORE INTO enrollments(student_user_id, timetable_id, semester_id, "
     "academic_year_id) VALUES(?,?,?,?)"),
    "INSERT OR IGNORE INTO session_students(session_id, student_user_id) VALUES(?,?)",
    ("INSERT INTO form_questions(form_id, position, text, qtype, is_required) "
     "VALUES(?,?,?,?,?)"),
    ("INSERT INTO answers(submission_id, question_id, option_id, text_value) VALUES(?,?,?,?)"),
    # SQLite-style upsert: valid in PostgreSQL too (excluded.* is shared syntax)
    ("INSERT INTO result_publications(form_id, session_id, is_published, published_by, "
     "published_at) VALUES(?,?,1,?,?) ON CONFLICT(form_id, session_id) DO UPDATE SET "
     "is_published=1, published_by=excluded.published_by, published_at=excluded.published_at, "
     "unpublished_by=NULL, unpublished_at=NULL"),
]


@pytest.mark.parametrize('sql', REPRESENTATIVE_SQL)
def test_representative_sql_is_valid_postgres(sql):
    _assert_parseable(sql)


def test_anonymous_view_is_valid():
    view = next(s for _v, _d, stmts in MIGRATIONS for s in stmts
                if 'anonymous_answers' in s)
    _assert_parseable(view)


def test_migrations_table_is_text_timestamp_on_postgres():
    """Regression: a TIMESTAMP column must not get the text to_char() default."""
    import inspect
    from feedback_system import db
    from feedback_system.pg import to_postgres
    src = inspect.getsource(db.current_version)
    ddl = src[src.index('CREATE TABLE'):src.index('""")')]
    assert 'TIMESTAMP WITHOUT' not in ddl
    assert 'applied_at TEXT' in to_postgres(ddl)
