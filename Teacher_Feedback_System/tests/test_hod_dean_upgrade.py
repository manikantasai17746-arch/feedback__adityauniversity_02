"""Tests for HOD/Dean account import, exclusive allocations, and onboarding gates."""
import csv
import io
import os
import tempfile

import pytest

from feedback_system import create_app
from feedback_system import db as db_module
from feedback_system.security import hash_password, allocation_owner
from helpers import get_csrf, login


@pytest.fixture(scope='module')
def app():
    tmpdir = tempfile.mkdtemp(prefix='ffs-hd-up-')
    application = create_app({
        'TESTING': True,
        'DATABASE': os.path.join(tmpdir, 'test.db'),
        'DATABASE_URL': None,
        'SECRET_KEY': 'test-secret-key-hod-dean-upgrade',
        'AUTO_IMPORT': True,
        'ADMIN_EMAIL': 'admin@college.edu',
        'ADMIN_PASSWORD': 'admin123',
        'DEFAULT_TEACHER_PASSWORD': 'teacher@123',
        'DEFAULT_STUDENT_PASSWORD': 'student@123',
        'LOGIN_MAX_ATTEMPTS': 50,
        'REQUIRE_ACCOUNT_SETUP': False,
    })
    yield application


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def admin(client):
    r = login(client, '/admin/login', {'email': 'admin@college.edu', 'password': 'admin123'})
    assert r.status_code == 302
    return client


def test_admin_hod_dean_page(admin):
    r = admin.get('/admin/accounts/hod-dean')
    assert r.status_code == 200
    assert b'HOD' in r.data


def test_unauthorized_import(client):
    r = client.post('/admin/accounts/hod-dean/import', data={})
    assert r.status_code in (302, 400, 401, 403)


def test_csv_template(admin):
    r = admin.get('/admin/accounts/hod-dean/template.csv')
    assert r.status_code == 200
    assert b'employee_id' in r.data
    assert b'role' in r.data


def test_csv_import_valid_hod(admin, app):
    with app.app_context():
        branch = db_module.query("SELECT code FROM branches LIMIT 1", one=True)
        code = branch['code'] if branch else 'CSE'
        if not branch:
            db_module.execute("INSERT INTO branches(code, name) VALUES('CSE','Computer Science')")
            code = 'CSE'

    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(['role', 'employee_id', 'full_name', 'official_email',
                'designation', 'department_codes', 'active'])
    w.writerow(['hod', 'HODIMP01', 'Import HOD', 'hodimp01@college.edu',
                'Head of Department', code, '1'])
    data = buf.getvalue().encode('utf-8')

    page = admin.get('/admin/accounts/hod-dean')
    csrf = get_csrf(page.get_data(as_text=True))
    r = admin.post('/admin/accounts/hod-dean/import', data={
        '_csrf': csrf,
        'csv_file': (io.BytesIO(data), 'hods.csv'),
    }, content_type='multipart/form-data', follow_redirects=True)
    assert r.status_code == 200
    assert b'Created' in r.data or b'HODIMP01' in r.data

    with app.app_context():
        u = db_module.query(
            "SELECT * FROM users WHERE emp_code='HODIMP01' AND role='hod'", one=True)
        assert u is not None
        assert u['must_change_password'] == 1
        assert u['onboarding_complete'] == 0
        assert u['password_hash'] and u['password_hash'].startswith(('pbkdf2:', 'scrypt:'))
        scopes = db_module.query(
            "SELECT * FROM user_department_scopes WHERE user_id=?", (u['id'],))
        assert len(scopes) >= 1


def test_csv_duplicate_rejected(admin, app):
    with app.app_context():
        branch = db_module.query("SELECT code FROM branches LIMIT 1", one=True)
        code = branch['code'] if branch else 'CSE'

    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(['role', 'employee_id', 'full_name', 'official_email',
                'designation', 'department_codes', 'active'])
    w.writerow(['hod', 'HODIMP01', 'Dup', 'dup@college.edu', 'HOD', code, '1'])
    data = buf.getvalue().encode('utf-8')
    page = admin.get('/admin/accounts/hod-dean')
    csrf = get_csrf(page.get_data(as_text=True))
    r = admin.post('/admin/accounts/hod-dean/import', data={
        '_csrf': csrf,
        'csv_file': (io.BytesIO(data), 'dup.csv'),
    }, content_type='multipart/form-data', follow_redirects=True)
    assert r.status_code == 200
    # Should not create a second account with same emp
    with app.app_context():
        rows = db_module.query(
            "SELECT id FROM users WHERE emp_code='HODIMP01'")
        assert len(rows) == 1


def test_inactive_login_rejected(client, app):
    with app.app_context():
        db_module.execute(
            """INSERT OR IGNORE INTO users(role, username, emp_code, name, email,
               password_hash, is_active, must_change_password)
               VALUES('hod','HODINACT','HODINACT','Inactive','inact@x.edu',?,0,0)""",
            (hash_password('pass12345'),))
    r = client.post('/hod/login', data={
        'emp_code': 'HODINACT', 'password': 'pass12345',
        '_csrf': get_csrf(client.get('/hod/login').get_data(as_text=True)),
    })
    # Should not redirect to dashboard
    assert r.status_code in (200, 302)
    if r.status_code == 302:
        assert 'dashboard' not in (r.headers.get('Location') or '')


def test_hod_login_and_must_change(client, app):
    with app.app_context():
        existing = db_module.query(
            "SELECT id FROM users WHERE username='HODLOGIN1'", one=True)
        if not existing:
            db_module.execute(
                """INSERT INTO users(role, username, emp_code, name, email,
                   password_hash, is_active, must_change_password, onboarding_complete)
                   VALUES('hod','HODLOGIN1','HODLOGIN1','Login HOD','lh@x.edu',?,1,1,1)""",
                (hash_password('TempPass99'),))
        else:
            db_module.execute(
                "UPDATE users SET password_hash=?, must_change_password=1, "
                "onboarding_complete=1, is_active=1 WHERE username='HODLOGIN1'",
                (hash_password('TempPass99'),))

    r = client.post('/hod/login', data={
        'emp_code': 'HODLOGIN1', 'password': 'TempPass99',
        '_csrf': get_csrf(client.get('/hod/login').get_data(as_text=True)),
    }, follow_redirects=False)
    assert r.status_code == 302
    # Follow to see password change enforcement
    r2 = client.get('/hod/', follow_redirects=False)
    # Should be redirected to change-password
    loc = r2.headers.get('Location') or ''
    assert 'change-password' in loc or r2.status_code == 200


def test_exclusive_allocation_unique(app):
    with app.app_context():
        # Ensure structure
        ay = db_module.query('SELECT id FROM academic_years LIMIT 1', one=True)
        br = db_module.query('SELECT id FROM branches LIMIT 1', one=True)
        sem = db_module.query('SELECT id FROM semesters LIMIT 1', one=True)
        tt = db_module.query(
            'SELECT id FROM timetables WHERE is_deleted=0 LIMIT 1', one=True)
        if not all([ay, br, sem, tt]):
            pytest.skip('No academic structure for allocation test')
        # Create two HODs
        for code in ('HODA', 'HODB'):
            if not db_module.query(
                    "SELECT id FROM users WHERE username=?", (code,), one=True):
                db_module.execute(
                    """INSERT INTO users(role, username, emp_code, name, password_hash,
                       is_active, must_change_password, onboarding_complete)
                       VALUES('hod',?,?,?, ?,1,0,1)""",
                    (code, code, code, hash_password('x')))
        hoda = db_module.query("SELECT id FROM users WHERE username='HODA'", one=True)
        hodb = db_module.query("SELECT id FROM users WHERE username='HODB'", one=True)
        # Clean prior
        db_module.execute(
            "DELETE FROM hod_allocations WHERE academic_year_id=? AND branch_id=? "
            "AND semester_id=? AND timetable_id=?",
            (ay['id'], br['id'], sem['id'], tt['id']))
        db_module.execute(
            """INSERT INTO hod_allocations
               (hod_user_id, academic_year_id, branch_id, semester_id, timetable_id)
               VALUES(?,?,?,?,?)""",
            (hoda['id'], ay['id'], br['id'], sem['id'], tt['id']))
        owner = allocation_owner(ay['id'], br['id'], sem['id'], tt['id'])
        assert owner == hoda['id']
        # Second insert must fail unique
        with pytest.raises(Exception):
            db_module.execute(
                """INSERT INTO hod_allocations
                   (hod_user_id, academic_year_id, branch_id, semester_id, timetable_id)
                   VALUES(?,?,?,?,?)""",
                (hodb['id'], ay['id'], br['id'], sem['id'], tt['id']))


def test_existing_roles_still_login(client, app):
    """Regression: student/teacher/admin login still work."""
    r = client.get('/admin/login')
    assert r.status_code == 200
    r = client.get('/teacher/login')
    assert r.status_code == 200
    r = client.get('/')
    assert r.status_code == 200


def test_hod_login_after_csv_import(admin, client, app):
    """Import HOD via CSV, then log in with employee_id + temp password."""
    import re
    with app.app_context():
        branch = db_module.query("SELECT code FROM branches LIMIT 1", one=True)
        if not branch:
            db_module.execute("INSERT INTO branches(code, name) VALUES('CSE','Computer Science')")
            code = 'CSE'
        else:
            code = branch['code']

    emp_id = 'HODLOGINCSV1'
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(['role', 'employee_id', 'full_name', 'official_email',
                'designation', 'department_codes', 'active'])
    w.writerow(['hod', emp_id, 'CSV Login HOD', 'csvhod1@college.edu',
                'Head of Department', code, '1'])
    data = buf.getvalue().encode('utf-8')

    page = admin.get('/admin/accounts/hod-dean')
    csrf = get_csrf(page.get_data(as_text=True))
    r = admin.post('/admin/accounts/hod-dean/import', data={
        '_csrf': csrf,
        'csv_file': (io.BytesIO(data), 'hod_login.csv'),
    }, content_type='multipart/form-data', follow_redirects=True)
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    # Extract the one-time temp password shown in the credentials panel
    # Pattern: inside <code>...</code> near the employee id row
    assert emp_id in body or 'Created' in body
    m = re.search(r'<code>([^<]{8,40})</code>', body)
    assert m, 'temporary password not displayed after import'
    temp_pw = m.group(1)

    with app.app_context():
        u = db_module.query(
            "SELECT * FROM users WHERE emp_code=? AND role='hod'", (emp_id,), one=True)
        assert u is not None
        assert u['must_change_password'] == 1
        assert u['is_active'] == 1
        assert u['username'] == emp_id
        from feedback_system.security import verify_password
        assert verify_password(u['password_hash'], temp_pw)

    # Log out admin session so HOD login is clean
    client.get('/logout')

    login_page = client.get('/hod/login')
    csrf2 = get_csrf(login_page.get_data(as_text=True))
    r2 = client.post('/hod/login', data={
        'emp_code': emp_id,  # exact case as imported
        'password': temp_pw,
        '_csrf': csrf2,
    }, follow_redirects=False)
    assert r2.status_code == 302, f'expected redirect after HOD login, got {r2.status_code}'

    # First protected page must force password change
    r3 = client.get('/hod/', follow_redirects=False)
    loc = r3.headers.get('Location') or ''
    assert 'change-password' in loc, f'expected change-password redirect, got {loc!r}'


def test_hod_login_case_insensitive_emp(admin, client, app):
    """Employee ID typed in lower case must still authenticate."""
    with app.app_context():
        u = db_module.query(
            "SELECT emp_code FROM users WHERE role='hod' AND emp_code='HODLOGINCSV1'",
            one=True)
        if not u:
            pytest.skip('depends on test_hod_login_after_csv_import')
        # Re-set a known temp password for this test
        pw = 'CaseTestPw99'
        db_module.execute(
            "UPDATE users SET password_hash=?, must_change_password=1, is_active=1 "
            "WHERE emp_code='HODLOGINCSV1'",
            (hash_password(pw),))

    client.get('/logout')
    csrf = get_csrf(client.get('/hod/login').get_data(as_text=True))
    r = client.post('/hod/login', data={
        'emp_code': 'hodlogincsv1',  # lower case
        'password': pw,
        '_csrf': csrf,
    }, follow_redirects=False)
    assert r.status_code == 302


def test_dean_login_after_csv_import(admin, client, app):
    """Import Dean via CSV, then log in with employee_id + temp password."""
    import re
    with app.app_context():
        branch = db_module.query("SELECT code FROM branches LIMIT 1", one=True)
        code = branch['code'] if branch else 'CSE'
        if not branch:
            db_module.execute("INSERT INTO branches(code, name) VALUES('CSE','Computer Science')")

    emp_id = 'DEANLOGINCSV1'
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(['role', 'employee_id', 'full_name', 'official_email',
                'designation', 'department_codes', 'active'])
    w.writerow(['dean', emp_id, 'CSV Login Dean', 'csvdean1@college.edu',
                'Dean', code, '1'])
    data = buf.getvalue().encode('utf-8')

    page = admin.get('/admin/accounts/hod-dean')
    csrf = get_csrf(page.get_data(as_text=True))
    r = admin.post('/admin/accounts/hod-dean/import', data={
        '_csrf': csrf,
        'csv_file': (io.BytesIO(data), 'dean_login.csv'),
    }, content_type='multipart/form-data', follow_redirects=True)
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    m = re.search(r'<code>([^<]{8,40})</code>', body)
    assert m, 'temporary password not displayed after Dean import'
    temp_pw = m.group(1)

    with app.app_context():
        u = db_module.query(
            "SELECT * FROM users WHERE emp_code=? AND role='dean'", (emp_id,), one=True)
        assert u is not None
        assert u['must_change_password'] == 1
        from feedback_system.security import verify_password
        assert verify_password(u['password_hash'], temp_pw)

    client.get('/logout')
    csrf2 = get_csrf(client.get('/dean/login').get_data(as_text=True))
    r2 = client.post('/dean/login', data={
        'emp_code': emp_id,
        'password': temp_pw,
        '_csrf': csrf2,
    }, follow_redirects=False)
    assert r2.status_code == 302

    r3 = client.get('/dean/', follow_redirects=False)
    loc = r3.headers.get('Location') or ''
    assert 'change-password' in loc
