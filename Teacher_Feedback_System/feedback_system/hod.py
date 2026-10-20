"""HOD portal — department-scoped form management and results."""
from flask import (Blueprint, abort, flash, redirect, render_template, request,
                   url_for)

from . import db, services
from .security import (audit, current_user, role_required, require_branch_access,
                       scoped_branch_ids_or_none, csrf_token)

bp = Blueprint('hod', __name__, url_prefix='/hod')


def _hod_branches(user):
    ids = scoped_branch_ids_or_none(user)
    if not ids:
        return []
    placeholders = ','.join('?' * len(ids))
    return db.query(
        f'SELECT id, code, name FROM branches WHERE id IN ({placeholders}) ORDER BY code',
        tuple(ids))


@bp.route('/')
@role_required('hod')
def dashboard():
    user = current_user()
    branches = _hod_branches(user)
    branch_ids = [b['id'] for b in branches]

    stats = {
        'branches': branches,
        'student_count': 0,
        'faculty_count': 0,
        'forms_draft': 0,
        'forms_open': 0,
        'forms_closed': 0,
        'sfa_confirmed': 0,
        'sfa_unresolved': 0,
        'recent_forms': [],
    }
    if branch_ids:
        ph = ','.join('?' * len(branch_ids))
        stats['student_count'] = db.query(
            f"""SELECT COUNT(DISTINCT e.student_user_id) c FROM enrollments e
                JOIN timetables t ON t.id=e.timetable_id
                WHERE t.branch_id IN ({ph}) AND e.is_deleted=0""",
            tuple(branch_ids), one=True)['c']
        stats['faculty_count'] = db.query(
            f"""SELECT COUNT(DISTINCT cs.teacher_user_id) c FROM class_sessions cs
                JOIN timetables t ON t.id=cs.timetable_id
                WHERE t.branch_id IN ({ph}) AND cs.is_deleted=0
                  AND cs.teacher_user_id IS NOT NULL""",
            tuple(branch_ids), one=True)['c']
        for status, key in [('draft', 'forms_draft'), ('open', 'forms_open'),
                            ('closed', 'forms_closed')]:
            stats[key] = db.query(
                f"""SELECT COUNT(*) c FROM feedback_forms
                    WHERE branch_id IN ({ph}) AND status=? AND is_deleted=0""",
                tuple(branch_ids) + (status,), one=True)['c']
        stats['sfa_confirmed'] = db.query(
            f"""SELECT COUNT(*) c FROM second_faculty_assignments
                WHERE branch_id IN ({ph}) AND status='confirmed'""",
            tuple(branch_ids), one=True)['c']
        stats['sfa_unresolved'] = db.query(
            f"""SELECT COUNT(*) c FROM second_faculty_assignments
                WHERE branch_id IN ({ph}) AND status='unresolved'""",
            tuple(branch_ids), one=True)['c']
        stats['recent_forms'] = db.query(
            f"""SELECT id, title, status, category, snapshot_subject_code,
                       snapshot_branch, published_at, created_at
                FROM feedback_forms
                WHERE branch_id IN ({ph}) AND is_deleted=0
                ORDER BY created_at DESC LIMIT 15""",
            tuple(branch_ids))

    return render_template('hod_dashboard.html', stats=stats, user=user)


@bp.route('/forms')
@role_required('hod')
def forms():
    user = current_user()
    branches = _hod_branches(user)
    branch_ids = [b['id'] for b in branches]
    forms_list = []
    if branch_ids:
        ph = ','.join('?' * len(branch_ids))
        forms_list = db.query(
            f"""SELECT id, title, status, category, snapshot_subject_code,
                       snapshot_subject_name, snapshot_branch, snapshot_timetable,
                       published_at, closed_at, created_at
                FROM feedback_forms
                WHERE branch_id IN ({ph}) AND is_deleted=0
                ORDER BY created_at DESC""",
            tuple(branch_ids))
    return render_template('hod_forms.html', forms=forms_list, branches=branches)


@bp.route('/forms/new', methods=['GET', 'POST'])
@role_required('hod')
def form_new():
    """HOD reuses admin form builder services with department restriction."""
    user = current_user()
    branches = _hod_branches(user)
    if not branches:
        flash('No department scope assigned. Contact Admin.', 'warning')
        return redirect(url_for('hod.dashboard'))

    if request.method == 'POST':
        branch_id = request.form.get('branch_id', type=int)
        require_branch_access(user, branch_id)
        # Delegate to shared save with category support
        from .admin import _parse_form_payload  # may not exist; use services directly
        flash('Use the form builder linked from Forms. Direct POST scaffold is active.',
              'info')
        return redirect(url_for('hod.forms'))

    # Provide data for a simplified create page that calls admin-style APIs
    # restricted by branch.
    years = db.query('SELECT id, name FROM academic_years ORDER BY name DESC')
    semesters = db.query('SELECT id, number, label FROM semesters ORDER BY number')
    return render_template('hod_form_new.html', branches=branches,
                           years=years, semesters=semesters)


@bp.route('/results')
@role_required('hod')
def results():
    user = current_user()
    branches = _hod_branches(user)
    branch_ids = [b['id'] for b in branches]
    forms_list = []
    if branch_ids:
        ph = ','.join('?' * len(branch_ids))
        forms_list = db.query(
            f"""SELECT f.id, f.title, f.status, f.category, f.snapshot_subject_code,
                       f.snapshot_branch,
                       (SELECT COUNT(*) FROM submissions s WHERE s.form_id=f.id) AS responses
                FROM feedback_forms f
                WHERE f.branch_id IN ({ph}) AND f.is_deleted=0
                  AND f.status IN ('open','closed','archived')
                ORDER BY f.published_at DESC, f.id DESC""",
            tuple(branch_ids))
    return render_template('hod_results.html', forms=forms_list)


@bp.route('/second-faculty')
@role_required('hod')
def second_faculty():
    user = current_user()
    branches = _hod_branches(user)
    branch_ids = [b['id'] for b in branches]
    rows = []
    summary = {'confirmed': 0, 'unresolved': 0, 'conflict': 0, 'rejected': 0}
    if branch_ids:
        ph = ','.join('?' * len(branch_ids))
        rows = db.query(
            f"""SELECT sfa.*, b.code AS branch_code, b.name AS branch_name
                FROM second_faculty_assignments sfa
                LEFT JOIN branches b ON b.id=sfa.branch_id
                WHERE sfa.branch_id IN ({ph})
                ORDER BY sfa.status, sfa.subject_code
                LIMIT 500""",
            tuple(branch_ids))
        for st in summary:
            summary[st] = db.query(
                f"""SELECT COUNT(*) c FROM second_faculty_assignments
                    WHERE branch_id IN ({ph}) AND status=?""",
                tuple(branch_ids) + (st,), one=True)['c']
    return render_template('hod_second_faculty.html', rows=rows, summary=summary,
                           branches=branches)


# --------------------------------------------------------------------------- #
# First-login onboarding wizard
# --------------------------------------------------------------------------- #
@bp.route('/onboarding', methods=['GET', 'POST'])
@role_required('hod')
def onboarding():
    """Multi-step HOD onboarding: email verify → claim exclusive allocations."""
    from . import verification, mailer
    from .security import allocation_owner, hod_allocation_keys

    user = current_user()
    row = db.query(
        'SELECT email, email_verified, onboarding_complete FROM users WHERE id=?',
        (user['id'],), one=True)
    if row and row.get('onboarding_complete'):
        return redirect(url_for('hod.dashboard'))

    email_verified = bool(row and row.get('email_verified'))
    step = request.args.get('step', 'email' if not email_verified else 'scopes')

    years = db.query('SELECT id, name, is_active FROM academic_years ORDER BY name DESC')
    branches = db.query(
        """SELECT b.id, b.code, b.name FROM branches b
           JOIN user_department_scopes uds ON uds.branch_id=b.id
           WHERE uds.user_id=? ORDER BY b.code""",
        (user['id'],))
    semesters = db.query('SELECT id, number, label FROM semesters ORDER BY number')
    # Timetables filtered by allowed branches
    branch_ids = [b['id'] for b in branches]
    timetables = []
    if branch_ids:
        ph = ','.join('?' * len(branch_ids))
        timetables = db.query(
            f"""SELECT t.id, t.code, t.name, t.branch_id, t.semester_id,
                       t.academic_year_id, b.code AS branch_code
                FROM timetables t
                JOIN branches b ON b.id=t.branch_id
                WHERE t.branch_id IN ({ph}) AND t.is_deleted=0
                ORDER BY b.code, t.code""",
            tuple(branch_ids))

    selected = []  # list of claimed keys from session staging
    from flask import session as _session
    staging = _session.get('hod_onboard_staging') or []

    preview = None
    conflicts = []

    if request.method == 'POST':
        action = request.form.get('action') or ''
        if action == 'send_code':
            email = (request.form.get('email') or user.get('email') or '').strip().lower()
            if not email or '@' not in email:
                flash('Enter a valid official email address.', 'error')
            else:
                # Rate limit via verification module
                try:
                    code = verification.issue(user['id'], 'verify_email', email)
                    subj, body, html = mailer.code_email(code, 'verify_email', 10)
                    mailer.send_email(email, subj, body, html)
                    flash('Verification code sent. Check your inbox.', 'success')
                    step = 'verify'
                except verification.Cooldown as cd:
                    flash(f'Please wait {cd.seconds}s before requesting another code.', 'error')
                except Exception:
                    flash('Could not send code. Try again later.', 'error')
        elif action == 'verify_code':
            code = (request.form.get('code') or '').strip()
            verified_email = verification.check(user['id'], 'verify_email', code)
            if verified_email:
                db.execute(
                    'UPDATE users SET email_verified=1, email=? WHERE id=?',
                    (verified_email, user['id']))
                audit('hod.email_verified', 'users', user['id'])
                flash('Email verified.', 'success')
                email_verified = True
                step = 'scopes'
            else:
                flash('Invalid or expired code.', 'error')
                step = 'verify'
        elif action == 'add_scope':
            ay = request.form.get('academic_year_id', type=int)
            br = request.form.get('branch_id', type=int)
            sem = request.form.get('semester_id', type=int)
            tt = request.form.get('timetable_id', type=int)
            if not all([ay, br, sem, tt]):
                flash('Select academic year, department, semester and timetable.', 'error')
            elif br not in branch_ids:
                flash('Department not in your authorised list.', 'error')
            else:
                # Validate timetable belongs to branch/semester/year
                tt_row = db.query(
                    """SELECT id FROM timetables
                       WHERE id=? AND branch_id=? AND semester_id=?
                         AND academic_year_id=? AND is_deleted=0""",
                    (tt, br, sem, ay), one=True)
                if not tt_row:
                    flash('Invalid timetable combination.', 'error')
                else:
                    owner = allocation_owner(ay, br, sem, tt)
                    key = {'academic_year_id': ay, 'branch_id': br,
                           'semester_id': sem, 'timetable_id': tt}
                    if owner and owner != user['id']:
                        conflicts.append(key)
                        flash('That allocation is already owned by another HOD.', 'error')
                    elif key not in staging:
                        staging.append(key)
                        _session['hod_onboard_staging'] = staging
                        flash('Allocation added to selection.', 'success')
            step = 'scopes'
        elif action == 'remove_scope':
            idx = request.form.get('index', type=int)
            if staging and idx is not None and 0 <= idx < len(staging):
                staging.pop(idx)
                _session['hod_onboard_staging'] = staging
            step = 'scopes'
        elif action == 'preview':
            step = 'preview'
            # Build preview counts for staged allocations
            preview = _build_hod_preview(staging)
        elif action == 'confirm':
            # Final transactional claim
            if not staging:
                flash('Add at least one allocation.', 'error')
                step = 'scopes'
            else:
                ok, err = _claim_allocations(user['id'], staging)
                if ok:
                    db.execute(
                        'UPDATE users SET onboarding_complete=1 WHERE id=?',
                        (user['id'],))
                    _session.pop('hod_onboard_staging', None)
                    audit('hod.onboarding_complete', 'users', user['id'],
                          f'{len(staging)} allocations')
                    flash('Onboarding complete. Welcome!', 'success')
                    return redirect(url_for('hod.dashboard'))
                else:
                    flash(err or 'Could not claim allocations (conflict or error).', 'error')
                    step = 'scopes'

    # Enrich staging for display
    display_scopes = []
    for s in staging:
        ay = next((y for y in years if y['id'] == s['academic_year_id']), None)
        br = next((b for b in branches if b['id'] == s['branch_id']), None)
        sem = next((m for m in semesters if m['id'] == s['semester_id']), None)
        tt = next((t for t in timetables if t['id'] == s['timetable_id']), None)
        display_scopes.append({
            **s,
            'academic_year': ay['name'] if ay else '?',
            'branch_code': br['code'] if br else '?',
            'semester_label': sem['label'] if sem else '?',
            'timetable_code': tt['code'] if tt else '?',
        })

    if step == 'preview' and preview is None:
        preview = _build_hod_preview(staging)

    return render_template(
        'hod_onboarding.html',
        step=step, email_verified=email_verified, user=user,
        years=years, branches=branches, semesters=semesters,
        timetables=timetables, display_scopes=display_scopes,
        preview=preview, conflicts=conflicts)


def _build_hod_preview(staging):
    """Read-only preview of sessions/students/teachers/forms for staged keys."""
    if not staging:
        return {'sessions': 0, 'students': 0, 'teachers': 0, 'forms': 0, 'items': []}
    items = []
    total_sessions = total_students = total_teachers = total_forms = 0
    for s in staging:
        sess = db.query(
            """SELECT COUNT(*) c FROM class_sessions
               WHERE timetable_id=? AND is_deleted=0""",
            (s['timetable_id'],), one=True)['c']
        stud = db.query(
            """SELECT COUNT(DISTINCT student_user_id) c FROM enrollments
               WHERE timetable_id=? AND is_deleted=0""",
            (s['timetable_id'],), one=True)['c']
        teach = db.query(
            """SELECT COUNT(DISTINCT teacher_user_id) c FROM class_sessions
               WHERE timetable_id=? AND is_deleted=0 AND teacher_user_id IS NOT NULL""",
            (s['timetable_id'],), one=True)['c']
        forms = db.query(
            """SELECT COUNT(*) c FROM feedback_forms
               WHERE timetable_id=? AND is_deleted=0""",
            (s['timetable_id'],), one=True)['c']
        total_sessions += sess
        total_students += stud
        total_teachers += teach
        total_forms += forms
        items.append({**s, 'sessions': sess, 'students': stud,
                      'teachers': teach, 'forms': forms})
    return {
        'sessions': total_sessions, 'students': total_students,
        'teachers': total_teachers, 'forms': total_forms, 'items': items,
    }


def _claim_allocations(hod_user_id, staging):
    """Claim exclusive allocations transactionally. Returns (ok, error_msg)."""
    from .security import allocation_owner
    conn = db.get_db()
    try:
        for s in staging:
            owner = allocation_owner(
                s['academic_year_id'], s['branch_id'],
                s['semester_id'], s['timetable_id'])
            if owner and owner != hod_user_id:
                conn.rollback()
                return False, 'Allocation already owned by another HOD.'
            # Validate timetable still exists and matches
            tt = conn.execute(
                """SELECT id FROM timetables
                   WHERE id=? AND branch_id=? AND semester_id=?
                     AND academic_year_id=? AND is_deleted=0""",
                (s['timetable_id'], s['branch_id'], s['semester_id'],
                 s['academic_year_id'])).fetchone()
            if not tt:
                conn.rollback()
                return False, 'Invalid timetable combination.'
            try:
                conn.execute(
                    """INSERT INTO hod_allocations
                       (hod_user_id, academic_year_id, branch_id, semester_id,
                        timetable_id, created_by)
                       VALUES(?,?,?,?,?,?)""",
                    (hod_user_id, s['academic_year_id'], s['branch_id'],
                     s['semester_id'], s['timetable_id'], hod_user_id))
            except Exception:
                # Unique constraint violation = concurrent claim
                conn.rollback()
                return False, 'Allocation claimed concurrently by another HOD.'
            key = f"{s['academic_year_id']}:{s['branch_id']}:{s['semester_id']}:{s['timetable_id']}"
            conn.execute(
                """INSERT INTO allocation_history
                   (allocation_key, academic_year_id, branch_id, semester_id,
                    timetable_id, previous_hod_user_id, new_hod_user_id, action,
                    actor_user_id)
                   VALUES(?,?,?,?,?,?,?,?,?)""",
                (key, s['academic_year_id'], s['branch_id'], s['semester_id'],
                 s['timetable_id'], None, hod_user_id, 'claim', hod_user_id))
        conn.commit()
        return True, None
    except Exception as exc:
        try:
            conn.rollback()
        except Exception:
            pass
        return False, str(exc)


# ---------------------------------------------------------------------------
# Change 11: Faculty Performance marks & historical comparison
# ---------------------------------------------------------------------------

@bp.route('/performance')
@role_required('hod')
def performance():
    """Marks-sheet for the HOD's own department(s)."""
    from . import scoring
    user = current_user()
    branches = _hod_branches(user)
    branch_ids = [b['id'] for b in branches]

    academic_year_id = request.args.get('academic_year_id', type=int)
    semester_id = request.args.get('semester_id', type=int)
    subject_code = (request.args.get('subject_code') or '').strip() or None
    teacher_user_id = request.args.get('teacher_user_id', type=int)
    q = (request.args.get('q') or '').strip().lower()

    rows = []
    if branch_ids:
        rows = scoring.faculty_scores_for_branches(
            branch_ids,
            academic_year_id=academic_year_id,
            semester_id=semester_id,
            subject_code=subject_code,
            teacher_user_id=teacher_user_id,
        )
        if q:
            rows = [r for r in rows
                    if q in (r.get('teacher_name') or '').lower()
                    or q in (r.get('teacher_emp_code') or '').lower()
                    or q in (r.get('subject_code') or '').lower()
                    or q in (r.get('subject_name') or '').lower()]

    years = db.query('SELECT id, name FROM academic_years ORDER BY name DESC')
    semesters = db.query('SELECT id, number FROM semesters ORDER BY number')
    return render_template(
        'hod_performance.html',
        user=user, branches=branches, rows=rows,
        years=years, semesters=semesters,
        filters={
            'academic_year_id': academic_year_id,
            'semester_id': semester_id,
            'subject_code': subject_code or '',
            'teacher_user_id': teacher_user_id,
            'q': q,
        })


@bp.route('/performance/faculty/<int:teacher_id>')
@role_required('hod')
def performance_detail(teacher_id):
    from . import scoring
    user = current_user()
    branches = _hod_branches(user)
    branch_ids = [b['id'] for b in branches]
    if not branch_ids:
        abort(403)
    rows = scoring.faculty_scores_for_branches(
        branch_ids, teacher_user_id=teacher_id)
    teacher = db.query(
        'SELECT id, name, emp_code FROM users WHERE id=? AND role IN (\'teacher\',\'hod\')',
        (teacher_id,), one=True)
    if not teacher:
        abort(404)
    return render_template(
        'hod_performance_detail.html',
        user=user, teacher=teacher, rows=rows, branches=branches)


@bp.route('/performance/compare')
@role_required('hod')
def performance_compare():
    from . import scoring
    user = current_user()
    branches = _hod_branches(user)
    branch_ids = [b['id'] for b in branches]
    teacher_id = request.args.get('teacher_id', type=int)
    form_a = request.args.get('form_a', type=int)
    form_b = request.args.get('form_b', type=int)
    comparison = None
    error = None
    teacher_forms = []
    if teacher_id and branch_ids:
        teacher_forms = scoring.faculty_scores_for_branches(
            branch_ids, teacher_user_id=teacher_id)
    if teacher_id and form_a and form_b:
        if form_a == form_b:
            error = 'Select two different periods.'
        else:
            comparison = scoring.compare_periods(teacher_id, form_a, form_b)
            if not comparison.get('ok'):
                error = comparison.get('error', 'Comparison failed')
                comparison = None
    teachers = []
    if branch_ids:
        ph = ','.join('?' * len(branch_ids))
        teachers = db.query(
            f"""SELECT DISTINCT u.id, u.name, u.emp_code
                FROM users u
                JOIN class_sessions cs ON cs.teacher_user_id = u.id
                JOIN timetables t ON t.id = cs.timetable_id
                WHERE t.branch_id IN ({ph}) AND cs.is_deleted=0
                ORDER BY u.name""",
            tuple(branch_ids))
    return render_template(
        'hod_performance_compare.html',
        user=user, branches=branches, teachers=teachers,
        teacher_id=teacher_id, form_a=form_a, form_b=form_b,
        teacher_forms=teacher_forms, comparison=comparison, error=error)
