"""Admin 'Import semester (Excel)' feature and environment hardening."""
import io
import os

import openpyxl
import pytest

from feedback_system import create_app, db
from feedback_system.import_data import (ImportErrorReport,
                                         claim_timetable_import,
                                         complete_timetable_import,
                                         read_workbook,
                                         reset_student_teacher_passwords,
                                         set_admin_credentials,
                                         validate_semester_year)
from feedback_system.security import hash_password, verify_password
from helpers import get_csrf, token_from

HEADER = ['S.No', 'Time Table', 'Course Code', 'Course Name', 'Emp.Code', 'Emp.Name', 'Roll.No']


def make_xlsx(rows, header=HEADER, sheet='CSE'):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = sheet
    ws.append(['#VALUE!'])
    ws.append(['Time Table Selection List'])
    ws.append(['B.Tech IV Semester, Computer Science & Engineering'])
    ws.append(header)
    for r in rows:
        ws.append(r)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


ROWS = [
    [1, 'T9-Test', '2502ZZ01', 'Import Test Subject', 9901, 'DR. IMPORT TEACHER', '25b11zz001'],
    [2, 'T9-Test', '2502ZZ02', 'Second Subject', 9902, 'SECOND TEACHER', '25B11ZZ001'],
    [3, 'T9-Test', '2502ZZ01', 'Import Test Subject', 9901, 'DR. IMPORT TEACHER', '25B11ZZ002'],
]


def post_import(admin_client, data, name='sem4.xlsx', **fields):
    tok = token_from(admin_client, '/admin/import')
    form = {'_csrf': tok, 'semester': '4', 'academic_year': '2025-26',
            'action': 'import', 'workbook': (io.BytesIO(data), name), **fields}
    return admin_client.post('/admin/import', data=form,
                             content_type='multipart/form-data')


def test_sync_admin_credentials_updates_existing_admin(tmp_path):
    application = create_app({
        'DATABASE': str(tmp_path / 'admin-sync.db'),
        'DATABASE_URL': None,
        'SECRET_KEY': 'test-secret-key',
        'AUTO_IMPORT': False,
    })
    with application.app_context():
        conn = db.get_db()
        conn.execute(
            "INSERT INTO users(role, username, email, name, password_hash) "
            "VALUES('admin', ?, ?, ?, ?)",
            ('old@example.com', 'old@example.com', 'Administrator',
             hash_password('old-password')))
        conn.commit()

        set_admin_credentials(conn, 'NEW@EXAMPLE.COM', 'new-password')
        admin = db.query("SELECT * FROM users WHERE role='admin'", one=True)

        assert admin['username'] == 'new@example.com'
        assert admin['email'] == 'new@example.com'
        assert verify_password(admin['password_hash'], 'new-password')
        assert not verify_password(admin['password_hash'], 'old-password')


def test_reset_student_teacher_passwords_updates_only_requested_roles(tmp_path):
    application = create_app({
        'DATABASE': str(tmp_path / 'student-teacher-reset.db'),
        'DATABASE_URL': None,
        'SECRET_KEY': 'test-secret-key',
        'AUTO_IMPORT': False,
    })
    with application.app_context():
        conn = db.get_db()
        for role, username in (
                ('admin', 'admin@example.com'),
                ('teacher', '9901'),
                ('student', '25B11ZZ001')):
            conn.execute(
                'INSERT INTO users(role, username, name, emp_code, roll, password_hash) '
                'VALUES(?, ?, ?, ?, ?, ?)',
                (role, username, username, username if role == 'teacher' else None,
                 username if role == 'student' else None, hash_password('old-password')))
        conn.commit()

        counts = reset_student_teacher_passwords(
            conn, 'new-teacher-password', 'new-student-password')
        teacher = db.query("SELECT * FROM users WHERE role='teacher'", one=True)
        student = db.query("SELECT * FROM users WHERE role='student'", one=True)
        admin = db.query("SELECT * FROM users WHERE role='admin'", one=True)

        assert counts == (1, 1)
        assert verify_password(teacher['password_hash'], 'new-teacher-password')
        assert teacher['must_change_password'] == 1
        assert verify_password(student['password_hash'], 'new-student-password')
        assert verify_password(admin['password_hash'], 'old-password')


def test_import_page_requires_admin(client):
    assert client.get('/admin/import').status_code == 302


def test_import_page_shows_in_progress_status(admin):
    response = admin.get('/admin/import')
    assert response.status_code == 200
    assert b'role="status"' in response.data
    assert b'aria-live="polite"' in response.data
    assert b'Keep this page open' in response.data


def test_fresh_database_requires_admin_environment_credentials(tmp_path):
    with pytest.raises(RuntimeError, match='ADMIN_EMAIL and ADMIN_PASSWORD'):
        create_app({
            'DATABASE': str(tmp_path / 'missing-admin.db'),
            'DATABASE_URL': None,
            'SECRET_KEY': 'test-secret-key',
            'AUTO_IMPORT': True,
            'ADMIN_EMAIL': '',
            'ADMIN_PASSWORD': '',
            'XLSX_PATH': str(tmp_path / 'missing.xlsx'),
        })


def test_check_file_writes_nothing(app, admin):
    r = post_import(admin, make_xlsx(ROWS), action='check')
    assert r.status_code == 200 and b'nothing saved yet' in r.data
    with app.app_context():
        assert db.query("SELECT COUNT(*) c FROM users WHERE emp_code='9901'", one=True)['c'] == 0


def test_import_new_semester(app, admin):
    r = post_import(admin, make_xlsx(ROWS))
    assert r.status_code == 200 and b'Import complete' in r.data
    with app.app_context():
        assert db.query("SELECT COUNT(*) c FROM users WHERE role='teacher' AND emp_code='9901'",
                        one=True)['c'] == 1
        assert db.query("SELECT COUNT(*) c FROM users WHERE role='student' AND roll='25B11ZZ001'",
                        one=True)['c'] == 1            # roll numbers are upper-cased
        tt = db.query("SELECT t.id FROM timetables t JOIN semesters s ON s.id=t.semester_id "
                      "WHERE t.code='T9-Test' AND s.number=4", one=True)
        assert tt is not None
        assert db.query('SELECT COUNT(*) c FROM class_sessions WHERE timetable_id=?',
                        (tt['id'],), one=True)['c'] == 2
        assert db.query("SELECT COUNT(*) c FROM audit_log WHERE action='import_timetable'",
                        one=True)['c'] >= 1


def test_reimport_same_file_is_idempotent(app, admin):
    workbook = make_xlsx(ROWS)
    first = post_import(admin, workbook, semester='5', academic_year='2026-27')
    assert first.status_code == 200 and b'Import complete' in first.data
    with app.app_context():
        before = db.query('SELECT COUNT(*) c FROM session_students', one=True)['c']
    duplicate = post_import(admin, workbook, semester='5', academic_year='2026-27')
    assert duplicate.status_code == 409 and b'already been imported' in duplicate.data
    with app.app_context():
        assert db.query('SELECT COUNT(*) c FROM session_students', one=True)['c'] == before
        assert db.query(
            'SELECT COUNT(*) c FROM timetable_imports '
            'WHERE semester=5 AND academic_year=?', ('2026-27',), one=True)['c'] == 1


def test_import_claim_blocks_in_progress_and_completed_duplicates(app):
    with app.app_context():
        conn = db.get_db()
        state, import_id = claim_timetable_import(
            conn, 'same-workbook', 4, '2025-26', 'semester.xlsx', now=1000)
        assert (state, import_id) == ('claimed', import_id)
        assert claim_timetable_import(
            conn, 'same-workbook', 4, '2025-26', 'semester.xlsx', now=1001) == (
                'importing', None)

        complete_timetable_import(conn, import_id)
        assert claim_timetable_import(
            conn, 'same-workbook', 4, '2025-26', 'semester.xlsx', now=1002) == (
                'completed', None)


def test_rejects_wrong_extension_and_fake_xlsx(admin):
    assert post_import(admin, b'a,b,c', name='x.csv').status_code == 400
    r = post_import(admin, b'not a zip at all', name='x.xlsx')
    assert r.status_code == 400 and b'not a valid' in r.data


def test_rejects_missing_columns(admin):
    bad = make_xlsx([[1, 'T1', 'C1']], header=['S.No', 'Time Table', 'Course Code'])
    r = post_import(admin, bad)
    assert r.status_code == 400 and b'no header row' in r.data


def test_rejects_bad_semester_and_year(admin):
    assert post_import(admin, make_xlsx(ROWS), semester='9').status_code == 400
    assert post_import(admin, make_xlsx(ROWS), academic_year='2025').status_code == 400


def test_import_requires_csrf(admin):
    r = admin.post('/admin/import', data={'semester': '4', 'academic_year': '2025-26'})
    assert r.status_code == 400


def test_header_order_and_float_codes():
    data = make_xlsx([[1, 'T1', 'C1', 'Subj', 12.0, 'Teach', 'r1']],
                     header=['Roll.No', 'Time Table', 'Course Code', 'Course Name',
                             'Emp.Code', 'Emp.Name', 'S.No'])
    # columns reordered: values still land by header name
    raw, _names, _report = read_workbook(io.BytesIO(data))
    assert raw[0][4] == '12'


def test_validate_semester_year():
    assert validate_semester_year('3', '2025-26') == (3, '2025-26')
    with pytest.raises(ImportErrorReport):
        validate_semester_year('0', '2025-26')


def test_production_requires_secret_key(monkeypatch):
    monkeypatch.setenv('APP_ENV', 'production')
    monkeypatch.delenv('SECRET_KEY', raising=False)
    with pytest.raises(RuntimeError):
        create_app({'DATABASE': ':memory:', 'AUTO_IMPORT': False})


def test_security_headers(client):
    r = client.get('/')
    assert r.headers['X-Frame-Options'] == 'DENY'
    assert r.headers['X-Content-Type-Options'] == 'nosniff'
