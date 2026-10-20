"""ID-card scan logs a student straight in (default-password students only)."""
import re

import pytest

from feedback_system import create_app, db
from feedback_system.security import hash_password


@pytest.fixture()
def app(tmp_path):
    app = create_app({'TESTING': True, 'DATABASE_URL': None, 'DATABASE': str(tmp_path / 't.db'),
                      'AUTO_IMPORT': False, 'REQUIRE_ACCOUNT_SETUP': False,
                      'ADMIN_EMAIL': 'a@x.in', 'ADMIN_PASSWORD': 'adminpass123',
                      'DEFAULT_STUDENT_PASSWORD': 'webcap'})
    with app.app_context():
        for roll, pw in (('25B11CS001', 'webcap'), ('25B11CS002', 'MyOwn#Pass99')):
            db.execute("INSERT INTO users(role, username, roll, name, password_hash) "
                       "VALUES('student', ?, ?, ?, ?)", (roll, roll, roll, hash_password(pw)))
    return app


def _scan(app, code):
    c = app.test_client()
    html = c.get('/').get_data(as_text=True)
    tok = re.search(r'name="_csrf"\s+value="([^"]+)"', html).group(1)
    r = c.post('/scan-login', data={'code': code, '_csrf': tok})
    with c.session_transaction() as s:
        return r.get_json(), s.get('role')


def test_scan_logs_in_default_password_student(app):
    data, role = _scan(app, '25b11cs001')
    assert data['ok'] and role == 'student'


def test_scan_falls_back_for_personal_password(app):
    data, role = _scan(app, '25B11CS002')
    assert not data['ok'] and data['fallback'] and role is None


def test_scan_unknown_card(app):
    data, role = _scan(app, 'NOPE')
    assert not data['ok'] and role is None


def test_scan_can_be_disabled(app):
    app.config['SCAN_LOGIN'] = False
    data, role = _scan(app, '25B11CS001')
    assert not data['ok'] and role is None


def test_scan_requires_csrf(app):
    r = app.test_client().post('/scan-login', data={'code': '25B11CS001'})
    assert r.status_code in (400, 403)
