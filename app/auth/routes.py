"""
NativeFrames — Auth Routes (Admin + Viewer entry)
"""
import uuid
from flask import (Blueprint, render_template, request, redirect,
                   url_for, session, flash, current_app)

from ..models import db, Admin, ViewerSession
from ..utils  import (check_rate_limit, record_attempt, clear_attempts,
                      audit_log, log_event, utcnow, get_client_ip)

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')


# ---------------------------------------------------------------------------
# Admin Login
# ---------------------------------------------------------------------------
@auth_bp.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if session.get('admin_logged'):
        return redirect(url_for('admin.dashboard'))

    error = None
    if request.method == 'POST':
        ip = get_client_ip()
        if not check_rate_limit(ip):
            error = 'Too many login attempts. Please wait 5 minutes.'
        else:
            username = request.form.get('username', '').strip()
            password = request.form.get('password', '')
            admin = Admin.query.filter_by(username=username).first()
            if admin and admin.check_password(password):
                clear_attempts(ip)
                session.permanent = True
                session['admin_logged'] = True
                session['admin_id']     = admin.id
                admin.last_login_at = utcnow()
                db.session.commit()
                audit_log('admin_login', 'auth', admin.id, f'IP={ip}')
                next_url = request.args.get('next') or url_for('admin.dashboard')
                return redirect(next_url)
            else:
                record_attempt(ip)
                error = 'Invalid username or password.'

    return render_template('auth/admin_login.html', error=error)


@auth_bp.route('/admin/logout')
def admin_logout():
    admin_id = session.get('admin_id')
    session.clear()
    if admin_id:
        audit_log('admin_logout', 'auth', admin_id)
    return redirect(url_for('auth.admin_login'))


# ---------------------------------------------------------------------------
# Viewer Entry
# ---------------------------------------------------------------------------
@auth_bp.route('/viewer', methods=['GET', 'POST'])
def viewer_entry():
    if session.get('viewer_token'):
        vs = ViewerSession.query.filter_by(
            session_token=session['viewer_token'],
            session_status='active',
        ).first()
        if vs:
            return redirect(url_for('gallery.index'))

    error = None
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        if not name:
            error = 'Please enter your name.'
        elif len(name) > 100:
            error = 'Name is too long (max 100 characters).'
        elif len(name) < 2:
            error = 'Name is too short (minimum 2 characters).'
        else:
            token = uuid.uuid4().hex + uuid.uuid4().hex   # 64-char unique token
            normalized = name.lower()
            ip = get_client_ip()
            ua = request.headers.get('User-Agent', '')[:300]
            vs = ViewerSession(
                display_name    = name,
                normalized_name = normalized,
                session_token   = token,
                last_activity_at= utcnow(),
                ip_address      = ip,
                user_agent      = ua,
                session_status  = 'active',
            )
            db.session.add(vs)
            db.session.commit()

            session.permanent = True
            session['viewer_token'] = token
            session['viewer_name']  = name

            # Log event
            log_event('viewer_login', meta={'display_name': name})

            next_url = request.args.get('next') or url_for('gallery.index')
            return redirect(next_url)

    return render_template('auth/viewer_entry.html', error=error)


@auth_bp.route('/viewer/logout')
def viewer_logout():
    token = session.get('viewer_token')
    if token:
        vs = ViewerSession.query.filter_by(session_token=token).first()
        if vs:
            vs.session_status = 'ended'
            vs.ended_at       = utcnow()
            db.session.commit()
            log_event('viewer_logout')
    session.pop('viewer_token', None)
    session.pop('viewer_name', None)
    return redirect(url_for('auth.viewer_entry'))
