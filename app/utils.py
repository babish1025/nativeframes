"""
NativeFrames — Utility functions
"""
import os
import uuid
import json
import time
import logging
from pathlib import Path
from datetime import datetime, timezone
from functools import wraps

from flask import current_app, session, redirect, url_for, request, abort, g
from werkzeug.utils import secure_filename

from .models import db, Admin, ViewerSession, AppSetting, AdminAuditLog, MediaEvent

logger = logging.getLogger('nativeframes.utils')

# ---------------------------------------------------------------------------
# Rate limiter (in-memory, resets on restart)
# ---------------------------------------------------------------------------
_login_attempts: dict[str, list[float]] = {}


def check_rate_limit(ip: str) -> bool:
    """Returns True if the IP is allowed to attempt login."""
    max_attempts = current_app.config.get('LOGIN_MAX_ATTEMPTS', 5)
    window       = current_app.config.get('LOGIN_LOCKOUT_SECONDS', 300)
    now = time.time()
    attempts = _login_attempts.get(ip, [])
    # Remove old attempts outside the window
    attempts = [t for t in attempts if now - t < window]
    _login_attempts[ip] = attempts
    return len(attempts) < max_attempts


def record_attempt(ip: str):
    attempts = _login_attempts.get(ip, [])
    attempts.append(time.time())
    _login_attempts[ip] = attempts


def clear_attempts(ip: str):
    _login_attempts.pop(ip, None)


# ---------------------------------------------------------------------------
# Auth decorators
# ---------------------------------------------------------------------------
def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('admin_logged') or not session.get('admin_id'):
            return redirect(url_for('auth.admin_login', next=request.url))
        # Validate admin still exists
        admin = Admin.query.get(session['admin_id'])
        if not admin:
            session.clear()
            return redirect(url_for('auth.admin_login'))
        g.admin = admin
        return f(*args, **kwargs)
    return decorated


def viewer_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = session.get('viewer_token')
        if not token:
            return redirect(url_for('auth.viewer_entry', next=request.url))
        vs = ViewerSession.query.filter_by(
            session_token=token,
            session_status='active',
        ).first()
        if not vs:
            session.clear()
            return redirect(url_for('auth.viewer_entry'))
        # Touch last_activity
        vs.last_activity_at = utcnow()
        db.session.commit()
        g.viewer_session = vs
        return f(*args, **kwargs)
    return decorated


# ---------------------------------------------------------------------------
# Settings helper
# ---------------------------------------------------------------------------
def get_setting(key: str, default: str = '') -> str:
    s = AppSetting.query.get(key)
    return s.value if s else default


def get_settings_dict() -> dict:
    return {s.key: s.value for s in AppSetting.query.all()}


def setting_enabled(key: str) -> bool:
    return get_setting(key, '0') in ('1', 'true', 'yes', 'on')


# ---------------------------------------------------------------------------
# File utilities
# ---------------------------------------------------------------------------
def allowed_file(filename: str, allowed_exts: set) -> bool:
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_exts


def _get_active_upload_base() -> str:
    upload_base = current_app.config.get('UPLOAD_FOLDER', 'uploads')
    if upload_base.startswith('/var/task'):
        upload_base = '/tmp/uploads'
        current_app.config['UPLOAD_FOLDER'] = upload_base
    return upload_base


def save_upload(file_obj, subfolder: str, allowed_exts: set | None = None) -> tuple[str, str, int]:
    """
    Save an uploaded file to uploads/<subfolder>/.
    Returns (stored_filename, relative_storage_path, file_size).
    """
    if allowed_exts and not allowed_file(file_obj.filename, allowed_exts):
        raise ValueError(f'File type not allowed: {file_obj.filename}')

    ext = Path(secure_filename(file_obj.filename)).suffix.lower()
    stored_name = f'{uuid.uuid4().hex}{ext}'
    upload_base = _get_active_upload_base()
    dest_dir = os.path.join(upload_base, subfolder)

    try:
        os.makedirs(dest_dir, exist_ok=True)
    except OSError:
        upload_base = '/tmp/uploads'
        current_app.config['UPLOAD_FOLDER'] = upload_base
        dest_dir = os.path.join(upload_base, subfolder)
        os.makedirs(dest_dir, exist_ok=True)

    dest_path = os.path.join(dest_dir, stored_name)
    try:
        file_obj.save(dest_path)
    except OSError:
        upload_base = '/tmp/uploads'
        current_app.config['UPLOAD_FOLDER'] = upload_base
        dest_dir = os.path.join(upload_base, subfolder)
        os.makedirs(dest_dir, exist_ok=True)
        dest_path = os.path.join(dest_dir, stored_name)
        file_obj.save(dest_path)

    file_size = os.path.getsize(dest_path)
    storage_path = f'{subfolder}/{stored_name}'
    return stored_name, storage_path, file_size


def delete_file_safe(relative_path: str):
    """Delete a file from the uploads directory, ignoring missing-file errors."""
    if not relative_path:
        return
    upload_base = _get_active_upload_base()
    full_path = os.path.join(upload_base, relative_path)
    try:
        if os.path.exists(full_path):
            os.remove(full_path)
    except OSError as e:
        logger.warning('Could not delete %s: %s', full_path, e)


def generate_image_thumbnail(source_path: str, thumb_filename: str, size=(400, 300)) -> str | None:
    """Generate a thumbnail using Pillow. Returns relative thumbnail path or None."""
    try:
        from PIL import Image
        upload_base = _get_active_upload_base()
        thumb_dir = os.path.join(upload_base, 'thumbnails')
        try:
            os.makedirs(thumb_dir, exist_ok=True)
        except OSError:
            upload_base = '/tmp/uploads'
            current_app.config['UPLOAD_FOLDER'] = upload_base
            thumb_dir = os.path.join(upload_base, 'thumbnails')
            os.makedirs(thumb_dir, exist_ok=True)

        thumb_path = os.path.join(thumb_dir, thumb_filename)
        with Image.open(source_path) as img:
            img.thumbnail(size, Image.LANCZOS)
            img = img.convert('RGB')
            img.save(thumb_path, 'JPEG', quality=85, optimize=True)
        return f'thumbnails/{thumb_filename}'
    except Exception as e:
        logger.warning('Thumbnail generation failed: %s', e)
        return None


# ---------------------------------------------------------------------------
# Audit logging
# ---------------------------------------------------------------------------
def audit_log(action: str, entity_type: str = None, entity_id: int = None, details: str = None):
    admin_id = session.get('admin_id')
    log = AdminAuditLog(
        admin_id    = admin_id,
        action      = action,
        entity_type = entity_type,
        entity_id   = entity_id,
        details     = details,
    )
    db.session.add(log)
    db.session.commit()


# ---------------------------------------------------------------------------
# Viewer activity events
# ---------------------------------------------------------------------------
def log_event(event_type: str, media_id: int = None, folder_id: int = None, meta: dict = None):
    """Log a viewer activity event."""
    token = session.get('viewer_token')
    vs_id = None
    if token:
        vs = ViewerSession.query.filter_by(session_token=token).first()
        if vs:
            vs_id = vs.id
    event = MediaEvent(
        viewer_session_id = vs_id,
        media_id          = media_id,
        folder_id         = folder_id,
        event_type        = event_type,
        event_metadata    = json.dumps(meta) if meta else None,
    )
    db.session.add(event)
    db.session.commit()


# ---------------------------------------------------------------------------
# Misc
# ---------------------------------------------------------------------------
def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def human_filesize(size_bytes: int) -> str:
    if size_bytes is None:
        return '—'
    size = float(size_bytes)
    for unit in ('B', 'KB', 'MB', 'GB', 'TB'):
        if size < 1024.0:
            return f'{size:.1f} {unit}'
        size /= 1024.0
    return f'{size:.1f} PB'


def format_duration(seconds: float | None) -> str:
    if not seconds:
        return ''
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    if h:
        return f'{h}:{m:02}:{s:02}'
    return f'{m}:{s:02}'


def get_client_ip() -> str:
    if request.headers.get('X-Forwarded-For'):
        return request.headers['X-Forwarded-For'].split(',')[0].strip()
    return request.remote_addr or '0.0.0.0'
