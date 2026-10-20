"""Tests for the upgrade: subject-scoped forms, PDF reports, toggle and anonymity.

These reuse the session-scoped throwaway database from ``conftest`` (built by the
real timetable import), so they exercise actual relationships rather than mocks.

Each test that creates a subject-scoped form pulls a *fresh* subject from a pool
via :func:`_next_subject`, so the duplicate guard can never make one test depend
on another.  Every pooled subject is taught across more than one timetable.
"""
import re

from feedback_system import db, services

from helpers import (get_csrf, login_student, publish_form, question_ids,
                     submit_feedback)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
_POOL = None
_POOL_INDEX = 0


def _subject_pool(app):
    """Distinct (configuration, subject) pairs taught across >1 timetable."""
    global _POOL
    if _POOL is None:
        with app.app_context():
            rows = db.query("""
                SELECT cs.subject_code, cs.subject_name, t.academic_year_id y,
                       t.semester_id s, t.branch_id b,
                       COUNT(DISTINCT t.id) tts, COUNT(DISTINCT cs.id) sessions
                FROM class_sessions cs JOIN timetables t ON t.id=cs.timetable_id
                WHERE cs.is_deleted=0
                GROUP BY cs.subject_code, t.academic_year_id, t.semester_id, t.branch_id
                HAVING COUNT(DISTINCT t.id) > 1
                ORDER BY tts DESC, sessions DESC, cs.subject_code""")
            _POOL = [dict(r) for r in rows]
    return _POOL


def _next_subject(app):
    global _POOL_INDEX
    pool = _subject_pool(app)
    row = pool[_POOL_INDEX % len(pool)]
    _POOL_INDEX += 1
    return row


def _subject_body(row, timetable_id=None, title='Subject form'):
    return {
        'form_id': None, 'scope': 'subject', 'title': title, 'instructions': 'anon',
        'academic_year_id': row['y'], 'semester_id': row['s'], 'branch_id': row['b'],
        'timetable_id': timetable_id if timetable_id is not None else '',
        'subject_code': row['subject_code'], 'session_id': '',
        'questions': [
            {'text': 'Rate the teaching', 'qtype': 'rating', 'is_required': True,
             'options': [{'label': 'Excellent', 'value': 1}, {'label': 'Good', 'value': 2},
                         {'label': 'Bad', 'value': 3}, {'label': 'Very poor', 'value': 4}]},
            {'text': 'Suggestions', 'qtype': 'text', 'is_required': False, 'options': []},
        ],
    }


def _post(admin, body, path='/admin/forms/save'):
    tok = get_csrf(admin.get('/admin/forms/new').get_data(as_text=True))
    return admin.post(path, json=body,
                      headers={'X-CSRF-Token': tok, 'X-Requested-With': 'XMLHttpRequest'})


def _create_subject_form(admin, row, timetable_id=None, title='Subject form'):
    r = _post(admin, _subject_body(row, timetable_id, title))
    assert r.status_code == 200 and r.get_json()['ok'], r.get_data(as_text=True)
    return r.get_json()['form_id']


def _timetables_for_subject(app, row):
    with app.app_context():
        return db.query("""SELECT DISTINCT t.id FROM class_sessions cs
            JOIN timetables t ON t.id=cs.timetable_id
            WHERE cs.subject_code=? AND t.academic_year_id=? AND t.semester_id=?
              AND t.branch_id=? ORDER BY t.id""",
            (row['subject_code'], row['y'], row['s'], row['b']))


def _students_in_timetable(app, timetable_id):
    with app.app_context():
        return {r['student_user_id'] for r in db.query(
            'SELECT student_user_id FROM enrollments WHERE timetable_id=? AND is_deleted=0',
            (timetable_id,))}


def _submit(admin, app, form_id, roll, text='Nice class'):
    c = app.test_client()
    login_student(c, roll)
    html = c.get(f'/student/form/{form_id}').get_data(as_text=True)
    rating_qid, text_qid, option_id = question_ids(html)
    return submit_feedback(c, form_id, rating_qid, text_qid, option_id, text)


# --------------------------------------------------------------------------- #
# Scenario A / E / F - all timetables, duplicate prevention, preview accuracy
# --------------------------------------------------------------------------- #
def test_subject_form_all_timetables(admin, app):
    row = _next_subject(app)
    fid = _create_subject_form(admin, row, None, 'All-timetable form')
    with app.app_context():
        form = services.get_form(fid)
        assert form['scope'] == 'subject'
        assert form['timetable_id'] is None
        session_ids = services.form_session_ids(fid)
        # one form, many sessions - NOT one form per timetable
        assert len(session_ids) > 1
        eligible = services.eligible_count_for_form(fid)
        distinct = db.query("""SELECT COUNT(DISTINCT student_user_id) c FROM session_students
            WHERE session_id IN (SELECT session_id FROM form_sessions WHERE form_id=?)""",
            (fid,), one=True)['c']
        assert eligible == distinct > 0
        # every eligible student belongs to the selected configuration
        students = services.eligible_students_for_form(fid)
        assert len(students) == eligible
        for st in students:
            assert st['academic_year'] == form['academic_year']
            assert st['semester'] == form['semester']
            assert st['branch'] == form['branch']
        # no duplicate students
        rolls = [s['roll'] for s in students]
        assert len(rolls) == len(set(rolls))


def test_preview_matches_publication(admin, app):
    row = _next_subject(app)
    params = {'academic_year_id': row['y'], 'semester_id': row['s'],
              'branch_id': row['b'], 'subject_code': row['subject_code']}
    qs = '&'.join(f'{k}={v}' for k, v in params.items())
    preview = admin.get('/admin/api/subject/preview?' + qs).get_json()
    assert preview['eligible'] > 0
    fid = _create_subject_form(admin, row, None, 'Preview-accuracy form')
    with app.app_context():
        assert preview['eligible'] == services.eligible_count_for_form(fid)
        assert preview['sessions'] == len(services.form_session_ids(fid))


def test_duplicate_subject_form_prevented(admin, app):
    row = _next_subject(app)
    body = _subject_body(row, None, 'Duplicate guard form')
    first = _post(admin, body)
    assert first.status_code == 200
    first_id = first.get_json()['form_id']
    second = _post(admin, body)
    assert second.status_code == 409
    data = second.get_json()
    assert data['ok'] is False and data['duplicate'] is True
    assert data['form_id'] == first_id
    with app.app_context():
        count = db.query("""SELECT COUNT(*) c FROM feedback_forms
            WHERE is_deleted=0 AND scope='subject' AND subject_code=?""",
            (row['subject_code'],), one=True)['c']
        # the same subject may legitimately exist in several configurations; here
        # the configuration is unique to this subject in the test data
        assert count == 1


def test_subject_mode_does_not_require_teacher_or_period(admin, app):
    # Only year/semester/branch/subject are supplied - no session/teacher/period.
    row = _next_subject(app)
    fid = _create_subject_form(admin, row, None, 'No teacher/period form')
    with app.app_context():
        assert services.get_form(fid)['session_id']      # representative only
        assert len(services.form_session_ids(fid)) > 1


# --------------------------------------------------------------------------- #
# Scenario B / G - specific timetable restriction + per-form tracking
# --------------------------------------------------------------------------- #
def test_subject_form_specific_timetable(admin, app):
    row = _next_subject(app)
    tts = _timetables_for_subject(app, row)
    assert len(tts) >= 2
    chosen, other = tts[0]['id'], tts[1]['id']
    fid = _create_subject_form(admin, row, chosen, 'One-timetable form')
    with app.app_context():
        covered = set(services.form_session_ids(fid))
        assert covered
        for s in covered:
            assert db.query('SELECT timetable_id FROM class_sessions WHERE id=?',
                            (s,), one=True)['timetable_id'] == chosen
        eligible = {s['id'] for s in services.eligible_students_for_form(fid)}
        # a student who only does this subject in the other timetable is excluded
        chosen_students = _students_in_timetable(app, chosen)
        for r in db.query("""SELECT DISTINCT ss.student_user_id FROM session_students ss
                JOIN class_sessions cs ON cs.id=ss.session_id
                WHERE cs.subject_code=? AND cs.timetable_id=?""",
                (row['subject_code'], other)):
            if r['student_user_id'] not in chosen_students:
                assert r['student_user_id'] not in eligible


def test_tracking_is_per_form(admin, app):
    row = _next_subject(app)
    tts = _timetables_for_subject(app, row)
    assert len(tts) >= 2
    chosen, other = tts[0]['id'], tts[1]['id']
    fa = _create_subject_form(admin, row, chosen, 'Tracking form A')
    fb = _create_subject_form(admin, row, other, 'Tracking form B')
    publish_form(admin, fa)
    publish_form(admin, fb)
    with app.app_context():
        roll = services.eligible_students_for_form(fa)[0]['roll']
    _submit(admin, app, fa, roll)
    with app.app_context():
        assert services.response_count(fa) == 1
        assert services.response_count(fb) == 0          # not counted on the other form
        assert roll in [r['roll'] for r in services.submitted_rolls(fa)]
        assert roll not in [r['roll'] for r in services.not_submitted_rolls(fa)]


# --------------------------------------------------------------------------- #
# Scenario C / D - other subjects and other configurations are excluded
# --------------------------------------------------------------------------- #
def test_other_subject_students_excluded(admin, app):
    row = _next_subject(app)
    fid = _create_subject_form(admin, row, None, 'Eligibility form')
    with app.app_context():
        eligible_ids = {s['id'] for s in services.eligible_students_for_form(fid)}
        not_taking = db.query("""SELECT u.id FROM users u
            WHERE u.role='student' AND u.is_active=1 AND u.id NOT IN (
                SELECT DISTINCT ss.student_user_id FROM session_students ss
                JOIN class_sessions cs ON cs.id=ss.session_id
                WHERE cs.subject_code=?) LIMIT 1""",
            (row['subject_code'],), one=True)
        assert not_taking is not None
        assert not_taking['id'] not in eligible_ids


# --------------------------------------------------------------------------- #
# Invalid configurations are rejected
# --------------------------------------------------------------------------- #
def test_subject_mode_requires_subject(admin, app):
    row = _next_subject(app)
    body = _subject_body(row)
    body['subject_code'] = ''
    r = _post(admin, body)
    assert r.status_code == 400
    assert r.get_json()['ok'] is False


def test_subject_mode_unknown_subject_rejected(admin, app):
    row = _next_subject(app)
    body = _subject_body(row)
    body['subject_code'] = 'NOPE-9999'
    r = _post(admin, body)
    assert r.status_code == 400


# --------------------------------------------------------------------------- #
# PDF reports
# --------------------------------------------------------------------------- #
def _pdf_pages(data):
    return len(re.findall(rb'/Type\s*/Page[^s]', data))


def test_submitted_pdf_matches_database(admin, app):
    row = _next_subject(app)
    fid = _create_subject_form(admin, row, None, 'PDF submitted form')
    publish_form(admin, fid)
    with app.app_context():
        rolls = [s['roll'] for s in services.eligible_students_for_form(fid)][:3]
    for roll in rolls:
        _submit(admin, app, fid, roll)
    r = admin.get(f'/admin/reports/submitted-students.pdf?form_id={fid}')
    assert r.status_code == 200
    assert r.mimetype == 'application/pdf'
    assert r.data[:5] == b'%PDF-'
    assert 'attachment' in r.headers['Content-Disposition']
    with app.app_context():
        rows = services.report_rows([services.get_form(fid)], 'submitted')
        assert len(rows) == 3
        assert {x['roll'] for x in rows} == set(rolls)
        assert all(x['status'] == 'Submitted' for x in rows)


def test_not_submitted_pdf_excludes_submitters(admin, app):
    row = _next_subject(app)
    fid = _create_subject_form(admin, row, None, 'PDF pending form')
    publish_form(admin, fid)
    with app.app_context():
        everyone = [s['roll'] for s in services.eligible_students_for_form(fid)]
        submitter = everyone[0]
    _submit(admin, app, fid, submitter)

    r = admin.get(f'/admin/reports/not-submitted-students.pdf?form_id={fid}')
    assert r.status_code == 200 and r.data[:5] == b'%PDF-'
    with app.app_context():
        pending = services.report_rows([services.get_form(fid)], 'not_submitted')
        pending_rolls = {x['roll'] for x in pending}
        assert submitter not in pending_rolls
        assert len(pending) == len(everyone) - 1
        assert all(x['status'] == 'Not Submitted' for x in pending)
        assert _pdf_pages(r.data) >= 1


def test_empty_report_is_valid(admin, app):
    # A session-scoped form with eligible students but zero submissions.
    with app.app_context():
        sid = db.query("""SELECT ss.session_id FROM session_students ss
            GROUP BY ss.session_id HAVING COUNT(*)>3 ORDER BY ss.session_id LIMIT 1""",
            one=True)['session_id']
    tok = get_csrf(admin.get('/admin/forms/new').get_data(as_text=True))
    r = admin.post('/admin/forms/save',
                   json={'form_id': None, 'title': 'Empty report form', 'session_id': sid,
                         'questions': [{'text': 'Q', 'qtype': 'rating', 'is_required': True,
                                        'options': [{'label': 'A', 'value': 1},
                                                    {'label': 'B', 'value': 2}]}]},
                   headers={'X-CSRF-Token': tok, 'X-Requested-With': 'XMLHttpRequest'})
    fid = r.get_json()['form_id']
    pdf = admin.get(f'/admin/reports/submitted-students.pdf?form_id={fid}')
    assert pdf.status_code == 200 and pdf.data[:5] == b'%PDF-'
    with app.app_context():
        assert services.report_rows([services.get_form(fid)], 'submitted') == []


def test_reports_require_admin(app):
    anon = app.test_client()
    assert anon.get('/admin/reports/submitted-students.pdf').status_code == 302
    st = app.test_client()
    with app.app_context():
        roll = db.query("SELECT roll FROM users WHERE role='student' AND is_active=1 LIMIT 1",
                        one=True)['roll']
    login_student(st, roll)
    assert st.get('/admin/reports/submitted-students.pdf').status_code == 403
    assert st.get('/admin/reports/not-submitted-students.pdf').status_code == 403


def test_reports_never_join_answers(admin, app):
    """Report rows carry no answer content and no anonymous linkage."""
    row = _next_subject(app)
    fid = _create_subject_form(admin, row, None, 'Anonymity form')
    publish_form(admin, fid)
    with app.app_context():
        roll = services.eligible_students_for_form(fid)[0]['roll']
    _submit(admin, app, fid, roll, 'SECRET_COMMENT_MARKER')
    with app.app_context():
        for which in ('submitted', 'not_submitted'):
            for r in services.report_rows([services.get_form(fid)], which):
                allowed = {'roll', 'name', 'academic_year', 'semester', 'branch',
                           'timetable', 'section', 'subject_code', 'subject_name',
                           'form_id', 'form_title', 'status', 'submitted_at'}
                assert set(r.keys()) <= allowed
                assert 'SECRET_COMMENT_MARKER' not in str(r.values())


# --------------------------------------------------------------------------- #
# Regression: session-scoped (Normal mode) forms still work
# --------------------------------------------------------------------------- #
def test_normal_mode_form_still_single_session(admin, app):
    with app.app_context():
        sid = db.query('SELECT id FROM class_sessions WHERE is_deleted=0 LIMIT 1',
                       one=True)['id']
    tok = get_csrf(admin.get('/admin/forms/new').get_data(as_text=True))
    r = admin.post('/admin/forms/save',
                   json={'form_id': None, 'scope': 'session', 'title': 'Normal form',
                         'session_id': sid,
                         'questions': [{'text': 'Q', 'qtype': 'rating', 'is_required': True,
                                        'options': [{'label': 'A', 'value': 1},
                                                    {'label': 'B', 'value': 2}]}]},
                   headers={'X-CSRF-Token': tok, 'X-Requested-With': 'XMLHttpRequest'})
    assert r.status_code == 200 and r.get_json()['ok']
    fid = r.get_json()['form_id']
    with app.app_context():
        assert services.form_session_ids(fid) == [sid]
        assert services.get_form(fid)['scope'] == 'session'
        assert services.eligible_count_for_form(fid) == services.eligible_count(sid)
